"""API de soporte para pruebas automatizadas.

Solo está disponible cuando QOLQE_MODO_PRUEBA=1 (valor por defecto en desarrollo).
Permite reiniciar los datos, controlar el reloj, revisar los SMS simulados, ajustar saldos
y ejecutar el proceso diario.
"""
import sqlite3
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from qolqe import reloj
from qolqe.api.recargas import ejecutar_programadas
from qolqe.api.servicios import ejecutar_debitos
from qolqe.bd import obtener_bd
from qolqe.dinero import a_centimos, formato
from qolqe.errores import no_encontrado, validacion
from qolqe.semilla import reiniciar_datos

router = APIRouter(prefix="/api/pruebas", tags=["Soporte para pruebas"])


class EstadoReloj(BaseModel):
    ahora: str
    desfasado: bool


class CambioReloj(BaseModel):
    ahora: datetime | None = Field(default=None, description="Fija la fecha y hora (hora de Lima)")
    avanzar_minutos: int | None = Field(default=None, description="Adelanta el reloj N minutos")


class Notificacion(BaseModel):
    celular: str
    mensaje: str
    fecha: str


class AjusteSaldo(BaseModel):
    celular: str
    saldo: Decimal


class Resultado(BaseModel):
    mensaje: str


class ResultadoProcesoDiario(BaseModel):
    fecha: str
    recargas_exitosas: int
    recargas_fallidas: int
    debitos_pagados: int
    debitos_fallidos: int


def _estado_reloj() -> EstadoReloj:
    return EstadoReloj(ahora=reloj.a_texto(reloj.ahora()), desfasado=reloj.esta_desfasado())


@router.post("/reiniciar", response_model=Resultado, summary="Restaurar los datos semilla")
def reiniciar():
    reiniciar_datos()
    return Resultado(mensaje="Datos restaurados")


@router.get("/reloj", response_model=EstadoReloj, summary="Ver el reloj de la aplicación")
def ver_reloj():
    return _estado_reloj()


@router.put("/reloj", response_model=EstadoReloj, summary="Fijar o adelantar el reloj")
def cambiar_reloj(datos: CambioReloj):
    if datos.ahora is None and datos.avanzar_minutos is None:
        raise validacion("SOLICITUD_INVALIDA", "Indica 'ahora' o 'avanzar_minutos'")
    if datos.ahora is not None:
        reloj.fijar(datos.ahora)
    if datos.avanzar_minutos is not None:
        reloj.avanzar(datos.avanzar_minutos)
    return _estado_reloj()


@router.delete("/reloj", response_model=EstadoReloj, summary="Volver a la hora real")
def restablecer_reloj():
    reloj.restablecer()
    return _estado_reloj()


@router.get("/notificaciones", response_model=list[Notificacion], summary="SMS simulados enviados a un celular")
def notificaciones(celular: str = Query(examples=["987654321"]), bd: sqlite3.Connection = Depends(obtener_bd)):
    filas = bd.execute(
        "SELECT celular, mensaje, fecha FROM notificaciones WHERE celular = ? ORDER BY id DESC LIMIT 20", (celular,)
    ).fetchall()
    return [Notificacion(**dict(f)) for f in filas]


@router.put("/saldo", response_model=Resultado, summary="Fijar el saldo de un usuario")
def ajustar_saldo(datos: AjusteSaldo, bd: sqlite3.Connection = Depends(obtener_bd)):
    if datos.saldo < 0:
        raise validacion("SALDO_INVALIDO", "El saldo no puede ser negativo")
    actualizado = bd.execute(
        """UPDATE cuentas SET saldo_cent = ?, actualizado_en = ?
           WHERE usuario_id = (SELECT id FROM usuarios WHERE celular = ?)""",
        (a_centimos(datos.saldo), reloj.a_texto(reloj.ahora()), datos.celular),
    ).rowcount
    if actualizado == 0:
        raise no_encontrado("USUARIO_NO_ENCONTRADO", "No existe un usuario con ese celular")
    return Resultado(mensaje=f"Saldo actualizado a S/ {formato(a_centimos(datos.saldo))}")


@router.post("/procesar-diario", response_model=ResultadoProcesoDiario,
             summary="Ejecutar el proceso diario (recargas programadas y débitos automáticos) con la fecha del reloj")
def procesar_diario(bd: sqlite3.Connection = Depends(obtener_bd)):
    recargas_ok, recargas_error = ejecutar_programadas(bd)
    debitos_ok, debitos_error = ejecutar_debitos(bd)
    return ResultadoProcesoDiario(fecha=reloj.hoy().isoformat(), recargas_exitosas=recargas_ok,
                                  recargas_fallidas=recargas_error, debitos_pagados=debitos_ok,
                                  debitos_fallidos=debitos_error)
