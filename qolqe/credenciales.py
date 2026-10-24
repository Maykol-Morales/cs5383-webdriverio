"""Hash de PIN y emisión/validación de tokens JWT."""
import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

import jwt

from qolqe import config, reloj

ITERACIONES_PBKDF2 = 200_000


def hash_pin(pin: str, sal: bytes | None = None) -> str:
    sal = sal or secrets.token_bytes(16)
    derivado = hashlib.pbkdf2_hmac("sha256", pin.encode(), sal, ITERACIONES_PBKDF2)
    return f"pbkdf2_sha256${ITERACIONES_PBKDF2}${sal.hex()}${derivado.hex()}"


def verificar_pin(pin: str, pin_hash: str) -> bool:
    _, iteraciones, sal_hex, esperado = pin_hash.split("$")
    derivado = hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(sal_hex), int(iteraciones))
    return hmac.compare_digest(derivado.hex(), esperado)


@dataclass
class TokenEmitido:
    token: str
    jti: str
    emitido: datetime
    expira: datetime
    segundos: int


def emitir_token(usuario_id: int, celular: str) -> TokenEmitido:
    emitido = reloj.ahora()
    duracion = timedelta(minutes=config.MINUTOS_TOKEN)
    jti = uuid.uuid4().hex
    contenido = {
        "sub": str(usuario_id),
        "cel": celular,
        "jti": jti,
        "iat": int(emitido.timestamp()),
        "exp": int((emitido + duracion).timestamp()),
    }
    token = jwt.encode(contenido, config.CLAVE_SECRETA, algorithm=config.ALGORITMO_JWT)
    return TokenEmitido(token, jti, emitido, emitido + duracion, int(duracion.total_seconds()))


def decodificar_token(token: str) -> dict:
    """Valida firma y expiración usando el reloj de la aplicación."""
    contenido = jwt.decode(
        token,
        config.CLAVE_SECRETA,
        algorithms=[config.ALGORITMO_JWT],
        options={"verify_exp": False, "verify_iat": False, "require": ["sub", "jti", "exp"]},
    )
    if reloj.ahora().timestamp() >= contenido["exp"]:
        raise jwt.ExpiredSignatureError("El token expiró")
    return contenido
