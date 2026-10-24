"""Reglas del módulo de seguridad: PIN, desbloqueo y dispositivos (G6)."""
from datetime import datetime, timedelta

from qolqe.reglas.nucleo import validar_pin

INTENTOS_PARA_BLOQUEO = 3
MINUTOS_BLOQUEO = 15
PINES_ANTERIORES_A_REVISAR = 2
LONGITUD_CODIGO_DESBLOQUEO = 6
MINUTOS_VIGENCIA_CODIGO = 5
INTENTOS_CODIGO = 3


def validar_nuevo_pin(pin_nuevo: str, celular: str) -> None:
    """RN-03 y además no puede coincidir con los últimos 4 dígitos del celular."""
    validar_pin(pin_nuevo)
    if pin_nuevo == celular[-4:]:
        raise ValueError("El PIN no puede coincidir con los últimos 4 dígitos de tu celular")


def esta_bloqueado(bloqueado_hasta: datetime | None, ahora: datetime) -> bool:
    return bloqueado_hasta is not None and ahora < bloqueado_hasta


def fin_de_bloqueo(ahora: datetime) -> datetime:
    return ahora + timedelta(minutes=MINUTOS_BLOQUEO)


def codigo_vigente(expira_en: datetime, ahora: datetime) -> bool:
    return ahora < expira_en


MAX_DISPOSITIVOS = 3
LONGITUD_MINIMA_NOMBRE_DISPOSITIVO = 3
LONGITUD_MAXIMA_NOMBRE_DISPOSITIVO = 30
TIPOS_DISPOSITIVO = ("CELULAR", "TABLET", "COMPUTADORA")


def validar_dispositivo(nombre: str, tipo: str | None = None) -> str:
    normalizado = nombre.strip()
    if not LONGITUD_MINIMA_NOMBRE_DISPOSITIVO <= len(normalizado) <= LONGITUD_MAXIMA_NOMBRE_DISPOSITIVO:
        raise ValueError("El nombre del dispositivo debe tener entre 3 y 30 caracteres")
    if tipo is not None and tipo not in TIPOS_DISPOSITIVO:
        raise ValueError(f"Tipo de dispositivo no válido. Valores: {', '.join(TIPOS_DISPOSITIVO)}")
    return normalizado
