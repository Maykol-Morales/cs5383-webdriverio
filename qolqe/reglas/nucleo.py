"""Reglas del núcleo: registro, credenciales, montos y comisiones (RN-01 a RN-09)."""
import re
from decimal import Decimal

LIMITE_POR_OPERACION = Decimal("500.00")
LIMITE_DIARIO_POR_DEFECTO = Decimal("2000.00")
TASA_INTERBANCARIA = Decimal("0.015")
COMISION_MINIMA = Decimal("1.00")
COMISION_MAXIMA = Decimal("5.00")
SECUENCIA_DIGITOS = "0123456789"


def _solo_digitos(texto: str) -> bool:
    return texto.isascii() and texto.isdigit()


def validar_dni(dni: str) -> None:
    """RN-01: el DNI tiene exactamente 8 dígitos."""
    if len(dni) != 8 or not _solo_digitos(dni):
        raise ValueError("El DNI debe tener exactamente 8 dígitos")


def validar_celular(celular: str) -> None:
    """RN-02: 9 dígitos y empieza con 9."""
    if len(celular) != 9 or not _solo_digitos(celular) or not celular.startswith("9"):
        raise ValueError("El celular debe tener 9 dígitos y empezar con 9")


def validar_pin(pin: str) -> None:
    """RN-03: 4 dígitos, no todos iguales y no secuencial."""
    if len(pin) != 4 or not _solo_digitos(pin):
        raise ValueError("El PIN debe tener 4 dígitos")
    if len(set(pin)) == 1:
        raise ValueError("El PIN no puede tener todos los dígitos iguales")
    if pin in SECUENCIA_DIGITOS:
        raise ValueError("El PIN no puede ser una secuencia de dígitos")


def validar_monto(monto: Decimal) -> None:
    """RN-05: mayor a cero, como máximo 2 decimales y no mayor al límite por operación."""
    if monto <= 0:
        raise ValueError("El monto debe ser mayor a cero")
    if monto.as_tuple().exponent < -2:
        raise ValueError("El monto admite como máximo 2 decimales")
    if monto > LIMITE_POR_OPERACION:
        raise ValueError("El monto supera el límite por operación de S/ 500.00")


def validar_cci(cci: str) -> None:
    """El Código de Cuenta Interbancario tiene 20 dígitos."""
    if len(cci) != 20 or not _solo_digitos(cci):
        raise ValueError("El CCI debe tener 20 dígitos")


def calcular_comision(monto: Decimal, mismo_banco: bool) -> Decimal:
    """RN-09: sin comisión entre cuentas Qolqe; 1.5 % a otros bancos (mín. S/ 1.00, máx. S/ 5.00)."""
    if mismo_banco:
        return Decimal("0.00")
    comision = (monto * TASA_INTERBANCARIA).quantize(Decimal("0.01"))
    return min(max(comision, COMISION_MINIMA), COMISION_MAXIMA)


PATRON_CORREO = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")
LONGITUD_MINIMA_NOMBRES = 2
LONGITUD_MAXIMA_NOMBRES = 80


def validar_nombres(nombres: str) -> str:
    """Nombres de 2 a 80 caracteres (sin contar espacios al inicio ni al final)."""
    normalizado = nombres.strip()
    if not LONGITUD_MINIMA_NOMBRES <= len(normalizado) <= LONGITUD_MAXIMA_NOMBRES:
        raise ValueError("Los nombres deben tener entre 2 y 80 caracteres")
    return normalizado


def validar_correo(correo: str) -> str:
    """Formato usuario@dominio.ext. Se guarda en minúsculas."""
    normalizado = correo.strip()
    if len(normalizado) > 100 or not PATRON_CORREO.match(normalizado):
        raise ValueError("El correo no tiene un formato válido")
    return normalizado.lower()
