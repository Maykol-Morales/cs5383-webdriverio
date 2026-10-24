"""Reglas del módulo de pago de servicios (G2)."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

LONGITUD_MINIMA_SUMINISTRO = 8
LONGITUD_MAXIMA_SUMINISTRO = 12
TASA_MORA_DIARIA = Decimal("0.005")
TOPE_MORA = Decimal("0.10")
DIAS_MAXIMOS_ATRASO = 60


class DeudaEnCobranza(ValueError):
    pass


def validar_suministro(suministro: str) -> None:
    if not (suministro.isascii() and suministro.isdigit()):
        raise ValueError("El código de suministro solo admite dígitos")
    if not LONGITUD_MINIMA_SUMINISTRO <= len(suministro) <= LONGITUD_MAXIMA_SUMINISTRO + 1:
        raise ValueError("El código de suministro debe tener entre 8 y 12 dígitos")


def dias_de_atraso(vencimiento: date, fecha_pago: date) -> int:
    if fecha_pago < vencimiento:
        return 0
    return (fecha_pago - vencimiento).days + 1


def calcular_mora(monto: Decimal, vencimiento: date, fecha_pago: date) -> Decimal:
    """0.5 % diario por atraso, con tope de 10 %. Con más de 60 días la deuda pasa a cobranza."""
    dias = dias_de_atraso(vencimiento, fecha_pago)
    if dias > DIAS_MAXIMOS_ATRASO:
        raise DeudaEnCobranza("Deuda enviada a cobranza")
    mora = monto * TASA_MORA_DIARIA * dias
    mora = min(mora, monto * TOPE_MORA)
    return mora.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


MAX_AFILIACIONES = 8
LONGITUD_MINIMA_ALIAS = 3
LONGITUD_MAXIMA_ALIAS = 20


def validar_alias_afiliacion(alias: str) -> str:
    normalizado = alias.strip()
    if not LONGITUD_MINIMA_ALIAS <= len(normalizado) <= LONGITUD_MAXIMA_ALIAS:
        raise ValueError("El alias debe tener entre 3 y 20 caracteres")
    return normalizado


def situacion_afiliacion(deudas_pendientes: int, deudas_en_cobranza: int) -> str:
    if deudas_en_cobranza:
        return "EN_COBRANZA"
    if deudas_pendientes:
        return "CON_DEUDA"
    return "AL_DIA"
