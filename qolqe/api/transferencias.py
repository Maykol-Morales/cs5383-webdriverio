"""Transferencias entre cuentas Qolqe e interbancarias."""
import sqlite3
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from qolqe.bd import obtener_bd
from qolqe.dependencias import UsuarioActual, usuario_actual
from qolqe.errores import no_encontrado, validacion
from qolqe.reglas import nucleo
from qolqe.transacciones import Titular, realizar_transferencia

router = APIRouter(tags=["Transferencias"])


class SolicitudTransferencia(BaseModel):
    tipo: Literal["QOLQE", "INTERBANCARIA"] = Field(default="QOLQE", description="QOLQE: a otro usuario de Qolqe; INTERBANCARIA: a una cuenta de otro banco")
    celular_destino: str | None = Field(default=None, description="Celular del destinatario (tipo QOLQE)", examples=["912345678"])
    contacto_id: int | None = Field(default=None, description="Alternativa a celular_destino: id de un contacto frecuente")
    cci: str | None = Field(default=None, description="CCI de 20 dígitos (tipo INTERBANCARIA)")
    monto: Decimal = Field(examples=["100.00"])
    descripcion: str | None = Field(default=None, max_length=60)


class Destinatario(BaseModel):
    nombre: str | None = None
    celular: str | None = None
    cci: str | None = None


class TransferenciaRealizada(BaseModel):
    codigo_operacion: str
    tipo: str
    monto: str
    comision: str
    total: str
    destinatario: Destinatario
    saldo: str = Field(description="Saldo del origen después de la operación")
    fecha: str


class Comision(BaseModel):
    monto: str
    comision: str
    total: str


@router.get("/api/transferencias/comision", response_model=Comision, summary="Simular la comisión de una transferencia")
def simular_comision(
    monto: Decimal = Query(examples=["150.00"]),
    tipo: Literal["QOLQE", "INTERBANCARIA"] = "QOLQE",
    usuario: UsuarioActual = Depends(usuario_actual),
):
    try:
        nucleo.validar_monto(monto)
    except ValueError as error:
        raise validacion("MONTO_INVALIDO", str(error))
    comision = nucleo.calcular_comision(monto, mismo_banco=(tipo == "QOLQE"))
    return Comision(monto=str(monto.quantize(Decimal("0.01"))), comision=str(comision),
                    total=str((monto + comision).quantize(Decimal("0.01"))))


def _resolver_destino_qolqe(bd: sqlite3.Connection, usuario: UsuarioActual, datos: SolicitudTransferencia) -> sqlite3.Row:
    celular = datos.celular_destino
    if datos.contacto_id is not None:
        contacto = bd.execute(
            """SELECT u.celular FROM contactos c JOIN usuarios u ON u.id = c.contacto_usuario_id
               WHERE c.id = ? AND c.usuario_id = ?""",
            (datos.contacto_id, usuario.id),
        ).fetchone()
        if contacto is None:
            raise no_encontrado("CONTACTO_NO_ENCONTRADO", "El contacto no existe")
        celular = contacto["celular"]
    if not celular:
        raise validacion("DESTINO_REQUERIDO", "Indica el celular de destino o un contacto")
    try:
        nucleo.validar_celular(celular)
    except ValueError as error:
        raise validacion("CELULAR_INVALIDO", str(error))
    if celular == usuario.celular:
        raise validacion("TRANSFERENCIA_A_SI_MISMO", "No puedes transferirte a ti mismo")
    destino = bd.execute("SELECT id, nombres, celular FROM usuarios WHERE celular = ?", (celular,)).fetchone()
    if destino is None:
        raise no_encontrado("DESTINO_NO_REGISTRADO", "El celular de destino no está registrado en Qolqe")
    return destino


@router.post("/api/transferencias", status_code=status.HTTP_201_CREATED, response_model=TransferenciaRealizada,
             summary="Realizar una transferencia")
def transferir(datos: SolicitudTransferencia, usuario: UsuarioActual = Depends(usuario_actual),
               bd: sqlite3.Connection = Depends(obtener_bd)):
    try:
        nucleo.validar_monto(datos.monto)
    except ValueError as error:
        raise validacion("MONTO_INVALIDO", str(error))

    destino = None
    if datos.tipo == "QOLQE":
        destino = _resolver_destino_qolqe(bd, usuario, datos)
    else:
        if not datos.cci:
            raise validacion("DESTINO_REQUERIDO", "Indica el CCI de destino")
        try:
            nucleo.validar_cci(datos.cci)
        except ValueError as error:
            raise validacion("CCI_INVALIDO", str(error))

    comprobante = realizar_transferencia(bd, Titular(usuario.id, usuario.celular, usuario.nombres), datos.monto,
                                         destino=destino, cci=datos.cci, descripcion=datos.descripcion)
    return TransferenciaRealizada(**comprobante)
