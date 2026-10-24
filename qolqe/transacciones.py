"""Operaciones financieras compartidas por la API y los procesos automáticos.

Transferencias, recargas y pagos de servicios se realizan siempre con estas funciones,
ya sea que las inicie el cliente (API) o el sistema (proceso diario, solicitudes aceptadas).
"""
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from qolqe import reloj
from qolqe.dinero import a_centimos, a_soles, formato
from qolqe.errores import ErrorNegocio, conflicto, validacion
from qolqe.operaciones import (
    enmascarar,
    enmascarar_nombre,
    evaluar_antifraude,
    generar_codigo_operacion,
    inicio_del_dia,
    limite_diario_vigente,
    mover_saldo,
    notificar,
    registrar_movimiento,
    saldo_centimos,
    transferido_hoy_centimos,
)
from qolqe.reglas import nucleo
from qolqe.reglas import recargas as reglas_recargas
from qolqe.reglas import servicios as reglas_servicios
from qolqe.reglas.limites import tipos_afectados


@dataclass
class Titular:
    """Datos mínimos del usuario que realiza la operación."""
    id: int
    celular: str
    nombres: str


# ---------------------------------------------------------------- transferencias

def realizar_transferencia(
    bd: sqlite3.Connection,
    origen: Titular,
    monto: Decimal,
    destino: sqlite3.Row | None = None,
    cci: str | None = None,
    descripcion: str | None = None,
) -> dict:
    """Transfiere a otro usuario Qolqe (destino) o a otro banco (cci). Devuelve el comprobante."""
    try:
        nucleo.validar_monto(monto)
    except ValueError as error:
        raise validacion("MONTO_INVALIDO", str(error))

    es_qolqe = destino is not None
    tipo = "QOLQE" if es_qolqe else "INTERBANCARIA"
    monto_cent = a_centimos(monto)
    comision_cent = a_centimos(nucleo.calcular_comision(monto, mismo_banco=es_qolqe))

    if saldo_centimos(bd, origen.id) < monto_cent:
        raise validacion("SALDO_INSUFICIENTE", "Saldo insuficiente para realizar la operación")

    momento = reloj.ahora()
    limite = limite_diario_vigente(bd, origen.id).limite_diario
    if transferido_hoy_centimos(bd, origen.id, momento) + monto_cent > a_centimos(limite):
        raise validacion("LIMITE_DIARIO_EXCEDIDO", f"La operación supera tu límite diario de S/ {limite}")

    referencia_destino = destino["celular"] if es_qolqe else cci
    if not evaluar_antifraude(origen.id, monto, referencia_destino):
        raise ErrorNegocio(403, "OPERACION_RECHAZADA", "La operación fue rechazada por seguridad")

    codigo = generar_codigo_operacion("TRF", origen.id, momento)
    total_cent = monto_cent + comision_cent
    mover_saldo(bd, origen.id, -total_cent, momento)
    bd.execute(
        """INSERT INTO transferencias (codigo_operacion, origen_id, destino_id, cci_destino, tipo, monto_cent,
                                       comision_cent, descripcion, fecha)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (codigo, origen.id, destino["id"] if es_qolqe else None, None if es_qolqe else cci,
         tipo, monto_cent, comision_cent, descripcion, reloj.a_texto(momento)),
    )

    if es_qolqe:
        nombre_destino = enmascarar_nombre(destino["nombres"])
        registrar_movimiento(bd, origen.id, codigo, "TRANSFERENCIA_ENVIADA",
                             descripcion or f"Transferencia a {nombre_destino}",
                             monto_cent, -total_cent, momento, comision_cent, destino["celular"])
        mover_saldo(bd, destino["id"], monto_cent, momento)
        registrar_movimiento(bd, destino["id"], codigo, "TRANSFERENCIA_RECIBIDA",
                             descripcion or f"Transferencia de {enmascarar_nombre(origen.nombres)}",
                             monto_cent, monto_cent, momento, 0, origen.celular)
        notificar(bd, destino["celular"],
                  f"Recibiste S/ {formato(monto_cent)} de {enmascarar_nombre(origen.nombres)}. Operación {codigo}.")
        destinatario = {"nombre": nombre_destino, "celular": destino["celular"], "cci": None}
    else:
        registrar_movimiento(bd, origen.id, codigo, "TRANSFERENCIA_ENVIADA",
                             descripcion or f"Transferencia interbancaria a CCI {enmascarar(cci)}",
                             monto_cent, -total_cent, momento, comision_cent, enmascarar(cci))
        destinatario = {"nombre": None, "celular": None, "cci": enmascarar(cci)}

    evaluar_alertas(bd, origen.id, origen.celular, "TRANSFERENCIAS")
    return {
        "codigo_operacion": codigo,
        "tipo": tipo,
        "monto": formato(monto_cent),
        "comision": formato(comision_cent),
        "total": formato(total_cent),
        "destinatario": destinatario,
        "saldo": formato(saldo_centimos(bd, origen.id)),
        "fecha": reloj.a_texto(momento),
    }


# ---------------------------------------------------------------- recargas

def realizar_recarga(
    bd: sqlite3.Connection,
    titular: Titular,
    celular: str,
    monto: Decimal,
    origen: str = "MANUAL",
    programada_id: int | None = None,
) -> dict:
    """Recarga un celular. origen: MANUAL (cliente) o PROGRAMADA (proceso diario)."""
    try:
        nucleo.validar_celular(celular)
    except ValueError as error:
        raise validacion("CELULAR_INVALIDO", str(error))
    try:
        bono = reglas_recargas.calcular_bono(monto)
    except ValueError as error:
        raise validacion("MONTO_NO_PERMITIDO", str(error))

    momento = reloj.ahora()
    recargas_hoy = bd.execute(
        "SELECT COUNT(*) FROM recargas WHERE usuario_id = ? AND celular = ? AND fecha >= ?",
        (titular.id, celular, inicio_del_dia(momento)),
    ).fetchone()[0]
    if not reglas_recargas.puede_recargar(recargas_hoy):
        raise validacion("LIMITE_RECARGAS", "Alcanzaste el máximo de recargas diarias a este número")

    monto_cent = a_centimos(monto)
    if saldo_centimos(bd, titular.id) < monto_cent:
        raise validacion("SALDO_INSUFICIENTE", "Saldo insuficiente para realizar la recarga")

    codigo = generar_codigo_operacion("REC", titular.id, momento)
    bono_cent = a_centimos(bono)
    mover_saldo(bd, titular.id, -monto_cent, momento)
    bd.execute(
        """INSERT INTO recargas (codigo_operacion, usuario_id, celular, monto_cent, bono_cent, fecha, origen, programada_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (codigo, titular.id, celular, monto_cent, bono_cent, reloj.a_texto(momento), origen, programada_id),
    )
    descripcion = f"Recarga {'programada ' if origen == 'PROGRAMADA' else ''}al {celular}"
    registrar_movimiento(bd, titular.id, codigo, "RECARGA", descripcion, monto_cent, -monto_cent, momento, 0, celular)
    mensaje = f"Recibiste una recarga de S/ {formato(monto_cent)}"
    if bono_cent:
        mensaje += f" + bono de S/ {formato(bono_cent)}"
    notificar(bd, celular, mensaje + ".")
    evaluar_alertas(bd, titular.id, titular.celular, "RECARGAS")
    return {
        "codigo_operacion": codigo,
        "celular": celular,
        "monto": formato(monto_cent),
        "bono": formato(bono_cent),
        "origen": origen,
        "saldo": formato(saldo_centimos(bd, titular.id)),
        "fecha": reloj.a_texto(momento),
    }


# ---------------------------------------------------------------- pagos de servicios

def realizar_pago(
    bd: sqlite3.Connection,
    titular: Titular,
    deuda: sqlite3.Row,
    origen: str = "MANUAL",
) -> dict:
    """Paga una deuda pendiente. origen: MANUAL (cliente) o DEBITO_AUTOMATICO (proceso diario, sin mora)."""
    if deuda["estado"] != "PENDIENTE":
        raise conflicto("DEUDA_YA_PAGADA", "La deuda ya fue pagada")

    momento = reloj.ahora()
    monto = a_soles(deuda["monto_cent"])
    if origen == "DEBITO_AUTOMATICO":
        mora = Decimal("0.00")
    else:
        try:
            mora = reglas_servicios.calcular_mora(monto, date.fromisoformat(deuda["vencimiento"]), momento.date())
        except reglas_servicios.DeudaEnCobranza as error:
            raise validacion("DEUDA_EN_COBRANZA", f"{error}. Comunícate con la empresa.")

    mora_cent = a_centimos(mora)
    total_cent = deuda["monto_cent"] + mora_cent
    if saldo_centimos(bd, titular.id) < total_cent:
        raise validacion("SALDO_INSUFICIENTE", "Saldo insuficiente para pagar la deuda")

    actualizada = bd.execute(
        "UPDATE deudas SET estado = 'PAGADA', pagada_en = ? WHERE id = ? AND estado = 'PENDIENTE'",
        (reloj.a_texto(momento), deuda["id"]),
    ).rowcount
    if actualizada == 0:
        raise conflicto("DEUDA_YA_PAGADA", "La deuda ya fue pagada")

    codigo = generar_codigo_operacion("PAG", titular.id, momento)
    mover_saldo(bd, titular.id, -total_cent, momento)
    bd.execute(
        """INSERT INTO pagos_servicio (codigo_operacion, usuario_id, deuda_id, monto_cent, mora_cent, total_cent, fecha, origen)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (codigo, titular.id, deuda["id"], deuda["monto_cent"], mora_cent, total_cent, reloj.a_texto(momento), origen),
    )
    nombre_empresa = bd.execute("SELECT nombre FROM empresas_servicio WHERE codigo = ?", (deuda["empresa"],)).fetchone()[0]
    prefijo = "Débito automático" if origen == "DEBITO_AUTOMATICO" else "Pago"
    registrar_movimiento(bd, titular.id, codigo, "PAGO_SERVICIO",
                         f"{prefijo} {nombre_empresa} - {deuda['periodo']}", total_cent, -total_cent, momento,
                         0, deuda["suministro"])
    evaluar_alertas(bd, titular.id, titular.celular, "PAGOS")
    return {
        "codigo_operacion": codigo,
        "empresa": deuda["empresa"],
        "suministro": deuda["suministro"],
        "periodo": deuda["periodo"],
        "monto": formato(deuda["monto_cent"]),
        "mora": formato(mora_cent),
        "total": formato(total_cent),
        "origen": origen,
        "saldo": formato(saldo_centimos(bd, titular.id)),
        "fecha": reloj.a_texto(momento),
    }


# ---------------------------------------------------------------- alertas de consumo

def gasto_del_dia(bd: sqlite3.Connection, usuario_id: int, tipo: str, momento: datetime | None = None) -> int:
    """Gasto del día en céntimos: transferencias por su monto, recargas por su monto y pagos por su total."""
    desde = inicio_del_dia(momento or reloj.ahora())
    consultas = {
        "TRANSFERENCIAS": "SELECT COALESCE(SUM(monto_cent), 0) FROM transferencias WHERE origen_id = ? AND fecha >= ?",
        "RECARGAS": "SELECT COALESCE(SUM(monto_cent), 0) FROM recargas WHERE usuario_id = ? AND fecha >= ?",
        "PAGOS": "SELECT COALESCE(SUM(total_cent), 0) FROM pagos_servicio WHERE usuario_id = ? AND fecha >= ?",
    }
    if tipo == "TODAS":
        return sum(bd.execute(c, (usuario_id, desde)).fetchone()[0] for c in consultas.values())
    return bd.execute(consultas[tipo], (usuario_id, desde)).fetchone()[0]


def evaluar_alertas(bd: sqlite3.Connection, usuario_id: int, celular: str, tipo_operacion: str) -> None:
    """Envía un SMS por cada alerta ACTIVA cuyo umbral se alcanzó (como máximo una vez por día)."""
    ahora = reloj.ahora()
    hoy = reloj.hoy().isoformat()
    alertas = bd.execute(
        f"""SELECT * FROM alertas WHERE usuario_id = ? AND estado = 'ACTIVA'
            AND tipo IN ({",".join("?" * len(tipos_afectados(tipo_operacion)))})""",
        (usuario_id, *tipos_afectados(tipo_operacion)),
    ).fetchall()
    for alerta in alertas:
        ya_notificada = alerta["ultima_notificacion"] == hoy
        if ya_notificada:
            continue
        gasto = gasto_del_dia(bd, usuario_id, alerta["tipo"], ahora)
        if gasto >= alerta["umbral_cent"]:
            notificar(bd, celular,
                      f"Alerta Qolqe: tu gasto de hoy en {alerta['tipo'].lower()} llegó a S/ {formato(gasto)} "
                      f"(umbral S/ {formato(alerta['umbral_cent'])}).")
            bd.execute("UPDATE alertas SET ultima_notificacion = ? WHERE id = ?", (reloj.a_texto(ahora), alerta["id"]))
