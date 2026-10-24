"""Reglas del módulo de recargas de celular (G1)."""
from datetime import date
from decimal import Decimal

MONTOS_PERMITIDOS = (Decimal("5"), Decimal("10"), Decimal("20"), Decimal("30"), Decimal("50"), Decimal("100"))
MONTO_MINIMO_BONO = Decimal("30")
PORCENTAJE_BONO = Decimal("0.05")
TOPE_BONO = Decimal("4.00")
MAX_RECARGAS_DIARIAS_MISMO_NUMERO = 5


def validar_monto_recarga(monto: Decimal) -> None:
    if monto not in MONTOS_PERMITIDOS:
        permitidos = ", ".join(str(m) for m in MONTOS_PERMITIDOS)
        raise ValueError(f"Monto no permitido. Montos válidos: S/ {permitidos}")


def calcular_bono(monto: Decimal) -> Decimal:
    """Bono de 5 % para recargas desde S/ 30, con tope de S/ 4.00."""
    validar_monto_recarga(monto)
    if monto > MONTO_MINIMO_BONO:
        bono = (monto * PORCENTAJE_BONO).quantize(Decimal("0.01"))
        return min(bono, TOPE_BONO)
    return Decimal("0.00")


def puede_recargar(recargas_hoy_mismo_numero: int) -> bool:
    """Máximo de recargas diarias al mismo número."""
    return not recargas_hoy_mismo_numero > MAX_RECARGAS_DIARIAS_MISMO_NUMERO


MAX_PROGRAMADAS_ACTIVAS = 3
DIA_MINIMO = 1
DIA_MAXIMO = 28
LONGITUD_MAXIMA_ALIAS_PROGRAMADA = 20


def validar_dia(dia: int) -> None:
    if not DIA_MINIMO <= dia <= DIA_MAXIMO:
        raise ValueError("El día de ejecución debe estar entre 1 y 28")


def validar_alias_programada(alias: str | None) -> str | None:
    if alias is None:
        return None
    normalizado = alias.strip()
    if len(normalizado) > LONGITUD_MAXIMA_ALIAS_PROGRAMADA:
        raise ValueError("El alias admite como máximo 20 caracteres")
    return normalizado or None


def proxima_ejecucion(dia: int, hoy: date) -> date:
    """Siguiente fecha con ese día: este mes si aún no pasó; si ya pasó o es hoy, el mes siguiente."""
    if dia > hoy.day:
        return hoy.replace(day=dia)
    if hoy.month == 12:
        return date(hoy.year + 1, 1, dia)
    return date(hoy.year, hoy.month + 1, dia)
