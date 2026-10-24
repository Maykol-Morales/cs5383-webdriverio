"""Seguridad: cambio de PIN, desbloqueo, dispositivos de confianza y sesiones (G6)."""
import secrets
import sqlite3
from datetime import timedelta

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from qolqe import reloj
from qolqe.bd import obtener_bd
from qolqe.credenciales import hash_pin, verificar_pin
from qolqe.dependencias import UsuarioActual, usuario_actual
from qolqe.errores import conflicto, no_encontrado, validacion
from qolqe.operaciones import notificar
from qolqe.reglas import seguridad as reglas

router = APIRouter(tags=["Seguridad"])


class SolicitudCambioPin(BaseModel):
    pin_actual: str = Field(examples=["4826"])
    pin_nuevo: str = Field(examples=["7305"])


class SolicitudCodigo(BaseModel):
    celular: str = Field(examples=["923456789"])


class ConfirmacionCodigo(BaseModel):
    celular: str = Field(examples=["923456789"])
    codigo: str = Field(examples=["123456"])


class Mensaje(BaseModel):
    mensaje: str


@router.put("/api/seguridad/pin", response_model=Mensaje, summary="Cambiar mi PIN")
def cambiar_pin(datos: SolicitudCambioPin, usuario: UsuarioActual = Depends(usuario_actual),
                bd: sqlite3.Connection = Depends(obtener_bd)):
    fila = bd.execute("SELECT pin_hash FROM usuarios WHERE id = ?", (usuario.id,)).fetchone()
    if not verificar_pin(datos.pin_actual, fila["pin_hash"]):
        raise validacion("PIN_ACTUAL_INCORRECTO", "El PIN actual no es correcto")
    try:
        reglas.validar_nuevo_pin(datos.pin_nuevo, usuario.celular)
    except ValueError as error:
        raise validacion("PIN_INVALIDO", str(error))

    anteriores = bd.execute(
        "SELECT pin_hash FROM historial_pin WHERE usuario_id = ? ORDER BY id DESC LIMIT ?",
        (usuario.id, reglas.PINES_ANTERIORES_A_REVISAR),
    ).fetchall()
    if any(verificar_pin(datos.pin_nuevo, a["pin_hash"]) for a in anteriores):
        raise validacion("PIN_REUTILIZADO", "El nuevo PIN no puede ser igual a uno de tus últimos 3 PIN")

    ahora = reloj.a_texto(reloj.ahora())
    nuevo_hash = hash_pin(datos.pin_nuevo)
    bd.execute("UPDATE usuarios SET pin_hash = ? WHERE id = ?", (nuevo_hash, usuario.id))
    bd.execute("INSERT INTO historial_pin (usuario_id, pin_hash, creado_en) VALUES (?, ?, ?)", (usuario.id, nuevo_hash, ahora))
    notificar(bd, usuario.celular, "Tu PIN de Qolqe fue cambiado. Si no fuiste tú, comunícate con nosotros.")
    return Mensaje(mensaje="Tu PIN fue actualizado")


@router.post("/api/seguridad/desbloqueo/solicitar", status_code=status.HTTP_202_ACCEPTED, response_model=Mensaje,
             summary="Solicitar un código de desbloqueo por SMS")
def solicitar_codigo(datos: SolicitudCodigo, bd: sqlite3.Connection = Depends(obtener_bd)):
    respuesta = Mensaje(mensaje="Si el celular corresponde a una cuenta bloqueada, recibirás un código por SMS")
    usuario = bd.execute("SELECT id, bloqueado_hasta FROM usuarios WHERE celular = ?", (datos.celular,)).fetchone()
    if usuario is None or not usuario["bloqueado_hasta"]:
        return respuesta
    ahora = reloj.ahora()
    if not reglas.esta_bloqueado(reloj.desde_texto(usuario["bloqueado_hasta"]), ahora):
        return respuesta

    codigo = "".join(secrets.choice("0123456789") for _ in range(reglas.LONGITUD_CODIGO_DESBLOQUEO))
    expira = ahora + timedelta(minutes=reglas.MINUTOS_VIGENCIA_CODIGO)
    bd.execute("UPDATE codigos_desbloqueo SET estado = 'REEMPLAZADO' WHERE usuario_id = ? AND estado = 'ACTIVO'",
               (usuario["id"],))
    bd.execute("INSERT INTO codigos_desbloqueo (usuario_id, codigo, expira_en) VALUES (?, ?, ?)",
               (usuario["id"], codigo, reloj.a_texto(expira)))
    notificar(bd, datos.celular, f"Tu código de desbloqueo Qolqe es {codigo}. Vence en {reglas.MINUTOS_VIGENCIA_CODIGO} minutos.")
    return respuesta


@router.post("/api/seguridad/desbloqueo/confirmar", response_model=Mensaje, summary="Desbloquear la cuenta con el código")
def confirmar_codigo(datos: ConfirmacionCodigo, bd: sqlite3.Connection = Depends(obtener_bd)):
    usuario = bd.execute("SELECT id FROM usuarios WHERE celular = ?", (datos.celular,)).fetchone()
    vigente = None
    if usuario:
        vigente = bd.execute(
            "SELECT * FROM codigos_desbloqueo WHERE usuario_id = ? AND estado = 'ACTIVO' ORDER BY id DESC LIMIT 1",
            (usuario["id"],),
        ).fetchone()
    if vigente is None:
        raise validacion("CODIGO_INVALIDO", "No hay un código de desbloqueo activo para este celular")

    if not reglas.codigo_vigente(reloj.desde_texto(vigente["expira_en"]), reloj.ahora()):
        bd.execute("UPDATE codigos_desbloqueo SET estado = 'EXPIRADO' WHERE id = ?", (vigente["id"],))
        bd.commit()
        raise validacion("CODIGO_EXPIRADO", "El código expiró. Solicita uno nuevo")

    if datos.codigo != vigente["codigo"]:
        intentos = vigente["intentos"] + 1
        if intentos >= reglas.INTENTOS_CODIGO:
            bd.execute("UPDATE codigos_desbloqueo SET intentos = ?, estado = 'ANULADO' WHERE id = ?", (intentos, vigente["id"]))
            bd.commit()
            raise validacion("CODIGO_ANULADO", "Superaste los intentos permitidos. Solicita un nuevo código")
        bd.execute("UPDATE codigos_desbloqueo SET intentos = ? WHERE id = ?", (intentos, vigente["id"]))
        bd.commit()
        raise validacion("CODIGO_INCORRECTO", f"Código incorrecto. Te quedan {reglas.INTENTOS_CODIGO - intentos} intentos")

    bd.execute("UPDATE codigos_desbloqueo SET estado = 'USADO' WHERE id = ?", (vigente["id"],))
    bd.execute("UPDATE usuarios SET bloqueado_hasta = NULL, intentos_fallidos = 0 WHERE id = ?", (usuario["id"],))
    return Mensaje(mensaje="Tu cuenta fue desbloqueada. Ya puedes iniciar sesión")


# ---------------------------------------------------------------- dispositivos de confianza

class SolicitudDispositivo(BaseModel):
    nombre: str = Field(examples=["Mi celular"])
    tipo: str = Field(description="CELULAR, TABLET o COMPUTADORA", examples=["CELULAR"])
    pin: str = Field(description="PIN actual, para confirmar", examples=["4826"])


class CambioDispositivo(BaseModel):
    nombre: str = Field(examples=["Celular del trabajo"])


class Dispositivo(BaseModel):
    id: str = Field(description="Identificador que se envía en el login (dispositivo_id)")
    nombre: str
    tipo: str
    registrado_en: str
    ultimo_ingreso: str | None


def _a_dispositivo(fila: sqlite3.Row) -> Dispositivo:
    return Dispositivo(id=fila["id"], nombre=fila["nombre"], tipo=fila["tipo"],
                       registrado_en=fila["registrado_en"], ultimo_ingreso=fila["ultimo_ingreso"])


def _dispositivos(bd: sqlite3.Connection, usuario_id: int) -> list[sqlite3.Row]:
    return bd.execute("SELECT * FROM dispositivos WHERE usuario_id = ? ORDER BY registrado_en, nombre",
                      (usuario_id,)).fetchall()


def _dispositivo(bd: sqlite3.Connection, usuario_id: int, dispositivo_id: str) -> sqlite3.Row:
    fila = bd.execute("SELECT * FROM dispositivos WHERE id = ? AND usuario_id = ?", (dispositivo_id, usuario_id)).fetchone()
    if fila is None:
        raise no_encontrado("DISPOSITIVO_NO_ENCONTRADO", "El dispositivo no existe")
    return fila


def _nombre_disponible(existentes: list[sqlite3.Row], nombre: str, excepto_id: str = "") -> None:
    if any(d["nombre"].lower() == nombre.lower() and d["id"] != excepto_id for d in existentes):
        raise conflicto("DISPOSITIVO_DUPLICADO", "Ya tienes un dispositivo con ese nombre")


@router.get("/api/seguridad/dispositivos", response_model=list[Dispositivo], summary="Mis dispositivos de confianza")
def listar_dispositivos(usuario: UsuarioActual = Depends(usuario_actual), bd: sqlite3.Connection = Depends(obtener_bd)):
    return [_a_dispositivo(f) for f in _dispositivos(bd, usuario.id)]


@router.post("/api/seguridad/dispositivos", status_code=status.HTTP_201_CREATED, response_model=Dispositivo,
             summary="Registrar un dispositivo de confianza")
def registrar_dispositivo(datos: SolicitudDispositivo, usuario: UsuarioActual = Depends(usuario_actual),
                          bd: sqlite3.Connection = Depends(obtener_bd)):
    try:
        nombre = reglas.validar_dispositivo(datos.nombre, datos.tipo)
    except ValueError as error:
        raise validacion("DISPOSITIVO_INVALIDO", str(error))
    fila = bd.execute("SELECT pin_hash FROM usuarios WHERE id = ?", (usuario.id,)).fetchone()
    if not verificar_pin(datos.pin, fila["pin_hash"]):
        raise validacion("PIN_INCORRECTO", "El PIN no es correcto")
    existentes = _dispositivos(bd, usuario.id)
    if len(existentes) >= reglas.MAX_DISPOSITIVOS:
        raise validacion("LIMITE_DISPOSITIVOS", f"Solo puedes registrar {reglas.MAX_DISPOSITIVOS} dispositivos")
    _nombre_disponible(existentes, nombre)

    dispositivo_id = secrets.token_hex(8)
    bd.execute("INSERT INTO dispositivos (id, usuario_id, nombre, tipo, registrado_en) VALUES (?, ?, ?, ?, ?)",
               (dispositivo_id, usuario.id, nombre, datos.tipo, reloj.a_texto(reloj.ahora())))
    notificar(bd, usuario.celular, f"Registraste el dispositivo de confianza \"{nombre}\" en tu cuenta Qolqe.")
    return _a_dispositivo(_dispositivo(bd, usuario.id, dispositivo_id))


@router.put("/api/seguridad/dispositivos/{dispositivo_id}", response_model=Dispositivo, summary="Renombrar un dispositivo")
def renombrar_dispositivo(dispositivo_id: str, datos: CambioDispositivo, usuario: UsuarioActual = Depends(usuario_actual),
                          bd: sqlite3.Connection = Depends(obtener_bd)):
    _dispositivo(bd, usuario.id, dispositivo_id)
    try:
        nombre = reglas.validar_dispositivo(datos.nombre)
    except ValueError as error:
        raise validacion("DISPOSITIVO_INVALIDO", str(error))
    _nombre_disponible(_dispositivos(bd, usuario.id), nombre, excepto_id=dispositivo_id)
    bd.execute("UPDATE dispositivos SET nombre = ? WHERE id = ?", (nombre, dispositivo_id))
    return _a_dispositivo(_dispositivo(bd, usuario.id, dispositivo_id))


@router.delete("/api/seguridad/dispositivos/{dispositivo_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Eliminar un dispositivo de confianza")
def eliminar_dispositivo(dispositivo_id: str, usuario: UsuarioActual = Depends(usuario_actual),
                         bd: sqlite3.Connection = Depends(obtener_bd)):
    _dispositivo(bd, usuario.id, dispositivo_id)
    bd.execute("DELETE FROM dispositivos WHERE id = ?", (dispositivo_id,))


# ---------------------------------------------------------------- sesiones

class DispositivoDeSesion(BaseModel):
    id: str
    nombre: str | None = Field(description="Nulo si el identificador no es un dispositivo de confianza")


class Sesion(BaseModel):
    id: int
    iniciada_en: str
    expira_en: str
    dispositivo: DispositivoDeSesion | None
    actual: bool = Field(description="Es la sesión del token con el que se hace la consulta")


class SesionesCerradas(BaseModel):
    sesiones_cerradas: int


def _sesion_vigente(bd: sqlite3.Connection, usuario_id: int, sesion_id: int) -> sqlite3.Row:
    fila = bd.execute(
        "SELECT * FROM sesiones WHERE id = ? AND usuario_id = ? AND cerrada_en IS NULL AND expira_en > ?",
        (sesion_id, usuario_id, reloj.a_texto(reloj.ahora())),
    ).fetchone()
    if fila is None:
        raise no_encontrado("SESION_NO_ENCONTRADA", "La sesión no existe o ya fue cerrada")
    return fila


@router.get("/api/seguridad/sesiones", response_model=list[Sesion], summary="Mis sesiones activas")
def listar_sesiones(usuario: UsuarioActual = Depends(usuario_actual), bd: sqlite3.Connection = Depends(obtener_bd)):
    filas = bd.execute(
        """SELECT s.*, d.nombre AS dispositivo_nombre FROM sesiones s
           LEFT JOIN dispositivos d ON d.id = s.dispositivo_id AND d.usuario_id = s.usuario_id
           WHERE s.usuario_id = ? AND s.cerrada_en IS NULL AND s.expira_en > ?
           ORDER BY s.iniciada_en DESC, s.id DESC""",
        (usuario.id, reloj.a_texto(reloj.ahora())),
    ).fetchall()
    return [Sesion(id=f["id"], iniciada_en=f["iniciada_en"], expira_en=f["expira_en"],
                   dispositivo=DispositivoDeSesion(id=f["dispositivo_id"], nombre=f["dispositivo_nombre"])
                   if f["dispositivo_id"] else None,
                   actual=f["id"] == usuario.sesion_id) for f in filas]


@router.delete("/api/seguridad/sesiones/{sesion_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Cerrar una sesión específica")
def cerrar_sesion(sesion_id: int, usuario: UsuarioActual = Depends(usuario_actual),
                  bd: sqlite3.Connection = Depends(obtener_bd)):
    _sesion_vigente(bd, usuario.id, sesion_id)
    bd.execute("UPDATE sesiones SET cerrada_en = ? WHERE id = ?", (reloj.a_texto(reloj.ahora()), sesion_id))


@router.delete("/api/seguridad/sesiones", response_model=SesionesCerradas,
               summary="Cerrar todas mis sesiones excepto la actual")
def cerrar_otras_sesiones(usuario: UsuarioActual = Depends(usuario_actual), bd: sqlite3.Connection = Depends(obtener_bd)):
    ahora = reloj.a_texto(reloj.ahora())
    cerradas = bd.execute(
        "UPDATE sesiones SET cerrada_en = ? WHERE usuario_id = ? AND id != ? AND cerrada_en IS NULL AND expira_en > ?",
        (ahora, usuario.id, usuario.sesion_id, ahora),
    ).rowcount
    return SesionesCerradas(sesiones_cerradas=cerradas)
