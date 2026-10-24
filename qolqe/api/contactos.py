"""Contactos frecuentes: alta, búsqueda, favoritos y baja (G4)."""
import sqlite3

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from qolqe import reloj
from qolqe.bd import obtener_bd
from qolqe.dependencias import UsuarioActual, usuario_actual
from qolqe.errores import conflicto, no_encontrado, validacion
from qolqe.operaciones import enmascarar_nombre
from qolqe.reglas import contactos as reglas
from qolqe.reglas import nucleo

router = APIRouter(tags=["Contactos"])

CONTACTOS_POR_PAGINA = 10


class Contacto(BaseModel):
    id: int
    alias: str
    celular: str
    nombre: str = Field(description="Nombre enmascarado del contacto")
    favorito: bool


class PaginaContactos(BaseModel):
    buscar: str | None
    pagina: int
    por_pagina: int
    total: int
    total_paginas: int
    contactos: list[Contacto]


class SolicitudContacto(BaseModel):
    celular: str = Field(examples=["912345678"])
    alias: str = Field(examples=["Bruno trabajo"])


class CambioContacto(BaseModel):
    alias: str | None = Field(default=None, examples=["Bruno oficina"])
    favorito: bool | None = None


def _a_contacto(fila: sqlite3.Row) -> Contacto:
    return Contacto(id=fila["id"], alias=fila["alias"], celular=fila["celular"],
                    nombre=enmascarar_nombre(fila["nombres"]), favorito=bool(fila["favorito"]))


def consultar_contactos(bd: sqlite3.Connection, usuario_id: int) -> list[sqlite3.Row]:
    """Contactos del usuario: primero los favoritos y luego el resto, ordenados por alias."""
    return bd.execute(
        """SELECT c.id, c.alias, c.favorito, u.celular, u.nombres, c.contacto_usuario_id FROM contactos c
           JOIN usuarios u ON u.id = c.contacto_usuario_id
           WHERE c.usuario_id = ? ORDER BY c.favorito DESC, c.alias COLLATE NOCASE""",
        (usuario_id,),
    ).fetchall()


def buscar_contacto(bd: sqlite3.Connection, usuario_id: int, contacto_id: int) -> sqlite3.Row:
    fila = next((c for c in consultar_contactos(bd, usuario_id) if c["id"] == contacto_id), None)
    if fila is None:
        raise no_encontrado("CONTACTO_NO_ENCONTRADO", "El contacto no existe")
    return fila


def _validar(funcion, *argumentos) -> str:
    try:
        return funcion(*argumentos)
    except reglas.LimiteContactos as error:
        raise validacion("LIMITE_CONTACTOS", str(error))
    except reglas.AliasDuplicado as error:
        raise conflicto("ALIAS_DUPLICADO", str(error))
    except ValueError as error:
        raise validacion("ALIAS_INVALIDO", str(error))


@router.get("/api/contactos", response_model=PaginaContactos, summary="Listar y buscar mis contactos")
def listar(
    buscar: str | None = Query(default=None, description="Parte del alias, sin distinguir mayúsculas ni tildes"),
    pagina: int = Query(default=1, ge=1),
    usuario: UsuarioActual = Depends(usuario_actual),
    bd: sqlite3.Connection = Depends(obtener_bd),
):
    filas = consultar_contactos(bd, usuario.id)
    if buscar and buscar.strip():
        filas = [f for f in filas if reglas.coincide_busqueda(f["alias"], buscar)]
    inicio = (pagina - 1) * CONTACTOS_POR_PAGINA
    return PaginaContactos(
        buscar=buscar,
        pagina=pagina,
        por_pagina=CONTACTOS_POR_PAGINA,
        total=len(filas),
        total_paginas=max(1, -(-len(filas) // CONTACTOS_POR_PAGINA)),
        contactos=[_a_contacto(f) for f in filas[inicio:inicio + CONTACTOS_POR_PAGINA]],
    )


@router.post("/api/contactos", status_code=status.HTTP_201_CREATED, response_model=Contacto, summary="Agregar un contacto")
def agregar(datos: SolicitudContacto, usuario: UsuarioActual = Depends(usuario_actual),
            bd: sqlite3.Connection = Depends(obtener_bd)):
    try:
        nucleo.validar_celular(datos.celular)
    except ValueError as error:
        raise validacion("CELULAR_INVALIDO", str(error))
    if datos.celular == usuario.celular:
        raise validacion("CONTACTO_PROPIO", "No puedes agregarte como contacto")
    destino = bd.execute("SELECT id, nombres, celular FROM usuarios WHERE celular = ? AND estado = 'ACTIVA'",
                         (datos.celular,)).fetchone()
    if destino is None:
        raise no_encontrado("CELULAR_NO_REGISTRADO", "El celular no está registrado en Qolqe")

    existentes = consultar_contactos(bd, usuario.id)
    if any(c["contacto_usuario_id"] == destino["id"] for c in existentes):
        raise conflicto("CONTACTO_EXISTENTE", "Ese celular ya está en tus contactos")
    alias = _validar(reglas.validar_alias, datos.alias, [c["alias"] for c in existentes])

    cursor = bd.execute(
        "INSERT INTO contactos (usuario_id, contacto_usuario_id, alias, creado_en) VALUES (?, ?, ?, ?)",
        (usuario.id, destino["id"], alias, reloj.a_texto(reloj.ahora())),
    )
    return _a_contacto(buscar_contacto(bd, usuario.id, cursor.lastrowid))


@router.put("/api/contactos/{contacto_id}", response_model=Contacto,
            summary="Cambiar el alias o marcar como favorito", description="Solo se actualizan los campos enviados.")
def editar(contacto_id: int, datos: CambioContacto, usuario: UsuarioActual = Depends(usuario_actual),
           bd: sqlite3.Connection = Depends(obtener_bd)):
    existentes = consultar_contactos(bd, usuario.id)
    actual = next((c for c in existentes if c["id"] == contacto_id), None)
    if actual is None:
        raise no_encontrado("CONTACTO_NO_ENCONTRADO", "El contacto no existe")

    alias = actual["alias"]
    if datos.alias is not None:
        otros = [c["alias"] for c in existentes if c["id"] != contacto_id]
        alias = _validar(reglas.validar_cambio_alias, datos.alias, otros)
    favorito = actual["favorito"] if datos.favorito is None else int(datos.favorito)
    if favorito and not actual["favorito"]:
        if sum(c["favorito"] for c in existentes) >= reglas.MAX_FAVORITOS:
            raise validacion("LIMITE_FAVORITOS", f"Solo puedes tener {reglas.MAX_FAVORITOS} contactos favoritos")

    bd.execute("UPDATE contactos SET alias = ?, favorito = ? WHERE id = ?", (alias, favorito, contacto_id))
    return _a_contacto(buscar_contacto(bd, usuario.id, contacto_id))


@router.delete("/api/contactos/{contacto_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Eliminar un contacto")
def eliminar(contacto_id: int, usuario: UsuarioActual = Depends(usuario_actual),
             bd: sqlite3.Connection = Depends(obtener_bd)):
    contacto = buscar_contacto(bd, usuario.id, contacto_id)
    pendientes = bd.execute(
        """SELECT COUNT(*) FROM solicitudes WHERE estado = 'PENDIENTE' AND vence_en > ?
           AND ((solicitante_id = ? AND destinatario_id = ?) OR (solicitante_id = ? AND destinatario_id = ?))""",
        (reloj.a_texto(reloj.ahora()), usuario.id, contacto["contacto_usuario_id"],
         contacto["contacto_usuario_id"], usuario.id),
    ).fetchone()[0]
    if pendientes:
        raise conflicto("SOLICITUDES_PENDIENTES", "Tienes solicitudes de dinero pendientes con este contacto")
    bd.execute("DELETE FROM contactos WHERE id = ?", (contacto_id,))
