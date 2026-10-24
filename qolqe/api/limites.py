"""Límite diario de transferencias y alertas de consumo (G5)."""
import sqlite3
from decimal import Decimal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from qolqe import reloj
from qolqe.bd import obtener_bd
from qolqe.dependencias import UsuarioActual, usuario_actual
from qolqe.dinero import a_centimos, a_soles, formato
from qolqe.errores import conflicto, no_encontrado, validacion
from qolqe.operaciones import (
    estado_limite,
    guardar_estado_limite,
    limite_diario_vigente,
    notificar,
    transferido_hoy_centimos,
)
from qolqe.reglas import limites as reglas
from qolqe.reglas.nucleo import LIMITE_POR_OPERACION
from qolqe.transacciones import gasto_del_dia

router = APIRouter(tags=["Límites"])


class EstadoLimites(BaseModel):
    limite_por_operacion: str
    limite_diario: str = Field(description="Límite diario vigente")
    limite_pendiente: str | None = Field(description="Aumento solicitado que aún no entra en vigencia")
    pendiente_desde: str | None
    usado_hoy: str
    disponible_hoy: str


class SolicitudLimite(BaseModel):
    limite_diario: Decimal = Field(examples=["1500"])


class CambioLimite(EstadoLimites):
    aplicacion: str = Field(examples=["INMEDIATA", "PROGRAMADA"])


def _estado(bd: sqlite3.Connection, usuario_id: int) -> EstadoLimites:
    vigente = limite_diario_vigente(bd, usuario_id)
    usado = transferido_hoy_centimos(bd, usuario_id, reloj.ahora())
    limite_cent = a_centimos(vigente.limite_diario)
    return EstadoLimites(
        limite_por_operacion=str(LIMITE_POR_OPERACION),
        limite_diario=formato(limite_cent),
        limite_pendiente=formato(a_centimos(vigente.limite_pendiente)) if vigente.limite_pendiente is not None else None,
        pendiente_desde=reloj.a_texto(vigente.pendiente_desde) if vigente.pendiente_desde else None,
        usado_hoy=formato(usado),
        disponible_hoy=formato(max(limite_cent - usado, 0)),
    )


@router.get("/api/limites", response_model=EstadoLimites, summary="Ver mis límites")
def ver(usuario: UsuarioActual = Depends(usuario_actual), bd: sqlite3.Connection = Depends(obtener_bd)):
    return _estado(bd, usuario.id)


@router.put("/api/limites", response_model=CambioLimite, summary="Cambiar mi límite diario")
def cambiar(datos: SolicitudLimite, usuario: UsuarioActual = Depends(usuario_actual),
            bd: sqlite3.Connection = Depends(obtener_bd)):
    ahora = reloj.ahora()
    try:
        nuevo = reglas.solicitar_cambio(estado_limite(bd, usuario.id), datos.limite_diario, ahora)
    except ValueError as error:
        raise validacion("LIMITE_INVALIDO", str(error))
    guardar_estado_limite(bd, usuario.id, nuevo)
    pausar_alertas_sobre_el_limite(bd, usuario.id, nuevo.limite_diario)
    programado = nuevo.limite_pendiente is not None and nuevo.limite_pendiente == datos.limite_diario
    if programado:
        notificar(bd, usuario.celular,
                  f"Tu nuevo límite diario de S/ {datos.limite_diario} estará vigente desde {nuevo.pendiente_desde:%d/%m %H:%M}.")
    else:
        notificar(bd, usuario.celular, f"Tu límite diario ahora es S/ {nuevo.limite_diario}.")
    return CambioLimite(**_estado(bd, usuario.id).model_dump(), aplicacion="PROGRAMADA" if programado else "INMEDIATA")


def pausar_alertas_sobre_el_limite(bd: sqlite3.Connection, usuario_id: int, limite_diario: Decimal) -> None:
    """Pausa las alertas de transferencias cuyo umbral quedó por encima del límite vigente."""
    bd.execute(
        f"""UPDATE alertas SET estado = 'PAUSADA' WHERE usuario_id = ? AND estado = 'ACTIVA' AND umbral_cent > ?
            AND tipo IN ({",".join("?" * len(reglas.TIPOS_SUJETOS_AL_LIMITE))})""",
        (usuario_id, a_centimos(limite_diario), *reglas.TIPOS_SUJETOS_AL_LIMITE),
    )


# ---------------------------------------------------------------- alertas de consumo

class SolicitudAlerta(BaseModel):
    tipo: str = Field(description="TRANSFERENCIAS, RECARGAS, PAGOS o TODAS", examples=["TRANSFERENCIAS"])
    umbral: Decimal = Field(examples=["300"])


class CambioAlerta(BaseModel):
    umbral: Decimal | None = Field(default=None, examples=["400"])
    estado: str | None = Field(default=None, description="ACTIVA para reanudar o PAUSADA para pausar")


class Alerta(BaseModel):
    id: int
    tipo: str
    umbral: str
    estado: str = Field(examples=["ACTIVA", "PAUSADA"])
    gasto_hoy: str = Field(description="Gasto de hoy del tipo de la alerta")
    ultima_notificacion: str | None
    creada_en: str


def _a_alerta(bd: sqlite3.Connection, fila: sqlite3.Row) -> Alerta:
    return Alerta(id=fila["id"], tipo=fila["tipo"], umbral=formato(fila["umbral_cent"]), estado=fila["estado"],
                  gasto_hoy=formato(gasto_del_dia(bd, fila["usuario_id"], fila["tipo"])),
                  ultima_notificacion=fila["ultima_notificacion"], creada_en=fila["creada_en"])


def _alerta(bd: sqlite3.Connection, usuario_id: int, alerta_id: int) -> sqlite3.Row:
    fila = bd.execute("SELECT * FROM alertas WHERE id = ? AND usuario_id = ?", (alerta_id, usuario_id)).fetchone()
    if fila is None:
        raise no_encontrado("ALERTA_NO_ENCONTRADA", "La alerta no existe")
    return fila


def _validar_alerta(bd: sqlite3.Connection, usuario_id: int, tipo: str, umbral: Decimal, excepto_id: int = 0) -> None:
    limite = limite_diario_vigente(bd, usuario_id).limite_diario
    try:
        reglas.validar_alerta(tipo, umbral, limite)
    except ValueError as error:
        raise validacion("ALERTA_INVALIDA", str(error))
    if bd.execute("SELECT 1 FROM alertas WHERE usuario_id = ? AND tipo = ? AND umbral_cent = ? AND id != ?",
                  (usuario_id, tipo, a_centimos(umbral), excepto_id)).fetchone():
        raise conflicto("ALERTA_DUPLICADA", "Ya tienes una alerta con ese tipo y umbral")


@router.get("/api/limites/alertas", response_model=list[Alerta], summary="Mis alertas de consumo")
def listar_alertas(usuario: UsuarioActual = Depends(usuario_actual), bd: sqlite3.Connection = Depends(obtener_bd)):
    filas = bd.execute("SELECT * FROM alertas WHERE usuario_id = ? ORDER BY tipo, umbral_cent", (usuario.id,)).fetchall()
    return [_a_alerta(bd, f) for f in filas]


@router.post("/api/limites/alertas", status_code=status.HTTP_201_CREATED, response_model=Alerta,
             summary="Crear una alerta de consumo")
def crear_alerta(datos: SolicitudAlerta, usuario: UsuarioActual = Depends(usuario_actual),
                 bd: sqlite3.Connection = Depends(obtener_bd)):
    _validar_alerta(bd, usuario.id, datos.tipo, datos.umbral)
    cantidad = bd.execute("SELECT COUNT(*) FROM alertas WHERE usuario_id = ?", (usuario.id,)).fetchone()[0]
    if cantidad >= reglas.MAX_ALERTAS:
        raise validacion("LIMITE_ALERTAS", f"Solo puedes tener {reglas.MAX_ALERTAS} alertas")
    cursor = bd.execute("INSERT INTO alertas (usuario_id, tipo, umbral_cent, creada_en) VALUES (?, ?, ?, ?)",
                        (usuario.id, datos.tipo, a_centimos(datos.umbral), reloj.a_texto(reloj.ahora())))
    return _a_alerta(bd, _alerta(bd, usuario.id, cursor.lastrowid))


@router.put("/api/limites/alertas/{alerta_id}", response_model=Alerta,
            summary="Cambiar el umbral, pausar o reanudar una alerta",
            description="Solo se actualizan los campos enviados.")
def editar_alerta(alerta_id: int, datos: CambioAlerta, usuario: UsuarioActual = Depends(usuario_actual),
                  bd: sqlite3.Connection = Depends(obtener_bd)):
    actual = _alerta(bd, usuario.id, alerta_id)
    umbral = datos.umbral if datos.umbral is not None else a_soles(actual["umbral_cent"])
    estado = datos.estado or actual["estado"]
    if estado not in ("ACTIVA", "PAUSADA"):
        raise validacion("ALERTA_INVALIDA", "El estado debe ser ACTIVA o PAUSADA")
    if datos.umbral is not None:
        _validar_alerta(bd, usuario.id, actual["tipo"], umbral, excepto_id=alerta_id)
    if estado == "ACTIVA" and actual["estado"] == "PAUSADA":
        try:
            reglas.validar_umbral_frente_al_limite(actual["tipo"], umbral, limite_diario_vigente(bd, usuario.id).limite_diario)
        except ValueError as error:
            raise validacion("ALERTA_INVALIDA", str(error))
    bd.execute("UPDATE alertas SET umbral_cent = ?, estado = ? WHERE id = ?", (a_centimos(umbral), estado, alerta_id))
    return _a_alerta(bd, _alerta(bd, usuario.id, alerta_id))


@router.delete("/api/limites/alertas/{alerta_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Eliminar una alerta")
def eliminar_alerta(alerta_id: int, usuario: UsuarioActual = Depends(usuario_actual),
                    bd: sqlite3.Connection = Depends(obtener_bd)):
    _alerta(bd, usuario.id, alerta_id)
    bd.execute("DELETE FROM alertas WHERE id = ?", (alerta_id,))
