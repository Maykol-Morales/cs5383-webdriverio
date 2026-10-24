"""Recargas de celular y recargas programadas (G1)."""
import sqlite3
from decimal import Decimal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from qolqe import reloj
from qolqe.bd import obtener_bd
from qolqe.dependencias import UsuarioActual, usuario_actual
from qolqe.dinero import a_centimos, a_soles, formato
from qolqe.errores import ErrorNegocio, conflicto, no_encontrado, validacion
from qolqe.operaciones import notificar
from qolqe.reglas import nucleo
from qolqe.reglas import recargas as reglas
from qolqe.transacciones import Titular, realizar_recarga

router = APIRouter(tags=["Recargas"])


class InfoBono(BaseModel):
    monto_minimo: str
    porcentaje: str
    tope: str


class ConfiguracionRecargas(BaseModel):
    montos: list[str]
    bono: InfoBono
    max_recargas_diarias_mismo_numero: int


class SolicitudRecarga(BaseModel):
    celular: str = Field(examples=["987111222"])
    monto: Decimal = Field(examples=["30"])


class RecargaRealizada(BaseModel):
    codigo_operacion: str
    celular: str
    monto: str
    bono: str
    origen: str = Field(examples=["MANUAL"])
    saldo: str
    fecha: str


class RecargaListada(BaseModel):
    codigo_operacion: str
    celular: str
    monto: str
    bono: str
    origen: str = Field(examples=["MANUAL", "PROGRAMADA"])
    fecha: str


@router.get("/api/recargas/configuracion", response_model=ConfiguracionRecargas, summary="Montos permitidos y bono")
def configuracion():
    return ConfiguracionRecargas(
        montos=[str(m) for m in reglas.MONTOS_PERMITIDOS],
        bono=InfoBono(monto_minimo=str(reglas.MONTO_MINIMO_BONO), porcentaje="5", tope=str(reglas.TOPE_BONO)),
        max_recargas_diarias_mismo_numero=reglas.MAX_RECARGAS_DIARIAS_MISMO_NUMERO,
    )


@router.get("/api/recargas", response_model=list[RecargaListada], summary="Mis últimas recargas")
def listar(usuario: UsuarioActual = Depends(usuario_actual), bd: sqlite3.Connection = Depends(obtener_bd)):
    filas = bd.execute(
        "SELECT * FROM recargas WHERE usuario_id = ? ORDER BY fecha DESC, id DESC LIMIT 20", (usuario.id,)
    ).fetchall()
    return [RecargaListada(codigo_operacion=f["codigo_operacion"], celular=f["celular"], monto=formato(f["monto_cent"]),
                           bono=formato(f["bono_cent"]), origen=f["origen"], fecha=f["fecha"]) for f in filas]


@router.post("/api/recargas", status_code=status.HTTP_201_CREATED, response_model=RecargaRealizada,
             summary="Recargar un celular")
def recargar(datos: SolicitudRecarga, usuario: UsuarioActual = Depends(usuario_actual),
             bd: sqlite3.Connection = Depends(obtener_bd)):
    comprobante = realizar_recarga(bd, Titular(usuario.id, usuario.celular, usuario.nombres), datos.celular, datos.monto)
    return RecargaRealizada(**comprobante)


# ---------------------------------------------------------------- recargas programadas

class SolicitudProgramada(BaseModel):
    celular: str = Field(examples=["987111222"])
    monto: Decimal = Field(examples=["20"])
    dia: int = Field(description="Día del mes en que se ejecuta (1 a 28)", examples=[15])
    alias: str | None = Field(default=None, examples=["Mamá"])


class CambioProgramada(BaseModel):
    monto: Decimal | None = Field(default=None, examples=["30"])
    dia: int | None = Field(default=None, examples=[20])
    alias: str | None = Field(default=None, examples=["Mamá celular"])


class Programada(BaseModel):
    id: int
    celular: str
    alias: str | None
    monto: str
    dia: int
    estado: str = Field(examples=["ACTIVA", "PAUSADA"])
    proxima_ejecucion: str = Field(examples=["2026-11-15"])
    ultimo_resultado: str = Field(examples=["EXITOSA", "FALLIDA", "SIN_EJECUCIONES"])
    ultimo_detalle: str | None = Field(description="Motivo de la última ejecución fallida")
    ultima_ejecucion_en: str | None
    creada_en: str


def _a_programada(fila: sqlite3.Row) -> Programada:
    return Programada(id=fila["id"], celular=fila["celular"], alias=fila["alias"], monto=formato(fila["monto_cent"]),
                      dia=fila["dia"], estado=fila["estado"], proxima_ejecucion=fila["proxima_ejecucion"],
                      ultimo_resultado=fila["ultimo_resultado"] or "SIN_EJECUCIONES",
                      ultimo_detalle=fila["ultimo_detalle"], ultima_ejecucion_en=fila["ultima_ejecucion_en"],
                      creada_en=fila["creada_en"])


def _programada(bd: sqlite3.Connection, usuario_id: int, programada_id: int) -> sqlite3.Row:
    fila = bd.execute(
        "SELECT * FROM recargas_programadas WHERE id = ? AND usuario_id = ? AND estado != 'ELIMINADA'",
        (programada_id, usuario_id),
    ).fetchone()
    if fila is None:
        raise no_encontrado("PROGRAMADA_NO_ENCONTRADA", "La recarga programada no existe")
    return fila


def _invalida(error: ValueError):
    return validacion("PROGRAMACION_INVALIDA", str(error))


def _verificar_duplicado(bd: sqlite3.Connection, usuario_id: int, celular: str, dia: int, excepto_id: int = 0) -> None:
    if bd.execute(
        """SELECT 1 FROM recargas_programadas WHERE usuario_id = ? AND celular = ? AND dia = ?
           AND estado != 'ELIMINADA' AND id != ?""",
        (usuario_id, celular, dia, excepto_id),
    ).fetchone():
        raise conflicto("PROGRAMACION_DUPLICADA", "Ya tienes una recarga programada a ese número ese día")


def _verificar_limite_activas(bd: sqlite3.Connection, usuario_id: int) -> None:
    activas = bd.execute(
        "SELECT COUNT(*) FROM recargas_programadas WHERE usuario_id = ? AND estado = 'ACTIVA'", (usuario_id,)
    ).fetchone()[0]
    if activas >= reglas.MAX_PROGRAMADAS_ACTIVAS:
        raise validacion("LIMITE_PROGRAMADAS",
                         f"Solo puedes tener {reglas.MAX_PROGRAMADAS_ACTIVAS} recargas programadas activas")


@router.get("/api/recargas/programadas", response_model=list[Programada], summary="Mis recargas programadas")
def listar_programadas(usuario: UsuarioActual = Depends(usuario_actual), bd: sqlite3.Connection = Depends(obtener_bd)):
    filas = bd.execute(
        "SELECT * FROM recargas_programadas WHERE usuario_id = ? AND estado != 'ELIMINADA' ORDER BY proxima_ejecucion, id",
        (usuario.id,),
    ).fetchall()
    return [_a_programada(f) for f in filas]


@router.post("/api/recargas/programadas", status_code=status.HTTP_201_CREATED, response_model=Programada,
             summary="Programar una recarga mensual")
def crear_programada(datos: SolicitudProgramada, usuario: UsuarioActual = Depends(usuario_actual),
                     bd: sqlite3.Connection = Depends(obtener_bd)):
    try:
        nucleo.validar_celular(datos.celular)
        reglas.validar_monto_recarga(datos.monto)
        reglas.validar_dia(datos.dia)
        alias = reglas.validar_alias_programada(datos.alias)
    except ValueError as error:
        raise _invalida(error)
    _verificar_duplicado(bd, usuario.id, datos.celular, datos.dia)
    _verificar_limite_activas(bd, usuario.id)

    hoy = reloj.hoy()
    cursor = bd.execute(
        """INSERT INTO recargas_programadas (usuario_id, celular, monto_cent, dia, alias, proxima_ejecucion, creada_en)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (usuario.id, datos.celular, a_centimos(datos.monto), datos.dia, alias,
         reglas.proxima_ejecucion(datos.dia, hoy).isoformat(), reloj.a_texto(reloj.ahora())),
    )
    return _a_programada(_programada(bd, usuario.id, cursor.lastrowid))


@router.put("/api/recargas/programadas/{programada_id}", response_model=Programada,
            summary="Cambiar el monto, el día o el alias de una programada",
            description="Solo se actualizan los campos enviados. Si cambia el día, se recalcula la próxima ejecución.")
def editar_programada(programada_id: int, datos: CambioProgramada, usuario: UsuarioActual = Depends(usuario_actual),
                      bd: sqlite3.Connection = Depends(obtener_bd)):
    actual = _programada(bd, usuario.id, programada_id)
    monto_cent, dia, alias = actual["monto_cent"], actual["dia"], actual["alias"]
    proxima = actual["proxima_ejecucion"]
    try:
        if datos.monto is not None:
            reglas.validar_monto_recarga(datos.monto)
            monto_cent = a_centimos(datos.monto)
        if "alias" in datos.model_fields_set:
            alias = reglas.validar_alias_programada(datos.alias)
        if datos.dia is not None:
            reglas.validar_dia(datos.dia)
    except ValueError as error:
        raise _invalida(error)
    if datos.dia is not None and datos.dia != actual["dia"]:
        _verificar_duplicado(bd, usuario.id, actual["celular"], datos.dia, excepto_id=programada_id)
        dia = datos.dia
        proxima = reglas.proxima_ejecucion(dia, reloj.hoy()).isoformat()

    bd.execute("UPDATE recargas_programadas SET monto_cent = ?, dia = ?, alias = ?, proxima_ejecucion = ? WHERE id = ?",
               (monto_cent, dia, alias, proxima, programada_id))
    return _a_programada(_programada(bd, usuario.id, programada_id))


@router.post("/api/recargas/programadas/{programada_id}/pausar", response_model=Programada,
             summary="Pausar una recarga programada")
def pausar_programada(programada_id: int, usuario: UsuarioActual = Depends(usuario_actual),
                      bd: sqlite3.Connection = Depends(obtener_bd)):
    actual = _programada(bd, usuario.id, programada_id)
    if actual["estado"] != "ACTIVA":
        raise conflicto("ESTADO_INVALIDO", "Solo se puede pausar una recarga programada activa")
    bd.execute("UPDATE recargas_programadas SET estado = 'PAUSADA' WHERE id = ?", (programada_id,))
    return _a_programada(_programada(bd, usuario.id, programada_id))


@router.post("/api/recargas/programadas/{programada_id}/reanudar", response_model=Programada,
             summary="Reanudar una recarga programada pausada")
def reanudar_programada(programada_id: int, usuario: UsuarioActual = Depends(usuario_actual),
                        bd: sqlite3.Connection = Depends(obtener_bd)):
    actual = _programada(bd, usuario.id, programada_id)
    if actual["estado"] != "PAUSADA":
        raise conflicto("ESTADO_INVALIDO", "Solo se puede reanudar una recarga programada pausada")
    proxima = reglas.proxima_ejecucion(actual["dia"], reloj.hoy()).isoformat()
    bd.execute("UPDATE recargas_programadas SET estado = 'ACTIVA', proxima_ejecucion = ? WHERE id = ?",
               (proxima, programada_id))
    return _a_programada(_programada(bd, usuario.id, programada_id))


@router.delete("/api/recargas/programadas/{programada_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Eliminar una recarga programada")
def eliminar_programada(programada_id: int, usuario: UsuarioActual = Depends(usuario_actual),
                        bd: sqlite3.Connection = Depends(obtener_bd)):
    _programada(bd, usuario.id, programada_id)
    bd.execute("UPDATE recargas_programadas SET estado = 'ELIMINADA' WHERE id = ?", (programada_id,))


def ejecutar_programadas(bd: sqlite3.Connection) -> tuple[int, int]:
    """Proceso diario: ejecuta las programadas activas que vencen hoy o antes. Devuelve (exitosas, fallidas)."""
    hoy = reloj.hoy()
    pendientes = bd.execute(
        """SELECT p.*, u.celular AS celular_titular, u.nombres FROM recargas_programadas p
           JOIN usuarios u ON u.id = p.usuario_id
           WHERE p.estado = 'ACTIVA' AND u.estado = 'ACTIVA' AND p.proxima_ejecucion <= ?
           ORDER BY p.proxima_ejecucion, p.id""",
        (hoy.isoformat(),),
    ).fetchall()
    exitosas = fallidas = 0
    for programada in pendientes:
        titular = Titular(programada["usuario_id"], programada["celular_titular"], programada["nombres"])
        try:
            realizar_recarga(bd, titular, programada["celular"], a_soles(programada["monto_cent"]),
                             origen="PROGRAMADA", programada_id=programada["id"])
            resultado, detalle = "EXITOSA", None
            exitosas += 1
        except ErrorNegocio as error:
            resultado, detalle = "FALLIDA", error.mensaje
            fallidas += 1
            notificar(bd, titular.celular,
                      f"No pudimos realizar tu recarga programada de S/ {formato(programada['monto_cent'])} "
                      f"al {programada['celular']}: {error.mensaje}.")
        bd.execute(
            """UPDATE recargas_programadas SET ultimo_resultado = ?, ultimo_detalle = ?, ultima_ejecucion_en = ?,
               proxima_ejecucion = ? WHERE id = ?""",
            (resultado, detalle, reloj.a_texto(reloj.ahora()),
             reglas.proxima_ejecucion(programada["dia"], hoy).isoformat(), programada["id"]),
        )
    return exitosas, fallidas
