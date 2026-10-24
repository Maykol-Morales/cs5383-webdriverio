"""Conversión entre soles (Decimal) y céntimos (int).

Los montos se guardan en céntimos para evitar errores de redondeo de punto flotante.
"""
from decimal import Decimal

CENTIMO = Decimal("0.01")


def a_centimos(monto: Decimal) -> int:
    return int((monto * 100).to_integral_value())


def a_soles(centimos: int) -> Decimal:
    return (Decimal(centimos) / 100).quantize(CENTIMO)


def formato(centimos: int) -> str:
    return str(a_soles(centimos))
