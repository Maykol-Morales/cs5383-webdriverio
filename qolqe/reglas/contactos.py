"""Reglas del módulo de contactos y solicitudes de dinero (G4)."""
import re
import unicodedata
from datetime import datetime, timedelta

MAX_CONTACTOS = 15
LONGITUD_MINIMA_ALIAS = 3
LONGITUD_MAXIMA_ALIAS = 20
PATRON_ALIAS = re.compile(r"^[A-Za-zÁÉÍÓÚÜáéíóúü0-9 ]+$")


class AliasDuplicado(ValueError):
    pass


class LimiteContactos(ValueError):
    pass


def validar_alias(alias: str, alias_existentes: list[str]) -> str:
    """Valida el alias y devuelve su versión normalizada (sin espacios al inicio ni al final)."""
    if len(alias_existentes) >= MAX_CONTACTOS:
        raise LimiteContactos(f"Solo se permiten {MAX_CONTACTOS} contactos")
    if alias.lower() in {a.lower() for a in alias_existentes}:
        raise AliasDuplicado("Ya tienes un contacto con ese alias")
    normalizado = alias.strip()
    if not LONGITUD_MINIMA_ALIAS <= len(normalizado) <= LONGITUD_MAXIMA_ALIAS:
        raise ValueError("El alias debe tener entre 3 y 20 caracteres")
    if not PATRON_ALIAS.match(normalizado):
        raise ValueError("El alias solo admite letras, números y espacios")
    return normalizado


def validar_cambio_alias(alias: str, alias_otros_contactos: list[str]) -> str:
    """Igual que validar_alias, pero sin contar el contacto que se está editando."""
    if alias.lower() in {a.lower() for a in alias_otros_contactos}:
        raise AliasDuplicado("Ya tienes un contacto con ese alias")
    normalizado = alias.strip()
    if not LONGITUD_MINIMA_ALIAS <= len(normalizado) <= LONGITUD_MAXIMA_ALIAS:
        raise ValueError("El alias debe tener entre 3 y 20 caracteres")
    if not PATRON_ALIAS.match(normalizado):
        raise ValueError("El alias solo admite letras, números y espacios")
    return normalizado


MAX_FAVORITOS = 5
MAX_SOLICITUDES_PENDIENTES = 10
HORAS_VIGENCIA_SOLICITUD = 48
LONGITUD_MINIMA_MOTIVO = 3
LONGITUD_MAXIMA_MOTIVO = 60
ESTADOS_SOLICITUD = ("PENDIENTE", "ACEPTADA", "RECHAZADA", "CANCELADA", "VENCIDA")


def sin_tildes(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn").lower()


def coincide_busqueda(alias: str, busqueda: str) -> bool:
    return sin_tildes(busqueda.strip()) in sin_tildes(alias)


def validar_motivo(motivo: str) -> str:
    normalizado = motivo.strip()
    if not LONGITUD_MINIMA_MOTIVO <= len(normalizado) <= LONGITUD_MAXIMA_MOTIVO:
        raise ValueError("El motivo debe tener entre 3 y 60 caracteres")
    return normalizado


def estado_solicitud(estado_guardado: str, vence_en: datetime, ahora: datetime) -> str:
    """Una solicitud PENDIENTE cuyo plazo ya pasó se considera VENCIDA."""
    if estado_guardado == "PENDIENTE" and ahora >= vence_en:
        return "VENCIDA"
    return estado_guardado


def vencimiento_solicitud(creada_en: datetime) -> datetime:
    return creada_en + timedelta(hours=HORAS_VIGENCIA_SOLICITUD)
