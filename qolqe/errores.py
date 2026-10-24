"""Errores de negocio con código estable para los clientes de la API."""


class ErrorNegocio(Exception):
    def __init__(self, estado_http: int, codigo: str, mensaje: str):
        super().__init__(mensaje)
        self.estado_http = estado_http
        self.codigo = codigo
        self.mensaje = mensaje


def validacion(codigo: str, mensaje: str) -> ErrorNegocio:
    return ErrorNegocio(422, codigo, mensaje)


def no_encontrado(codigo: str, mensaje: str) -> ErrorNegocio:
    return ErrorNegocio(404, codigo, mensaje)


def conflicto(codigo: str, mensaje: str) -> ErrorNegocio:
    return ErrorNegocio(409, codigo, mensaje)
