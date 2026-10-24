"""Reglas del módulo de configuración de límites (G5)."""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal

LIMITE_DIARIO_MINIMO = Decimal("100")
LIMITE_DIARIO_MAXIMO = Decimal("2000")
MULTIPLO_LIMITE = Decimal("50")
HORAS_PARA_AUMENTO = 24


@dataclass(frozen=True)
class EstadoLimite:
    limite_diario: Decimal
    limite_pendiente: Decimal | None = None
    pendiente_desde: datetime | None = None


def validar_nuevo_limite(limite: Decimal) -> None:
    if not LIMITE_DIARIO_MINIMO <= limite <= LIMITE_DIARIO_MAXIMO:
        raise ValueError("El límite diario debe estar entre S/ 100 y S/ 2,000")
    if limite % MULTIPLO_LIMITE != 0:
        raise ValueError("El límite diario debe ser múltiplo de S/ 50")


def limite_vigente(estado: EstadoLimite, ahora: datetime) -> EstadoLimite:
    """Aplica el aumento pendiente si ya se cumplió el plazo."""
    if estado.limite_pendiente is not None and estado.pendiente_desde is not None and ahora >= estado.pendiente_desde:
        return EstadoLimite(limite_diario=estado.limite_pendiente)
    return estado


def solicitar_cambio(estado: EstadoLimite, solicitado: Decimal, ahora: datetime) -> EstadoLimite:
    """Una reducción es inmediata; un aumento entra en vigencia 24 horas después."""
    validar_nuevo_limite(solicitado)
    actual = limite_vigente(estado, ahora)
    if solicitado <= actual.limite_diario:
        return replace(actual, limite_diario=solicitado)
    return EstadoLimite(
        limite_diario=actual.limite_diario,
        limite_pendiente=solicitado,
        pendiente_desde=ahora + timedelta(hours=HORAS_PARA_AUMENTO),
    )


MAX_ALERTAS = 5
UMBRAL_MINIMO = Decimal("10")
UMBRAL_MAXIMO = Decimal("2000")
MULTIPLO_UMBRAL = Decimal("10")
TIPOS_ALERTA = ("TRANSFERENCIAS", "RECARGAS", "PAGOS", "TODAS")
TIPOS_SUJETOS_AL_LIMITE = ("TRANSFERENCIAS", "TODAS")


def validar_alerta(tipo: str, umbral: Decimal, limite_vigente_diario: Decimal) -> None:
    if tipo not in TIPOS_ALERTA:
        raise ValueError(f"Tipo de alerta no válido. Valores: {', '.join(TIPOS_ALERTA)}")
    if not UMBRAL_MINIMO <= umbral <= UMBRAL_MAXIMO:
        raise ValueError("El umbral debe estar entre S/ 10 y S/ 2,000")
    if umbral % MULTIPLO_UMBRAL != 0:
        raise ValueError("El umbral debe ser múltiplo de S/ 10")
    validar_umbral_frente_al_limite(tipo, umbral, limite_vigente_diario)


def validar_umbral_frente_al_limite(tipo: str, umbral: Decimal, limite_vigente_diario: Decimal) -> None:
    if tipo in TIPOS_SUJETOS_AL_LIMITE and umbral > limite_vigente_diario:
        raise ValueError(f"El umbral no puede superar tu límite diario vigente de S/ {limite_vigente_diario}")


def tipos_afectados(tipo_operacion: str) -> tuple[str, str]:
    """Una operación de un tipo afecta a las alertas de ese tipo y a las de tipo TODAS."""
    return tipo_operacion, "TODAS"
