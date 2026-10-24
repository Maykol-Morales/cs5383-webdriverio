"""Configuración de Qolqe a partir de variables de entorno."""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

RUTA_BD = Path(os.getenv("QOLQE_BD", RAIZ / "datos" / "qolqe.db"))
RUTA_PLANTILLA = Path(os.getenv("QOLQE_BD_PLANTILLA", RAIZ / "datos" / "plantilla_carga.db"))

CLAVE_SECRETA = os.getenv("QOLQE_CLAVE_SECRETA", "qolqe-clave-de-desarrollo-no-usar-en-produccion")
ALGORITMO_JWT = "HS256"
MINUTOS_TOKEN = int(os.getenv("QOLQE_MINUTOS_TOKEN", "30"))

MODO_PRUEBA = os.getenv("QOLQE_MODO_PRUEBA", "1") == "1"

VERSION = "1.0.0"
