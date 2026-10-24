"""Dependencias compartidas por los endpoints: usuario autenticado y conexión a BD."""
import sqlite3
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from qolqe.bd import obtener_bd
from qolqe.credenciales import decodificar_token

esquema_bearer = HTTPBearer(auto_error=False, description="Token JWT obtenido en /api/auth/login")


@dataclass
class UsuarioActual:
    id: int
    celular: str
    nombres: str
    jti: str
    exp: int
    sesion_id: int


def _no_autenticado(mensaje: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"codigo": "NO_AUTENTICADO", "detail": mensaje},
        headers={"WWW-Authenticate": "Bearer"},
    )


def usuario_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(esquema_bearer),
    bd: sqlite3.Connection = Depends(obtener_bd),
) -> UsuarioActual:
    if credenciales is None:
        raise _no_autenticado("Falta el token de autenticación")
    try:
        contenido = decodificar_token(credenciales.credentials)
    except jwt.ExpiredSignatureError:
        raise _no_autenticado("El token expiró")
    except jwt.PyJWTError:
        raise _no_autenticado("Token inválido")

    revocado = bd.execute(
        "SELECT 1 FROM tokens_revocados WHERE jti = ?", (credenciales.credentials,)
    ).fetchone()
    if revocado:
        raise _no_autenticado("La sesión fue cerrada")

    sesion = bd.execute(
        "SELECT id FROM sesiones WHERE jti = ? AND usuario_id = ? AND cerrada_en IS NULL",
        (contenido["jti"], int(contenido["sub"])),
    ).fetchone()
    if sesion is None:
        raise _no_autenticado("La sesión fue cerrada")

    fila = bd.execute(
        "SELECT id, celular, nombres, estado FROM usuarios WHERE id = ?", (int(contenido["sub"]),)
    ).fetchone()
    if fila is None or fila["estado"] != "ACTIVA":
        raise _no_autenticado("Usuario no encontrado")
    return UsuarioActual(fila["id"], fila["celular"], fila["nombres"], contenido["jti"], contenido["exp"], sesion["id"])
