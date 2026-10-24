"""Operaciones comunes sobre cuentas, movimientos, límites y notificaciones."""
import random
import sqlite3
import time
from datetime import datetime, timedelta
from decimal import Decimal

from qolqe import reloj
from qolqe.dinero import a_centimos, a_soles
from qolqe.reglas.limites import EstadoLimite, limite_vigente


def generar_codigo_operacion(prefijo: str, usuario_id: int, momento: datetime) -> str:
    """Código legible para el cliente: prefijo + fecha y hora + usuario."""
    return f"{prefijo}{momento:%y%m%d%H%M%S}{usuario_id:05d}"


def saldo_centimos(bd: sqlite3.Connection, usuario_id: int) -> int:
    return bd.execute("SELECT saldo_cent FROM cuentas WHERE usuario_id = ?", (usuario_id,)).fetchone()["saldo_cent"]


def mover_saldo(bd: sqlite3.Connection, usuario_id: int, importe_cent: int, momento: datetime) -> None:
    bd.execute(
        "UPDATE cuentas SET saldo_cent = saldo_cent + ?, actualizado_en = ? WHERE usuario_id = ?",
        (importe_cent, reloj.a_texto(momento), usuario_id),
    )


def registrar_movimiento(
    bd: sqlite3.Connection,
    usuario_id: int,
    codigo: str,
    tipo: str,
    descripcion: str,
    monto_cent: int,
    importe_cent: int,
    momento: datetime,
    comision_cent: int = 0,
    contraparte: str | None = None,
) -> None:
    bd.execute(
        """INSERT INTO movimientos
           (usuario_id, codigo_operacion, tipo, descripcion, contraparte, monto_cent, comision_cent, importe_cent, fecha)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (usuario_id, codigo, tipo, descripcion, contraparte, monto_cent, comision_cent, importe_cent, reloj.a_texto(momento)),
    )


def notificar(bd: sqlite3.Connection, celular: str, mensaje: str) -> None:
    """Envía un SMS simulado (queda en la bandeja de notificaciones)."""
    bd.execute(
        "INSERT INTO notificaciones (celular, mensaje, fecha) VALUES (?, ?, ?)",
        (celular, mensaje, reloj.a_texto(reloj.ahora())),
    )


def inicio_del_dia(momento: datetime) -> str:
    return reloj.a_texto(momento.replace(hour=0, minute=0, second=0))


def transferido_hoy_centimos(bd: sqlite3.Connection, usuario_id: int, momento: datetime) -> int:
    fila = bd.execute(
        """SELECT COALESCE(SUM(monto_cent), 0) AS total FROM transferencias
           WHERE origen_id = ? AND fecha >= ? AND tipo = 'QOLQE'""",
        (usuario_id, inicio_del_dia(momento)),
    ).fetchone()
    return fila["total"]


def estado_limite(bd: sqlite3.Connection, usuario_id: int) -> EstadoLimite:
    fila = bd.execute("SELECT * FROM limites WHERE usuario_id = ?", (usuario_id,)).fetchone()
    return EstadoLimite(
        limite_diario=a_soles(fila["limite_diario_cent"]),
        limite_pendiente=a_soles(fila["limite_pendiente_cent"]) if fila["limite_pendiente_cent"] is not None else None,
        pendiente_desde=reloj.desde_texto(fila["pendiente_desde"]) if fila["pendiente_desde"] else None,
    )


def guardar_estado_limite(bd: sqlite3.Connection, usuario_id: int, estado: EstadoLimite) -> None:
    bd.execute(
        "UPDATE limites SET limite_diario_cent = ?, limite_pendiente_cent = ?, pendiente_desde = ? WHERE usuario_id = ?",
        (
            a_centimos(estado.limite_diario),
            a_centimos(estado.limite_pendiente) if estado.limite_pendiente is not None else None,
            reloj.a_texto(estado.pendiente_desde) if estado.pendiente_desde else None,
            usuario_id,
        ),
    )


def limite_diario_vigente(bd: sqlite3.Connection, usuario_id: int) -> EstadoLimite:
    estado = estado_limite(bd, usuario_id)
    vigente = limite_vigente(estado, reloj.ahora())
    if vigente != estado:
        guardar_estado_limite(bd, usuario_id, vigente)
    return vigente


def evaluar_antifraude(usuario_id: int, monto: Decimal, destino: str) -> bool:
    """Consulta al motor antifraude (simulado: responde entre 40 y 120 ms y aprueba la operación)."""
    time.sleep(random.uniform(0.04, 0.12))
    return True


def enmascarar_nombre(nombres: str) -> str:
    partes = nombres.split()
    if len(partes) == 1:
        return partes[0]
    return f"{partes[0]} {partes[1][0]}."


def enmascarar(texto: str, visibles: int = 4) -> str:
    return "*" * (len(texto) - visibles) + texto[-visibles:]


def fecha_iso(momento: datetime) -> str:
    return reloj.a_texto(momento)


def mas_horas(momento: datetime, horas: int) -> datetime:
    return momento + timedelta(hours=horas)
