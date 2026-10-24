"""Registro de usuarios, inicio y cierre de sesión."""
import sqlite3

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from qolqe import reloj
from qolqe.bd import obtener_bd
from qolqe.credenciales import emitir_token, hash_pin, verificar_pin
from qolqe.dependencias import UsuarioActual, usuario_actual
from qolqe.errores import ErrorNegocio, conflicto, validacion
from qolqe.operaciones import notificar
from qolqe.reglas import nucleo
from qolqe.reglas.seguridad import INTENTOS_PARA_BLOQUEO, esta_bloqueado, fin_de_bloqueo

router = APIRouter(tags=["Autenticación"])


class SolicitudRegistro(BaseModel):
    dni: str = Field(examples=["45678912"])
    nombres: str = Field(min_length=2, max_length=80, examples=["Lucía Fernández Rojas"])
    celular: str = Field(examples=["987000111"])
    pin: str = Field(examples=["4826"])
    correo: str | None = Field(default=None, description="Opcional", examples=["lucia.fernandez@correo.pe"])


class UsuarioRegistrado(BaseModel):
    id: int
    nombres: str
    celular: str
    correo: str | None
    creado_en: str


class SolicitudLogin(BaseModel):
    celular: str = Field(examples=["987654321"])
    pin: str = Field(examples=["4826"])
    dispositivo_id: str | None = Field(default=None, description="Identificador de un dispositivo de confianza (opcional)")


class DatosUsuario(BaseModel):
    id: int
    nombres: str
    celular: str


class RespuestaLogin(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Segundos de vigencia del token")
    sesion_id: int
    usuario: DatosUsuario


@router.post("/api/usuarios", status_code=status.HTTP_201_CREATED, response_model=UsuarioRegistrado,
             summary="Registrar un nuevo usuario")
def registrar(datos: SolicitudRegistro, bd: sqlite3.Connection = Depends(obtener_bd)):
    for validar, valor, codigo in (
        (nucleo.validar_dni, datos.dni, "DNI_INVALIDO"),
        (nucleo.validar_celular, datos.celular, "CELULAR_INVALIDO"),
        (nucleo.validar_pin, datos.pin, "PIN_INVALIDO"),
    ):
        try:
            validar(valor)
        except ValueError as error:
            raise validacion(codigo, str(error))
    correo = None
    if datos.correo is not None and datos.correo.strip():
        try:
            correo = nucleo.validar_correo(datos.correo)
        except ValueError as error:
            raise validacion("CORREO_INVALIDO", str(error))

    if bd.execute("SELECT 1 FROM usuarios WHERE celular = ?", (datos.celular,)).fetchone():
        raise conflicto("CELULAR_REGISTRADO", "El celular ya está registrado")
    if correo and correo_en_uso(bd, correo):
        raise conflicto("CORREO_REGISTRADO", "El correo ya está registrado en otra cuenta")

    ahora = reloj.a_texto(reloj.ahora())
    pin_hash = hash_pin(datos.pin)
    cursor = bd.execute(
        "INSERT INTO usuarios (dni, nombres, celular, correo, pin_hash, creado_en) VALUES (?, ?, ?, ?, ?, ?)",
        (datos.dni, datos.nombres.strip(), datos.celular, correo, pin_hash, ahora),
    )
    usuario_id = cursor.lastrowid
    bd.execute("INSERT INTO cuentas (usuario_id, saldo_cent, actualizado_en) VALUES (?, 0, ?)", (usuario_id, ahora))
    bd.execute("INSERT INTO limites (usuario_id, limite_diario_cent) VALUES (?, ?)", (usuario_id, 200000))
    bd.execute("INSERT INTO historial_pin (usuario_id, pin_hash, creado_en) VALUES (?, ?, ?)", (usuario_id, pin_hash, ahora))
    notificar(bd, datos.celular, "Bienvenido a Qolqe. Tu cuenta fue creada con éxito.")
    return UsuarioRegistrado(id=usuario_id, nombres=datos.nombres.strip(), celular=datos.celular, correo=correo,
                             creado_en=ahora)


def correo_en_uso(bd: sqlite3.Connection, correo: str, excepto_usuario_id: int | None = None) -> bool:
    """El correo es único entre las cuentas activas, sin distinguir mayúsculas."""
    fila = bd.execute(
        "SELECT 1 FROM usuarios WHERE lower(correo) = lower(?) AND estado = 'ACTIVA' AND id != ?",
        (correo, excepto_usuario_id or 0),
    ).fetchone()
    return fila is not None


@router.post("/api/auth/login", response_model=RespuestaLogin, summary="Iniciar sesión y obtener un token JWT",
             responses={401: {"description": "Credenciales inválidas"}, 423: {"description": "Cuenta bloqueada"}})
def iniciar_sesion(datos: SolicitudLogin, bd: sqlite3.Connection = Depends(obtener_bd)):
    usuario = bd.execute("SELECT * FROM usuarios WHERE celular = ?", (datos.celular,)).fetchone()
    if usuario is None:
        raise ErrorNegocio(401, "CREDENCIALES_INVALIDAS", "Celular o PIN incorrectos")

    ahora = reloj.ahora()
    bloqueado_hasta = reloj.desde_texto(usuario["bloqueado_hasta"]) if usuario["bloqueado_hasta"] else None
    if esta_bloqueado(bloqueado_hasta, ahora):
        raise ErrorNegocio(423, "CUENTA_BLOQUEADA",
                           f"Tu cuenta está bloqueada hasta las {bloqueado_hasta:%H:%M}. Puedes solicitar un código de desbloqueo.")
    if bloqueado_hasta is not None:
        bd.execute("UPDATE usuarios SET bloqueado_hasta = NULL, intentos_fallidos = 0 WHERE id = ?", (usuario["id"],))

    if not verificar_pin(datos.pin, usuario["pin_hash"]):
        intentos = usuario["intentos_fallidos"] + 1 if bloqueado_hasta is None else 1
        if intentos >= INTENTOS_PARA_BLOQUEO:
            fin = fin_de_bloqueo(ahora)
            bd.execute("UPDATE usuarios SET intentos_fallidos = 0, bloqueado_hasta = ? WHERE id = ?",
                       (reloj.a_texto(fin), usuario["id"]))
            notificar(bd, usuario["celular"], f"Tu cuenta Qolqe fue bloqueada por intentos fallidos hasta las {fin:%H:%M}.")
            bd.commit()
            raise ErrorNegocio(423, "CUENTA_BLOQUEADA",
                               f"Superaste los intentos permitidos. Tu cuenta está bloqueada hasta las {fin:%H:%M}.")
        bd.execute("UPDATE usuarios SET intentos_fallidos = ? WHERE id = ?", (intentos, usuario["id"]))
        bd.commit()
        raise ErrorNegocio(401, "CREDENCIALES_INVALIDAS", "Celular o PIN incorrectos")

    if usuario["estado"] != "ACTIVA":
        raise ErrorNegocio(401, "CUENTA_CERRADA", "La cuenta fue cerrada")

    emitido = emitir_token(usuario["id"], usuario["celular"])
    sesion_id = bd.execute(
        "INSERT INTO sesiones (jti, usuario_id, dispositivo_id, iniciada_en, expira_en) VALUES (?, ?, ?, ?, ?)",
        (emitido.jti, usuario["id"], datos.dispositivo_id, reloj.a_texto(emitido.emitido), reloj.a_texto(emitido.expira)),
    ).lastrowid
    if datos.dispositivo_id:
        conocido = bd.execute(
            "UPDATE dispositivos SET ultimo_ingreso = ? WHERE id = ? AND usuario_id = ?",
            (reloj.a_texto(ahora), datos.dispositivo_id, usuario["id"]),
        ).rowcount
        if not conocido:
            notificar(bd, usuario["celular"],
                      f"Alerta Qolqe: se inició sesión en tu cuenta desde un nuevo dispositivo el {ahora:%d/%m a las %H:%M}. "
                      "Si no fuiste tú, cambia tu PIN.")
    return RespuestaLogin(
        access_token=emitido.token,
        expires_in=emitido.segundos,
        sesion_id=sesion_id,
        usuario=DatosUsuario(id=usuario["id"], nombres=usuario["nombres"], celular=usuario["celular"]),
    )


@router.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Cerrar sesión (revoca el token)")
def cerrar_sesion(usuario: UsuarioActual = Depends(usuario_actual), bd: sqlite3.Connection = Depends(obtener_bd)):
    bd.execute("INSERT OR IGNORE INTO tokens_revocados (jti, revocado_en) VALUES (?, ?)",
               (usuario.jti, reloj.a_texto(reloj.ahora())))
