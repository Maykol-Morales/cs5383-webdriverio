"""Perfil, saldo y cierre de la cuenta del usuario autenticado."""
import sqlite3

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from qolqe import reloj
from qolqe.api.autenticacion import correo_en_uso
from qolqe.bd import obtener_bd
from qolqe.credenciales import verificar_pin
from qolqe.dependencias import UsuarioActual, usuario_actual
from qolqe.dinero import formato
from qolqe.errores import conflicto, validacion
from qolqe.operaciones import enmascarar, notificar, saldo_centimos
from qolqe.reglas import nucleo

router = APIRouter(tags=["Cuenta"])


class Perfil(BaseModel):
    id: int
    nombres: str
    celular: str
    correo: str | None
    dni: str = Field(description="DNI enmascarado", examples=["****8912"])
    estado: str = Field(examples=["ACTIVA"])
    creado_en: str


class Saldo(BaseModel):
    saldo: str = Field(pattern=r"^-?\d+\.\d{2}$", examples=["1500.00"])
    moneda: str = Field(examples=["PEN"])
    actualizado_en: str = Field(examples=["2026-10-09T10:15:00"])


class CambioPerfil(BaseModel):
    nombres: str | None = Field(default=None, examples=["Ana Lucía Torres Quispe"])
    correo: str | None = Field(default=None, description="Enviar null o vacío para quitar el correo",
                               examples=["ana.torres@correo.pe"])


class SolicitudCierre(BaseModel):
    pin: str = Field(examples=["4826"])


def _perfil(bd: sqlite3.Connection, usuario_id: int) -> Perfil:
    fila = bd.execute("SELECT * FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
    return Perfil(id=fila["id"], nombres=fila["nombres"], celular=fila["celular"], correo=fila["correo"],
                  dni=enmascarar(fila["dni"]), estado=fila["estado"], creado_en=fila["creado_en"])


@router.get("/api/cuentas/me", response_model=Perfil, summary="Perfil del usuario autenticado")
def perfil(usuario: UsuarioActual = Depends(usuario_actual), bd: sqlite3.Connection = Depends(obtener_bd)):
    return _perfil(bd, usuario.id)


@router.put("/api/cuentas/me", response_model=Perfil, summary="Editar mis nombres y mi correo",
            description="Solo se actualizan los campos enviados. El DNI y el celular no se pueden modificar.")
def editar_perfil(datos: CambioPerfil, usuario: UsuarioActual = Depends(usuario_actual),
                  bd: sqlite3.Connection = Depends(obtener_bd)):
    actual = bd.execute("SELECT nombres, correo FROM usuarios WHERE id = ?", (usuario.id,)).fetchone()
    nombres, correo = actual["nombres"], actual["correo"]

    if "nombres" in datos.model_fields_set:
        try:
            nombres = nucleo.validar_nombres(datos.nombres or "")
        except ValueError as error:
            raise validacion("PERFIL_INVALIDO", str(error))
    if "correo" in datos.model_fields_set:
        correo = None
        if datos.correo is not None and datos.correo.strip():
            try:
                correo = nucleo.validar_correo(datos.correo)
            except ValueError as error:
                raise validacion("CORREO_INVALIDO", str(error))
            if correo_en_uso(bd, correo, excepto_usuario_id=usuario.id):
                raise conflicto("CORREO_REGISTRADO", "El correo ya está registrado en otra cuenta")

    bd.execute("UPDATE usuarios SET nombres = ?, correo = ? WHERE id = ?", (nombres, correo, usuario.id))
    if correo != actual["correo"]:
        destino = correo or "(sin correo)"
        notificar(bd, usuario.celular, f"El correo de tu cuenta Qolqe se cambió a {destino}. Si no fuiste tú, comunícate con nosotros.")
    return _perfil(bd, usuario.id)


@router.get("/api/cuentas/me/saldo", response_model=Saldo, summary="Saldo disponible")
def saldo(usuario: UsuarioActual = Depends(usuario_actual), bd: sqlite3.Connection = Depends(obtener_bd)):
    fila = bd.execute("SELECT saldo_cent, actualizado_en FROM cuentas WHERE usuario_id = ?", (usuario.id,)).fetchone()
    return Saldo(saldo=formato(fila["saldo_cent"]), moneda="PEN", actualizado_en=fila["actualizado_en"])


@router.post("/api/cuentas/me/cierre", status_code=status.HTTP_204_NO_CONTENT, summary="Cerrar mi cuenta",
             description="Requiere el PIN, saldo S/ 0.00 y no tener solicitudes de dinero pendientes.")
def cerrar_cuenta(datos: SolicitudCierre, usuario: UsuarioActual = Depends(usuario_actual),
                  bd: sqlite3.Connection = Depends(obtener_bd)):
    fila = bd.execute("SELECT pin_hash FROM usuarios WHERE id = ?", (usuario.id,)).fetchone()
    if not verificar_pin(datos.pin, fila["pin_hash"]):
        raise validacion("PIN_INCORRECTO", "El PIN no es correcto")
    if saldo_centimos(bd, usuario.id) != 0:
        raise validacion("SALDO_PENDIENTE", "Para cerrar tu cuenta el saldo debe ser S/ 0.00")

    ahora = reloj.a_texto(reloj.ahora())
    pendientes = bd.execute(
        """SELECT COUNT(*) FROM solicitudes WHERE estado = 'PENDIENTE' AND vence_en > ?
           AND (solicitante_id = ? OR destinatario_id = ?)""",
        (ahora, usuario.id, usuario.id),
    ).fetchone()[0]
    if pendientes:
        raise conflicto("SOLICITUDES_PENDIENTES", "Tienes solicitudes de dinero pendientes")

    bd.execute("UPDATE usuarios SET estado = 'CERRADA', cerrada_en = ? WHERE id = ?", (ahora, usuario.id))
    bd.execute("UPDATE sesiones SET cerrada_en = ? WHERE usuario_id = ? AND cerrada_en IS NULL", (ahora, usuario.id))
    bd.execute("UPDATE recargas_programadas SET estado = 'ELIMINADA' WHERE usuario_id = ?", (usuario.id,))
    bd.execute("UPDATE afiliaciones SET debito_automatico = 0 WHERE usuario_id = ?", (usuario.id,))
    notificar(bd, usuario.celular, "Tu cuenta Qolqe fue cerrada. Gracias por usar Qolqe.")
