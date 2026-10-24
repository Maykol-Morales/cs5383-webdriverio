"""Reglas del módulo de historial y filtros de movimientos (G3)."""
from datetime import date

MOVIMIENTOS_POR_PAGINA = 10
RANGO_MAXIMO_DIAS = 90
TIPOS_MOVIMIENTO = ("TRANSFERENCIA_ENVIADA", "TRANSFERENCIA_RECIBIDA", "RECARGA", "PAGO_SERVICIO")


def validar_filtro(desde: date, hasta: date, pagina: int, hoy: date, tipo: str | None = None) -> None:
    if desde > hasta:
        raise ValueError("La fecha 'desde' no puede ser posterior a 'hasta'")
    if (hasta - desde).days > RANGO_MAXIMO_DIAS:
        raise ValueError("El rango máximo de consulta es de 90 días")
    if hasta > hoy:
        raise ValueError("La fecha 'hasta' no puede ser futura")
    if pagina < 1:
        raise ValueError("La página debe ser mayor o igual a 1")
    if tipo is not None and tipo not in TIPOS_MOVIMIENTO:
        raise ValueError(f"Tipo de movimiento no válido. Valores: {', '.join(TIPOS_MOVIMIENTO)}")


def total_paginas(total_movimientos: int) -> int:
    return max(1, -(-total_movimientos // MOVIMIENTOS_POR_PAGINA))


MAX_CATEGORIAS = 10
LONGITUD_MINIMA_CATEGORIA = 3
LONGITUD_MAXIMA_CATEGORIA = 20
LONGITUD_MAXIMA_NOTA = 100
PALETA_COLORES = ("#E53935", "#FB8C00", "#FDD835", "#43A047", "#00897B", "#1E88E5", "#8E24AA", "#6D4C41")


class CategoriaDuplicada(ValueError):
    pass


def validar_nombre_categoria(nombre: str) -> str:
    normalizado = nombre.strip()
    if not LONGITUD_MINIMA_CATEGORIA <= len(normalizado) <= LONGITUD_MAXIMA_CATEGORIA:
        raise ValueError("El nombre de la categoría debe tener entre 3 y 20 caracteres")
    return normalizado


def validar_color(color: str) -> str:
    normalizado = color.strip().upper()
    if normalizado not in PALETA_COLORES:
        raise ValueError(f"Color no permitido. Colores válidos: {', '.join(PALETA_COLORES)}")
    return normalizado


def verificar_nombre_disponible(nombre: str, nombres_existentes: list[str]) -> None:
    if nombre.lower() in {n.lower() for n in nombres_existentes}:
        raise CategoriaDuplicada("Ya tienes una categoría con ese nombre")


def validar_nota(nota: str | None) -> str | None:
    if nota is None:
        return None
    normalizado = nota.strip()
    if len(normalizado) > LONGITUD_MAXIMA_NOTA:
        raise ValueError("La nota admite como máximo 100 caracteres")
    return normalizado or None
