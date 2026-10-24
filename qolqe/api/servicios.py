"""Consulta y pago de servicios, afiliaciones y débito automático (G2)."""
import sqlite3
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from qolqe import reloj
from qolqe.bd import obtener_bd
from qolqe.dependencias import UsuarioActual, usuario_actual
from qolqe.dinero import a_centimos, a_soles, formato
from qolqe.errores import ErrorNegocio, conflicto, no_encontrado, validacion
from qolqe.operaciones import enmascarar_nombre, notificar
from qolqe.reglas import servicios as reglas
from qolqe.transacciones import Titular, realizar_pago

router = APIRouter(tags=["Pago de servicios"])


class Empresa(BaseModel):
    codigo: str
    nombre: str
    rubro: str


class Deuda(BaseModel):
    id: int
    empresa: str
    suministro: str
    titular: str
    periodo: str
    monto: str
    vencimiento: str
    dias_atraso: int
    mora: str | None = Field(description="Nulo si la deuda está en cobranza")
    total: str | None
    estado: str = Field(examples=["PENDIENTE", "EN_COBRANZA"])


class SolicitudPago(BaseModel):
    deuda_id: int


class PagoRealizado(BaseModel):
    codigo_operacion: str
    empresa: str
    suministro: str
    periodo: str
    monto: str
    mora: str
    total: str
    origen: str = Field(examples=["MANUAL"])
    saldo: str
    fecha: str


def _a_deuda(fila: sqlite3.Row, hoy: date) -> Deuda:
    vencimiento = date.fromisoformat(fila["vencimiento"])
    monto = a_soles(fila["monto_cent"])
    try:
        mora = reglas.calcular_mora(monto, vencimiento, hoy)
        estado, total = "PENDIENTE", str(monto + mora)
        mora_texto = str(mora)
    except reglas.DeudaEnCobranza:
        estado, total, mora_texto = "EN_COBRANZA", None, None
    return Deuda(id=fila["id"], empresa=fila["empresa"], suministro=fila["suministro"],
                 titular=enmascarar_nombre(fila["titular"]), periodo=fila["periodo"], monto=str(monto),
                 vencimiento=fila["vencimiento"], dias_atraso=reglas.dias_de_atraso(vencimiento, hoy),
                 mora=mora_texto, total=total, estado=estado)


@router.get("/api/servicios/empresas", response_model=list[Empresa], summary="Empresas de servicios afiliadas")
def empresas(bd: sqlite3.Connection = Depends(obtener_bd)):
    return [Empresa(**dict(f)) for f in bd.execute("SELECT * FROM empresas_servicio ORDER BY nombre")]


@router.get("/api/servicios/deudas", response_model=list[Deuda], summary="Consultar deudas pendientes de un suministro")
def consultar_deudas(
    empresa: str = Query(examples=["ELECTRO"]),
    suministro: str = Query(examples=["10000003"]),
    usuario: UsuarioActual = Depends(usuario_actual),
    bd: sqlite3.Connection = Depends(obtener_bd),
):
    if not bd.execute("SELECT 1 FROM empresas_servicio WHERE codigo = ?", (empresa,)).fetchone():
        raise no_encontrado("EMPRESA_NO_ENCONTRADA", "La empresa no existe")
    try:
        reglas.validar_suministro(suministro)
    except ValueError as error:
        raise validacion("SUMINISTRO_INVALIDO", str(error))
    filas = bd.execute(
        "SELECT * FROM deudas WHERE empresa = ? AND suministro = ? AND estado = 'PENDIENTE' ORDER BY vencimiento",
        (empresa, suministro),
    ).fetchall()
    if not filas:
        raise no_encontrado("SIN_DEUDA_PENDIENTE", "El suministro no tiene deudas pendientes")
    hoy = reloj.hoy()
    return [_a_deuda(f, hoy) for f in filas]


@router.post("/api/servicios/pagos", status_code=status.HTTP_201_CREATED, response_model=PagoRealizado,
             summary="Pagar una deuda (monto total + mora)")
def pagar(datos: SolicitudPago, usuario: UsuarioActual = Depends(usuario_actual),
          bd: sqlite3.Connection = Depends(obtener_bd)):
    deuda = bd.execute("SELECT * FROM deudas WHERE id = ?", (datos.deuda_id,)).fetchone()
    if deuda is None:
        raise no_encontrado("DEUDA_NO_ENCONTRADA", "La deuda no existe")
    comprobante = realizar_pago(bd, Titular(usuario.id, usuario.celular, usuario.nombres), deuda)
    return PagoRealizado(**comprobante)


class PagoListado(BaseModel):
    codigo_operacion: str
    empresa: str
    suministro: str
    periodo: str
    monto: str
    mora: str
    total: str
    origen: str = Field(examples=["MANUAL", "DEBITO_AUTOMATICO"])
    fecha: str


_CONSULTA_PAGOS = """SELECT p.*, d.empresa, d.suministro, d.periodo FROM pagos_servicio p
                     JOIN deudas d ON d.id = p.deuda_id WHERE p.usuario_id = ?"""


def _a_pago(fila: sqlite3.Row) -> PagoListado:
    return PagoListado(codigo_operacion=fila["codigo_operacion"], empresa=fila["empresa"], suministro=fila["suministro"],
                       periodo=fila["periodo"], monto=formato(fila["monto_cent"]), mora=formato(fila["mora_cent"]),
                       total=formato(fila["total_cent"]), origen=fila["origen"], fecha=fila["fecha"])


@router.get("/api/servicios/pagos", response_model=list[PagoListado], summary="Mis pagos de servicios")
def listar_pagos(
    afiliacion_id: int | None = Query(default=None, description="Filtra los pagos del suministro de una afiliación"),
    usuario: UsuarioActual = Depends(usuario_actual),
    bd: sqlite3.Connection = Depends(obtener_bd),
):
    consulta, parametros = _CONSULTA_PAGOS, [usuario.id]
    if afiliacion_id is not None:
        afiliacion = _afiliacion(bd, usuario.id, afiliacion_id)
        consulta += " AND d.empresa = ? AND d.suministro = ?"
        parametros += [afiliacion["empresa"], afiliacion["suministro"]]
    filas = bd.execute(consulta + " ORDER BY p.fecha DESC, p.id DESC", parametros).fetchall()
    return [_a_pago(f) for f in filas]


@router.get("/api/servicios/pagos/{codigo_operacion}", response_model=PagoListado, summary="Comprobante de un pago")
def comprobante_pago(codigo_operacion: str, usuario: UsuarioActual = Depends(usuario_actual),
                     bd: sqlite3.Connection = Depends(obtener_bd)):
    fila = bd.execute(_CONSULTA_PAGOS + " AND p.codigo_operacion = ?", (usuario.id, codigo_operacion)).fetchone()
    if fila is None:
        raise no_encontrado("PAGO_NO_ENCONTRADO", "El pago no existe")
    return _a_pago(fila)


# ---------------------------------------------------------------- afiliaciones

class SolicitudAfiliacion(BaseModel):
    empresa: str = Field(examples=["ELECTRO"])
    suministro: str = Field(examples=["10000001"])
    alias: str = Field(examples=["Luz de la casa"])


class CambioAfiliacion(BaseModel):
    alias: str | None = Field(default=None, examples=["Luz depa"])
    debito_automatico: bool | None = None


class Afiliacion(BaseModel):
    id: int
    alias: str
    empresa: str
    empresa_nombre: str
    suministro: str
    total_pendiente: str = Field(description="Suma de los totales (monto + mora) de las deudas que se pueden pagar")
    proximo_vencimiento: str | None = Field(description="Vencimiento más cercano, desde hoy, de una deuda pendiente")
    debito_automatico: bool
    situacion: str = Field(examples=["AL_DIA", "CON_DEUDA", "EN_COBRANZA"])
    creada_en: str


def _afiliacion(bd: sqlite3.Connection, usuario_id: int, afiliacion_id: int) -> sqlite3.Row:
    fila = bd.execute("SELECT * FROM afiliaciones WHERE id = ? AND usuario_id = ?", (afiliacion_id, usuario_id)).fetchone()
    if fila is None:
        raise no_encontrado("AFILIACION_NO_ENCONTRADA", "La afiliación no existe")
    return fila


def _a_afiliacion(bd: sqlite3.Connection, fila: sqlite3.Row) -> Afiliacion:
    hoy = reloj.hoy()
    deudas = bd.execute(
        "SELECT * FROM deudas WHERE empresa = ? AND suministro = ? AND estado = 'PENDIENTE' ORDER BY vencimiento",
        (fila["empresa"], fila["suministro"]),
    ).fetchall()
    total_cent, en_cobranza, proximo = 0, 0, None
    for deuda in deudas:
        detalle = _a_deuda(deuda, hoy)
        if detalle.estado == "EN_COBRANZA":
            en_cobranza += 1
        else:
            total_cent += a_centimos(Decimal(detalle.total))
        if proximo is None and deuda["vencimiento"] >= hoy.isoformat():
            proximo = deuda["vencimiento"]
    nombre = bd.execute("SELECT nombre FROM empresas_servicio WHERE codigo = ?", (fila["empresa"],)).fetchone()[0]
    return Afiliacion(id=fila["id"], alias=fila["alias"], empresa=fila["empresa"], empresa_nombre=nombre,
                      suministro=fila["suministro"], total_pendiente=formato(total_cent), proximo_vencimiento=proximo,
                      debito_automatico=bool(fila["debito_automatico"]),
                      situacion=reglas.situacion_afiliacion(len(deudas), en_cobranza), creada_en=fila["creada_en"])


def _alias_valido(alias: str) -> str:
    try:
        return reglas.validar_alias_afiliacion(alias)
    except ValueError as error:
        raise validacion("AFILIACION_INVALIDA", str(error))


@router.get("/api/servicios/afiliaciones", response_model=list[Afiliacion], summary="Mis servicios afiliados")
def listar_afiliaciones(usuario: UsuarioActual = Depends(usuario_actual), bd: sqlite3.Connection = Depends(obtener_bd)):
    filas = bd.execute("SELECT * FROM afiliaciones WHERE usuario_id = ? ORDER BY alias COLLATE NOCASE", (usuario.id,))
    return [_a_afiliacion(bd, f) for f in filas.fetchall()]


@router.post("/api/servicios/afiliaciones", status_code=status.HTTP_201_CREATED, response_model=Afiliacion,
             summary="Afiliar un servicio")
def afiliar(datos: SolicitudAfiliacion, usuario: UsuarioActual = Depends(usuario_actual),
            bd: sqlite3.Connection = Depends(obtener_bd)):
    if not bd.execute("SELECT 1 FROM empresas_servicio WHERE codigo = ?", (datos.empresa,)).fetchone():
        raise no_encontrado("EMPRESA_NO_ENCONTRADA", "La empresa no existe")
    try:
        reglas.validar_suministro(datos.suministro)
    except ValueError as error:
        raise validacion("AFILIACION_INVALIDA", str(error))
    alias = _alias_valido(datos.alias)
    if not bd.execute("SELECT 1 FROM deudas WHERE empresa = ? AND suministro = ?", (datos.empresa, datos.suministro)).fetchone():
        raise no_encontrado("SUMINISTRO_NO_ENCONTRADO", "El suministro no existe en la empresa")

    existentes = bd.execute("SELECT empresa, suministro FROM afiliaciones WHERE usuario_id = ?", (usuario.id,)).fetchall()
    if len(existentes) >= reglas.MAX_AFILIACIONES:
        raise validacion("LIMITE_AFILIACIONES", f"Solo puedes afiliar {reglas.MAX_AFILIACIONES} servicios")
    if any(e["empresa"] == datos.empresa and e["suministro"] == datos.suministro for e in existentes):
        raise conflicto("AFILIACION_DUPLICADA", "Ya tienes afiliado ese suministro")

    cursor = bd.execute(
        "INSERT INTO afiliaciones (usuario_id, empresa, suministro, alias, creada_en) VALUES (?, ?, ?, ?, ?)",
        (usuario.id, datos.empresa, datos.suministro, alias, reloj.a_texto(reloj.ahora())),
    )
    return _a_afiliacion(bd, _afiliacion(bd, usuario.id, cursor.lastrowid))


@router.put("/api/servicios/afiliaciones/{afiliacion_id}", response_model=Afiliacion,
            summary="Cambiar el alias o el débito automático de una afiliación")
def editar_afiliacion(afiliacion_id: int, datos: CambioAfiliacion, usuario: UsuarioActual = Depends(usuario_actual),
                      bd: sqlite3.Connection = Depends(obtener_bd)):
    actual = _afiliacion(bd, usuario.id, afiliacion_id)
    alias = _alias_valido(datos.alias) if datos.alias is not None else actual["alias"]
    debito = actual["debito_automatico"] if datos.debito_automatico is None else int(datos.debito_automatico)
    bd.execute("UPDATE afiliaciones SET alias = ?, debito_automatico = ? WHERE id = ?", (alias, debito, afiliacion_id))
    if debito != actual["debito_automatico"]:
        estado = "activado" if debito else "desactivado"
        notificar(bd, usuario.celular, f"Débito automático {estado} para {alias} ({actual['empresa']} {actual['suministro']}).")
    return _a_afiliacion(bd, _afiliacion(bd, usuario.id, afiliacion_id))


@router.delete("/api/servicios/afiliaciones/{afiliacion_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Desafiliar un servicio")
def desafiliar(afiliacion_id: int, usuario: UsuarioActual = Depends(usuario_actual),
               bd: sqlite3.Connection = Depends(obtener_bd)):
    actual = _afiliacion(bd, usuario.id, afiliacion_id)
    if actual["debito_automatico"]:
        raise conflicto("DEBITO_ACTIVO", "Desactiva el débito automático antes de desafiliar el servicio")
    bd.execute("DELETE FROM afiliaciones WHERE id = ?", (afiliacion_id,))


def ejecutar_debitos(bd: sqlite3.Connection) -> tuple[int, int]:
    """Proceso diario: paga las deudas de afiliaciones con débito automático. Devuelve (pagadas, fallidas)."""
    hoy = reloj.hoy().isoformat()
    candidatas = bd.execute(
        """SELECT d.id AS deuda_id, a.alias, u.id AS usuario_id, u.celular, u.nombres FROM afiliaciones a
           JOIN usuarios u ON u.id = a.usuario_id
           JOIN deudas d ON d.empresa = a.empresa AND d.suministro = a.suministro
           WHERE a.debito_automatico = 1 AND u.estado = 'ACTIVA' AND d.estado = 'PENDIENTE' AND d.vencimiento <= ?
           ORDER BY d.vencimiento, a.id""",
        (hoy,),
    ).fetchall()
    pagadas = fallidas = 0
    for candidata in candidatas:
        deuda = bd.execute("SELECT * FROM deudas WHERE id = ?", (candidata["deuda_id"],)).fetchone()
        if deuda["estado"] != "PENDIENTE":
            continue
        titular = Titular(candidata["usuario_id"], candidata["celular"], candidata["nombres"])
        try:
            realizar_pago(bd, titular, deuda, origen="DEBITO_AUTOMATICO")
            pagadas += 1
        except ErrorNegocio as error:
            fallidas += 1
            notificar(bd, titular.celular,
                      f"No pudimos pagar con débito automático {candidata['alias']} ({deuda['periodo']}): {error.mensaje}.")
    return pagadas, fallidas
