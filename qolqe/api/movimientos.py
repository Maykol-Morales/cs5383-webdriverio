"""Historial de movimientos: filtros, paginación, clasificación y exportación (G3)."""
import csv
import io
import sqlite3
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field

from qolqe import reloj
from qolqe.bd import obtener_bd
from qolqe.dependencias import UsuarioActual, usuario_actual
from qolqe.dinero import formato
from qolqe.errores import no_encontrado, validacion
from qolqe.operaciones import saldo_centimos
from qolqe.reglas.historial import MOVIMIENTOS_POR_PAGINA, total_paginas, validar_filtro, validar_nota

COLUMNAS_CSV = ["fecha", "codigo_operacion", "tipo", "descripcion", "monto", "comision", "importe", "categoria", "nota"]

router = APIRouter(tags=["Movimientos"])


class CategoriaAsignada(BaseModel):
    id: int
    nombre: str
    color: str


class Movimiento(BaseModel):
    codigo_operacion: str
    fecha: str
    tipo: str = Field(examples=["TRANSFERENCIA_ENVIADA"])
    descripcion: str
    contraparte: str | None
    monto: str
    comision: str
    importe: str = Field(description="Efecto en el saldo: negativo si es un cargo")
    saldo_posterior: str | None = None
    categoria: CategoriaAsignada | None = None
    nota: str | None = None


class PaginaMovimientos(BaseModel):
    desde: str
    hasta: str
    tipo: str | None
    categoria_id: int | None
    pagina: int
    por_pagina: int
    total: int
    total_paginas: int
    movimientos: list[Movimiento]


def _a_movimiento(fila: sqlite3.Row, saldo_posterior: int | None = None) -> Movimiento:
    return Movimiento(
        codigo_operacion=fila["codigo_operacion"],
        fecha=fila["fecha"],
        tipo=fila["tipo"],
        descripcion=fila["descripcion"],
        contraparte=fila["contraparte"],
        monto=formato(fila["monto_cent"]),
        comision=formato(fila["comision_cent"]),
        importe=formato(fila["importe_cent"]),
        saldo_posterior=formato(saldo_posterior) if saldo_posterior is not None else None,
        categoria=CategoriaAsignada(id=fila["categoria_id"], nombre=fila["categoria_nombre"], color=fila["categoria_color"])
        if fila["categoria_id"] is not None else None,
        nota=fila["nota"],
    )


_SELECT_MOVIMIENTOS = """SELECT m.*, c.nombre AS categoria_nombre, c.color AS categoria_color FROM movimientos m
                         LEFT JOIN categorias c ON c.id = m.categoria_id"""


def _filtrar(bd: sqlite3.Connection, usuario_id: int, desde: date | None, hasta: date | None,
             tipo: str | None, categoria_id: int | None) -> tuple[date, date, list[sqlite3.Row]]:
    """Aplica los filtros del historial (rango, tipo y categoría) y devuelve los movimientos, del más reciente al más antiguo."""
    hoy = reloj.hoy()
    hasta = hasta or hoy
    desde = desde or (hasta - timedelta(days=30))
    try:
        validar_filtro(desde, hasta, 1, hoy, tipo)
    except ValueError as error:
        raise validacion("FILTRO_INVALIDO", str(error))

    consulta = _SELECT_MOVIMIENTOS + " WHERE m.usuario_id = ? AND m.fecha BETWEEN ? AND ?"
    parametros: list = [usuario_id, desde.isoformat(), hasta.isoformat()]
    if tipo:
        consulta += " AND m.tipo = ?"
        parametros.append(tipo)
    if categoria_id is not None:
        if not bd.execute("SELECT 1 FROM categorias WHERE id = ? AND usuario_id = ?", (categoria_id, usuario_id)).fetchone():
            raise validacion("FILTRO_INVALIDO", "La categoría no existe")
        consulta += " AND m.categoria_id = ?"
        parametros.append(categoria_id)
    consulta += " ORDER BY m.fecha DESC, m.id DESC"
    return desde, hasta, bd.execute(consulta, parametros).fetchall()


@router.get("/api/movimientos", response_model=PaginaMovimientos, summary="Historial de movimientos")
def listar(
    desde: date | None = Query(default=None, description="Fecha inicial (AAAA-MM-DD). Por defecto, hace 30 días"),
    hasta: date | None = Query(default=None, description="Fecha final (AAAA-MM-DD). Por defecto, hoy"),
    tipo: str | None = Query(default=None, description="TRANSFERENCIA_ENVIADA, TRANSFERENCIA_RECIBIDA, RECARGA o PAGO_SERVICIO"),
    categoria_id: int | None = Query(default=None, description="Id de una de mis categorías"),
    pagina: int = Query(default=1),
    usuario: UsuarioActual = Depends(usuario_actual),
    bd: sqlite3.Connection = Depends(obtener_bd),
):
    if pagina < 1:
        raise validacion("FILTRO_INVALIDO", "La página debe ser mayor o igual a 1")
    desde, hasta, filas = _filtrar(bd, usuario.id, desde, hasta, tipo, categoria_id)

    saldo_actual = saldo_centimos(bd, usuario.id)
    movimientos = []
    for fila in filas:
        posteriores = bd.execute(
            """SELECT COALESCE(SUM(importe_cent), 0) FROM movimientos
               WHERE usuario_id = ? AND (fecha > ? OR (fecha = ? AND id > ?))""",
            (usuario.id, fila["fecha"], fila["fecha"], fila["id"]),
        ).fetchone()[0]
        movimientos.append(_a_movimiento(fila, saldo_actual - posteriores))

    inicio = (pagina - 1) * MOVIMIENTOS_POR_PAGINA
    return PaginaMovimientos(
        desde=desde.isoformat(),
        hasta=hasta.isoformat(),
        tipo=tipo,
        categoria_id=categoria_id,
        pagina=pagina,
        por_pagina=MOVIMIENTOS_POR_PAGINA,
        total=len(movimientos),
        total_paginas=total_paginas(len(movimientos)),
        movimientos=movimientos[inicio:inicio + MOVIMIENTOS_POR_PAGINA],
    )


@router.get("/api/movimientos/recientes", response_model=list[Movimiento], summary="Últimos movimientos (para la pantalla de inicio)")
def recientes(limite: int = Query(default=5, ge=1, le=20), usuario: UsuarioActual = Depends(usuario_actual),
              bd: sqlite3.Connection = Depends(obtener_bd)):
    filas = bd.execute(
        _SELECT_MOVIMIENTOS + " WHERE m.usuario_id = ? ORDER BY m.fecha DESC, m.id DESC LIMIT ?", (usuario.id, limite)
    ).fetchall()
    return [_a_movimiento(f) for f in filas]


@router.get("/api/movimientos/exportar", summary="Exportar mis movimientos a CSV",
            response_class=Response, responses={200: {"content": {"text/csv": {}}}},
            description="Mismos filtros y reglas de rango que el historial, sin paginar. Separador punto y coma, UTF-8.")
def exportar(
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    tipo: str | None = Query(default=None),
    categoria_id: int | None = Query(default=None),
    usuario: UsuarioActual = Depends(usuario_actual),
    bd: sqlite3.Connection = Depends(obtener_bd),
):
    desde, hasta, filas = _filtrar(bd, usuario.id, desde, hasta, tipo, categoria_id)
    salida = io.StringIO()
    escritor = csv.writer(salida, delimiter=";", lineterminator="\n")
    escritor.writerow(COLUMNAS_CSV)
    for f in filas:
        escritor.writerow([f["fecha"], f["codigo_operacion"], f["tipo"], f["descripcion"], formato(f["monto_cent"]),
                           formato(f["comision_cent"]), formato(f["importe_cent"]), f["categoria_nombre"] or "",
                           f["nota"] or ""])
    nombre = f"movimientos_{desde.isoformat()}_{hasta.isoformat()}.csv"
    return Response(content=salida.getvalue().encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.get("/api/movimientos/{codigo_operacion}", response_model=Movimiento, summary="Detalle de un movimiento")
def detalle(codigo_operacion: str, usuario: UsuarioActual = Depends(usuario_actual),
            bd: sqlite3.Connection = Depends(obtener_bd)):
    fila = bd.execute(
        _SELECT_MOVIMIENTOS + " WHERE m.codigo_operacion = ? ORDER BY m.id LIMIT 1", (codigo_operacion,)
    ).fetchone()
    if fila is None:
        raise no_encontrado("MOVIMIENTO_NO_ENCONTRADO", "El movimiento no existe")
    return _a_movimiento(fila)


class Clasificacion(BaseModel):
    categoria_id: int | None = Field(default=None, description="Id de una de mis categorías; null para quitarla")
    nota: str | None = Field(default=None, description="Hasta 100 caracteres; null o vacío para quitarla")


@router.put("/api/movimientos/{codigo_operacion}/clasificacion", response_model=Movimiento,
            summary="Asignar categoría y nota a un movimiento",
            description="Solo se actualizan los campos enviados. No modifica el monto, la fecha ni el tipo.")
def clasificar(codigo_operacion: str, datos: Clasificacion, usuario: UsuarioActual = Depends(usuario_actual),
               bd: sqlite3.Connection = Depends(obtener_bd)):
    actual = bd.execute("SELECT * FROM movimientos WHERE codigo_operacion = ? AND usuario_id = ? ORDER BY id LIMIT 1",
                        (codigo_operacion, usuario.id)).fetchone()
    if actual is None:
        raise no_encontrado("MOVIMIENTO_NO_ENCONTRADO", "El movimiento no existe")
    categoria_id, nota = actual["categoria_id"], actual["nota"]
    if "categoria_id" in datos.model_fields_set:
        categoria_id = datos.categoria_id
        if categoria_id is not None and not bd.execute(
            "SELECT 1 FROM categorias WHERE id = ? AND usuario_id = ?", (categoria_id, usuario.id)
        ).fetchone():
            raise no_encontrado("CATEGORIA_NO_ENCONTRADA", "La categoría no existe")
    if "nota" in datos.model_fields_set:
        try:
            nota = validar_nota(datos.nota)
        except ValueError as error:
            raise validacion("NOTA_INVALIDA", str(error))
    bd.execute("UPDATE movimientos SET categoria_id = ?, nota = ? WHERE codigo_operacion = ? AND usuario_id = ?",
               (categoria_id, nota, codigo_operacion, usuario.id))
    fila = bd.execute(_SELECT_MOVIMIENTOS + " WHERE m.id = ?", (actual["id"],)).fetchone()
    return _a_movimiento(fila)
