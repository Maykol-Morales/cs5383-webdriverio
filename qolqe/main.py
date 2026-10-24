"""Aplicación Qolqe Wallet: API REST + interfaz web."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from qolqe import config, contrato
from qolqe.api import (
    autenticacion,
    categorias,
    contactos,
    cuentas,
    limites,
    movimientos,
    recargas,
    seguridad,
    servicios,
    solicitudes,
    soporte_pruebas,
    transferencias,
)
from qolqe.errores import ErrorNegocio
from qolqe.semilla import inicializar_si_es_necesario

CARPETA_WEB = Path(__file__).parent / "web"
PAGINAS = ["login", "registro", "desbloqueo", "inicio", "perfil", "transferir", "recargas", "servicios",
           "historial", "contactos", "solicitudes", "limites", "seguridad"]

DESCRIPCION = """
API de **Qolqe Wallet**, billetera digital ficticia del curso CS5383.
La especificación funcional (historias de usuario, criterios de aceptación y reglas) está en `docs/requisitos.md`;
cada operación indica la historia de usuario que implementa.

### Autenticación
1. `POST /api/auth/login` devuelve un `access_token` (JWT) válido por **30 minutos** y crea una sesión.
2. En **Authorize** (o en la cabecera `Authorization: Bearer <token>`) se envía el token en cada operación protegida.
3. Un token vencido, inválido o de una sesión cerrada responde `401 NO_AUTENTICADO`.

### Convenciones
| Tema | Convención |
|---|---|
| Montos | Se envían como número o texto (`100`, `"100.50"`) y se devuelven como texto con 2 decimales (`"100.50"`) |
| Fechas | Hora de Lima (UTC-5). Fecha y hora: `AAAA-MM-DDTHH:MM:SS`. Fecha: `AAAA-MM-DD` |
| Actualización parcial | En los `PUT` de edición solo se modifican los campos enviados |
| Propiedad de los datos | Un recurso de otro usuario responde `404`, como si no existiera |

### Errores
Todas las respuestas de error tienen el esquema **Error**: `{"codigo": "...", "detail": "..."}`.
Cada operación lista los códigos que puede devolver, con un ejemplo por código.

| HTTP | Significado |
|---|---|
| 401 | No autenticado o credenciales incorrectas |
| 404 | Recurso inexistente o de otro usuario |
| 409 | Conflicto con el estado actual (duplicados, transiciones no permitidas) |
| 422 | Regla de negocio o dato inválido. `SOLICITUD_INVALIDA` indica un campo faltante o de tipo incorrecto, con el detalle en `errores` |
| 423 | Cuenta bloqueada |
"""


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    inicializar_si_es_necesario()
    yield


app = FastAPI(title="Qolqe Wallet API", version=config.VERSION, description=DESCRIPCION, lifespan=ciclo_de_vida)


@app.exception_handler(ErrorNegocio)
async def manejar_error_negocio(request: Request, error: ErrorNegocio):
    return JSONResponse(status_code=error.estado_http, content={"codigo": error.codigo, "detail": error.mensaje})


@app.exception_handler(StarletteHTTPException)
async def manejar_error_http(request: Request, error: StarletteHTTPException):
    if error.status_code == 400:
        return JSONResponse(status_code=422, content={"codigo": "SOLICITUD_INVALIDA",
                                                      "detail": "El cuerpo de la solicitud no es un JSON válido",
                                                      "errores": []})
    if isinstance(error.detail, dict):
        contenido = error.detail
    else:
        contenido = {"codigo": "ERROR_HTTP", "detail": str(error.detail)}
    return JSONResponse(status_code=error.status_code, content=contenido, headers=getattr(error, "headers", None))


@app.exception_handler(OverflowError)
async def manejar_numero_fuera_de_rango(request: Request, error: OverflowError):
    return JSONResponse(status_code=422, content={"codigo": "SOLICITUD_INVALIDA",
                                                  "detail": "Un identificador o número está fuera del rango permitido",
                                                  "errores": []})


@app.exception_handler(RequestValidationError)
async def manejar_error_validacion(request: Request, error: RequestValidationError):
    errores = [{"campo": ".".join(str(p) for p in e["loc"]), "mensaje": e["msg"]} for e in error.errors()]
    return JSONResponse(status_code=422, content={"codigo": "SOLICITUD_INVALIDA",
                                                  "detail": "La solicitud tiene datos inválidos", "errores": errores})


class Salud(BaseModel):
    estado: str
    version: str
    modo_prueba: bool


@app.get("/api/salud", response_model=Salud, tags=["Salud"], summary="Estado del servicio")
def salud():
    return Salud(estado="ok", version=config.VERSION, modo_prueba=config.MODO_PRUEBA)


for modulo in (autenticacion, cuentas, transferencias, movimientos, categorias, recargas, servicios, contactos,
               solicitudes, limites, seguridad):
    app.include_router(modulo.router)
if config.MODO_PRUEBA:
    app.include_router(soporte_pruebas.router)

contrato.instalar(app)

app.mount("/static", StaticFiles(directory=CARPETA_WEB / "static"), name="static")


@app.get("/", include_in_schema=False)
def raiz():
    return RedirectResponse("/login")


def _pagina(nombre: str):
    def servir():
        return FileResponse(CARPETA_WEB / f"{nombre}.html")
    return servir


for _nombre in PAGINAS:
    app.add_api_route(f"/{_nombre}", _pagina(_nombre), include_in_schema=False)
