"""Reloj de la aplicación (hora de Lima, UTC-5).

En modo prueba el reloj puede adelantarse o fijarse mediante la API de soporte,
lo que permite probar reglas que dependen del tiempo (bloqueos, vencimientos, límites).
"""
from datetime import date, datetime, timedelta, timezone

ZONA_LIMA = timezone(timedelta(hours=-5), "America/Lima")

_desfase = timedelta(0)


def ahora() -> datetime:
    return (datetime.now(ZONA_LIMA) + _desfase).replace(microsecond=0)


def hoy() -> date:
    return ahora().date()


def fijar(momento: datetime) -> None:
    global _desfase
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=ZONA_LIMA)
    _desfase = momento - datetime.now(ZONA_LIMA)


def avanzar(minutos: int) -> None:
    global _desfase
    _desfase += timedelta(minutes=minutos)


def restablecer() -> None:
    global _desfase
    _desfase = timedelta(0)


def esta_desfasado() -> bool:
    return _desfase != timedelta(0)


def a_texto(momento: datetime) -> str:
    """Formato de almacenamiento: ISO 8601 sin zona (hora local de Lima)."""
    return momento.strftime("%Y-%m-%dT%H:%M:%S")


def desde_texto(texto: str) -> datetime:
    return datetime.strptime(texto, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=ZONA_LIMA)
