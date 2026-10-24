"""Solicitudes de dinero entre contactos (G4)."""
import sqlite3
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from qolqe import reloj
from qolqe.api.contactos import buscar_contacto
from qolqe.bd import obtener_bd
from qolqe.dependencias import UsuarioActual, usuario_actual
from qolqe.dinero import a_centimos, a_soles, formato
from qolqe.errores import conflicto, no_encontrado, validacion
from qolqe.operaciones import enmascarar_nombre, notificar
from qolqe.reglas import contactos as reglas
from qolqe.reglas import nucleo
from qolqe.transacciones import Titular, realizar_transferencia

router = APIRouter(tags=["Solicitudes de dinero"])


class SolicitudDinero(BaseModel):
    contacto_id: int = Field(description="Contacto al que se le pide el dinero")
    monto: Decimal = Field(examples=["45.00"])
    motivo: str = Field(examples=["Almuerzo del viernes"])


class Rechazo(BaseModel):
    motivo: str | None = Field(default=None, examples=["Ya te pagué en efectivo"])


class Participante(BaseModel):
    nombre: str
    celular: str


class Solicitud(BaseModel):
    id: int
    solicitante: Participante
    destinatario: Participante
    monto: str
    motivo: str
    estado: str = Field(examples=["PENDIENTE", "ACEPTADA", "RECHAZADA", "CANCELADA", "VENCIDA"])
    creada_en: str
    vence_en: str
    resuelta_en: str | None
    motivo_rechazo: str | None
    codigo_operacion: str | None = Field(description="Código de la transferencia, si fue aceptada")


class MisSolicitudes(BaseModel):
    enviadas: list[Solicitud]
    recibidas: list[Solicitud]


_CONSULTA = """SELECT s.*, us.nombres AS solicitante_nombres, us.celular AS solicitante_celular,
                      ud.nombres AS destinatario_nombres, ud.celular AS destinatario_celular
               FROM solicitudes s
               JOIN usuarios us ON us.id = s.solicitante_id
               JOIN usuarios ud ON ud.id = s.destinatario_id"""


def _a_solicitud(fila: sqlite3.Row) -> Solicitud:
    return Solicitud(
        id=fila["id"],
        solicitante=Participante(nombre=enmascarar_nombre(fila["solicitante_nombres"]), celular=fila["solicitante_celular"]),
        destinatario=Participante(nombre=enmascarar_nombre(fila["destinatario_nombres"]), celular=fila["destinatario_celular"]),
        monto=formato(fila["monto_cent"]),
        motivo=fila["motivo"],
        estado=reglas.estado_solicitud(fila["estado"], reloj.desde_texto(fila["vence_en"]), reloj.ahora()),
        creada_en=fila["creada_en"],
        vence_en=fila["vence_en"],
        resuelta_en=fila["resuelta_en"],
        motivo_rechazo=fila["motivo_rechazo"],
        codigo_operacion=fila["codigo_operacion"],
    )


def _buscar(bd: sqlite3.Connection, solicitud_id: int, usuario_id: int, como: str) -> sqlite3.Row:
    """Busca una solicitud en la que el usuario participa con el rol indicado (solicitante o destinatario)."""
    fila = bd.execute(_CONSULTA + f" WHERE s.id = ? AND s.{como}_id = ?", (solicitud_id, usuario_id)).fetchone()
    if fila is None:
        raise no_encontrado("SOLICITUD_NO_ENCONTRADA", "La solicitud no existe")
    return fila


def _exigir_pendiente(fila: sqlite3.Row) -> None:
    if reglas.estado_solicitud(fila["estado"], reloj.desde_texto(fila["vence_en"]), reloj.ahora()) != "PENDIENTE":
        raise conflicto("ESTADO_INVALIDO", "La solicitud ya no está pendiente")


def _resolver(bd: sqlite3.Connection, solicitud_id: int, estado: str, **campos) -> None:
    asignaciones = ", ".join(f"{campo} = ?" for campo in campos)
    bd.execute(f"UPDATE solicitudes SET estado = ?, resuelta_en = ?{', ' if campos else ''}{asignaciones} WHERE id = ?",
               (estado, reloj.a_texto(reloj.ahora()), *campos.values(), solicitud_id))


@router.get("/api/solicitudes", response_model=MisSolicitudes, summary="Mis solicitudes enviadas y recibidas")
def listar(
    estado: str | None = Query(default=None, description="PENDIENTE, ACEPTADA, RECHAZADA, CANCELADA o VENCIDA"),
    usuario: UsuarioActual = Depends(usuario_actual),
    bd: sqlite3.Connection = Depends(obtener_bd),
):
    if estado is not None and estado not in reglas.ESTADOS_SOLICITUD:
        raise validacion("FILTRO_INVALIDO", f"Estado no válido. Valores: {', '.join(reglas.ESTADOS_SOLICITUD)}")

    def de(columna: str) -> list[Solicitud]:
        filas = bd.execute(_CONSULTA + f" WHERE s.{columna} = ? ORDER BY s.creada_en DESC, s.id DESC", (usuario.id,))
        solicitudes = [_a_solicitud(f) for f in filas.fetchall()]
        return [s for s in solicitudes if estado is None or s.estado == estado]

    return MisSolicitudes(enviadas=de("solicitante_id"), recibidas=de("destinatario_id"))


@router.post("/api/solicitudes", status_code=status.HTTP_201_CREATED, response_model=Solicitud,
             summary="Solicitar dinero a un contacto")
def crear(datos: SolicitudDinero, usuario: UsuarioActual = Depends(usuario_actual),
          bd: sqlite3.Connection = Depends(obtener_bd)):
    contacto = buscar_contacto(bd, usuario.id, datos.contacto_id)
    try:
        nucleo.validar_monto(datos.monto)
        motivo = reglas.validar_motivo(datos.motivo)
    except ValueError as error:
        raise validacion("SOLICITUD_INVALIDA", str(error))
    destinatario = bd.execute("SELECT estado FROM usuarios WHERE id = ?", (contacto["contacto_usuario_id"],)).fetchone()
    if destinatario["estado"] != "ACTIVA":
        raise validacion("DESTINO_INACTIVO", "La cuenta del contacto está cerrada")

    ahora = reloj.ahora()
    pendientes = bd.execute(
        "SELECT COUNT(*) FROM solicitudes WHERE solicitante_id = ? AND estado = 'PENDIENTE' AND vence_en > ?",
        (usuario.id, reloj.a_texto(ahora)),
    ).fetchone()[0]
    if pendientes >= reglas.MAX_SOLICITUDES_PENDIENTES:
        raise validacion("LIMITE_SOLICITUDES",
                         f"Solo puedes tener {reglas.MAX_SOLICITUDES_PENDIENTES} solicitudes pendientes enviadas")

    vence = reglas.vencimiento_solicitud(ahora)
    cursor = bd.execute(
        """INSERT INTO solicitudes (solicitante_id, destinatario_id, monto_cent, motivo, creada_en, vence_en)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (usuario.id, contacto["contacto_usuario_id"], a_centimos(datos.monto), motivo,
         reloj.a_texto(ahora), reloj.a_texto(vence)),
    )
    notificar(bd, contacto["celular"],
              f"{enmascarar_nombre(usuario.nombres)} te solicita S/ {formato(a_centimos(datos.monto))} por \"{motivo}\". "
              f"Vence el {vence:%d/%m a las %H:%M}.")
    return _a_solicitud(_buscar(bd, cursor.lastrowid, usuario.id, "solicitante"))


@router.post("/api/solicitudes/{solicitud_id}/aceptar", response_model=Solicitud,
             summary="Aceptar una solicitud recibida (realiza la transferencia)")
def aceptar(solicitud_id: int, usuario: UsuarioActual = Depends(usuario_actual),
            bd: sqlite3.Connection = Depends(obtener_bd)):
    fila = _buscar(bd, solicitud_id, usuario.id, "destinatario")
    if fila["estado"] != "PENDIENTE":
        raise conflicto("ESTADO_INVALIDO", "La solicitud ya no está pendiente")

    solicitante = bd.execute("SELECT id, nombres, celular FROM usuarios WHERE id = ?", (fila["solicitante_id"],)).fetchone()
    comprobante = realizar_transferencia(bd, Titular(usuario.id, usuario.celular, usuario.nombres),
                                         a_soles(fila["monto_cent"]), destino=solicitante,
                                         descripcion=f"Solicitud: {fila['motivo']}"[:60])
    _resolver(bd, solicitud_id, "ACEPTADA", codigo_operacion=comprobante["codigo_operacion"])
    notificar(bd, solicitante["celular"],
              f"{enmascarar_nombre(usuario.nombres)} aceptó tu solicitud de S/ {formato(fila['monto_cent'])}. "
              f"Operación {comprobante['codigo_operacion']}.")
    return _a_solicitud(_buscar(bd, solicitud_id, usuario.id, "destinatario"))


@router.post("/api/solicitudes/{solicitud_id}/rechazar", response_model=Solicitud,
             summary="Rechazar una solicitud recibida")
def rechazar(solicitud_id: int, datos: Rechazo | None = None, usuario: UsuarioActual = Depends(usuario_actual),
             bd: sqlite3.Connection = Depends(obtener_bd)):
    fila = _buscar(bd, solicitud_id, usuario.id, "destinatario")
    _exigir_pendiente(fila)
    motivo = (datos.motivo or "").strip() if datos else ""
    if len(motivo) > reglas.LONGITUD_MAXIMA_MOTIVO:
        raise validacion("SOLICITUD_INVALIDA", "El motivo admite como máximo 60 caracteres")
    _resolver(bd, solicitud_id, "RECHAZADA", motivo_rechazo=motivo or None)
    notificar(bd, fila["solicitante_celular"],
              f"{enmascarar_nombre(usuario.nombres)} rechazó tu solicitud de S/ {formato(fila['monto_cent'])}"
              + (f": {motivo}." if motivo else "."))
    return _a_solicitud(_buscar(bd, solicitud_id, usuario.id, "destinatario"))


@router.post("/api/solicitudes/{solicitud_id}/cancelar", response_model=Solicitud,
             summary="Cancelar una solicitud enviada")
def cancelar(solicitud_id: int, usuario: UsuarioActual = Depends(usuario_actual),
             bd: sqlite3.Connection = Depends(obtener_bd)):
    fila = _buscar(bd, solicitud_id, usuario.id, "solicitante")
    _exigir_pendiente(fila)
    _resolver(bd, solicitud_id, "CANCELADA")
    return _a_solicitud(_buscar(bd, solicitud_id, usuario.id, "solicitante"))
