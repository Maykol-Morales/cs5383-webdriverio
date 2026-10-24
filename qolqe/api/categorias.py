"""Categorías propias para clasificar movimientos (G3)."""
import sqlite3

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from qolqe import reloj
from qolqe.bd import obtener_bd
from qolqe.dependencias import UsuarioActual, usuario_actual
from qolqe.errores import conflicto, no_encontrado, validacion
from qolqe.reglas import historial as reglas

router = APIRouter(tags=["Categorías"])

DESCRIPCION_COLOR = "Color de la paleta: " + ", ".join(reglas.PALETA_COLORES)


class SolicitudCategoria(BaseModel):
    nombre: str = Field(examples=["Comida"])
    color: str = Field(description=DESCRIPCION_COLOR, examples=["#43A047"])


class CambioCategoria(BaseModel):
    nombre: str | None = Field(default=None, examples=["Restaurantes"])
    color: str | None = Field(default=None, description=DESCRIPCION_COLOR, examples=["#FB8C00"])


class Categoria(BaseModel):
    id: int
    nombre: str
    color: str
    cantidad_movimientos: int
    creada_en: str


def _categorias(bd: sqlite3.Connection, usuario_id: int) -> list[sqlite3.Row]:
    return bd.execute(
        """SELECT c.*, (SELECT COUNT(*) FROM movimientos m WHERE m.categoria_id = c.id) AS cantidad
           FROM categorias c WHERE c.usuario_id = ? ORDER BY c.nombre COLLATE NOCASE""",
        (usuario_id,),
    ).fetchall()


def _a_categoria(fila: sqlite3.Row) -> Categoria:
    return Categoria(id=fila["id"], nombre=fila["nombre"], color=fila["color"],
                     cantidad_movimientos=fila["cantidad"], creada_en=fila["creada_en"])


def _buscar(bd: sqlite3.Connection, usuario_id: int, categoria_id: int) -> sqlite3.Row:
    fila = next((c for c in _categorias(bd, usuario_id) if c["id"] == categoria_id), None)
    if fila is None:
        raise no_encontrado("CATEGORIA_NO_ENCONTRADA", "La categoría no existe")
    return fila


def _validar(funcion, valor: str) -> str:
    try:
        return funcion(valor)
    except ValueError as error:
        raise validacion("CATEGORIA_INVALIDA", str(error))


@router.get("/api/categorias", response_model=list[Categoria], summary="Mis categorías")
def listar(usuario: UsuarioActual = Depends(usuario_actual), bd: sqlite3.Connection = Depends(obtener_bd)):
    return [_a_categoria(f) for f in _categorias(bd, usuario.id)]


@router.post("/api/categorias", status_code=status.HTTP_201_CREATED, response_model=Categoria,
             summary="Crear una categoría")
def crear(datos: SolicitudCategoria, usuario: UsuarioActual = Depends(usuario_actual),
          bd: sqlite3.Connection = Depends(obtener_bd)):
    nombre = _validar(reglas.validar_nombre_categoria, datos.nombre)
    color = _validar(reglas.validar_color, datos.color)
    existentes = _categorias(bd, usuario.id)
    if len(existentes) >= reglas.MAX_CATEGORIAS:
        raise validacion("LIMITE_CATEGORIAS", f"Solo puedes tener {reglas.MAX_CATEGORIAS} categorías")
    try:
        reglas.verificar_nombre_disponible(nombre, [c["nombre"] for c in existentes])
    except reglas.CategoriaDuplicada as error:
        raise conflicto("CATEGORIA_DUPLICADA", str(error))
    cursor = bd.execute("INSERT INTO categorias (usuario_id, nombre, color, creada_en) VALUES (?, ?, ?, ?)",
                        (usuario.id, nombre, color, reloj.a_texto(reloj.ahora())))
    return _a_categoria(_buscar(bd, usuario.id, cursor.lastrowid))


@router.put("/api/categorias/{categoria_id}", response_model=Categoria, summary="Cambiar el nombre o el color")
def editar(categoria_id: int, datos: CambioCategoria, usuario: UsuarioActual = Depends(usuario_actual),
           bd: sqlite3.Connection = Depends(obtener_bd)):
    actual = _buscar(bd, usuario.id, categoria_id)
    nombre = _validar(reglas.validar_nombre_categoria, datos.nombre) if datos.nombre is not None else actual["nombre"]
    color = _validar(reglas.validar_color, datos.color) if datos.color is not None else actual["color"]
    bd.execute("UPDATE categorias SET nombre = ?, color = ? WHERE id = ?", (nombre, color, categoria_id))
    return _a_categoria(_buscar(bd, usuario.id, categoria_id))


@router.delete("/api/categorias/{categoria_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Eliminar una categoría (sus movimientos quedan sin categoría)")
def eliminar(categoria_id: int, usuario: UsuarioActual = Depends(usuario_actual),
             bd: sqlite3.Connection = Depends(obtener_bd)):
    _buscar(bd, usuario.id, categoria_id)
    bd.execute("UPDATE movimientos SET categoria_id = NULL WHERE categoria_id = ?", (categoria_id,))
    bd.execute("DELETE FROM categorias WHERE id = ?", (categoria_id,))
