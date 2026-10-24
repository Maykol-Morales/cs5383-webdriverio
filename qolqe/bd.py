"""Acceso a la base de datos SQLite."""
import sqlite3
from collections.abc import Iterator

from qolqe import config

ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dni TEXT NOT NULL,
    nombres TEXT NOT NULL,
    celular TEXT NOT NULL UNIQUE,
    correo TEXT,
    pin_hash TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'ACTIVA',
    cerrada_en TEXT,
    intentos_fallidos INTEGER NOT NULL DEFAULT 0,
    bloqueado_hasta TEXT,
    creado_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cuentas (
    usuario_id INTEGER PRIMARY KEY REFERENCES usuarios(id),
    saldo_cent INTEGER NOT NULL,
    actualizado_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS limites (
    usuario_id INTEGER PRIMARY KEY REFERENCES usuarios(id),
    limite_diario_cent INTEGER NOT NULL,
    limite_pendiente_cent INTEGER,
    pendiente_desde TEXT
);
CREATE TABLE IF NOT EXISTS movimientos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    codigo_operacion TEXT NOT NULL,
    tipo TEXT NOT NULL,
    descripcion TEXT NOT NULL,
    contraparte TEXT,
    monto_cent INTEGER NOT NULL,
    comision_cent INTEGER NOT NULL DEFAULT 0,
    importe_cent INTEGER NOT NULL,
    fecha TEXT NOT NULL,
    categoria_id INTEGER REFERENCES categorias(id),
    nota TEXT
);
CREATE INDEX IF NOT EXISTS ix_movimientos_usuario_fecha ON movimientos(usuario_id, fecha);
CREATE INDEX IF NOT EXISTS ix_movimientos_codigo ON movimientos(codigo_operacion);
CREATE TABLE IF NOT EXISTS transferencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_operacion TEXT NOT NULL,
    origen_id INTEGER NOT NULL REFERENCES usuarios(id),
    destino_id INTEGER REFERENCES usuarios(id),
    cci_destino TEXT,
    tipo TEXT NOT NULL,
    monto_cent INTEGER NOT NULL,
    comision_cent INTEGER NOT NULL,
    descripcion TEXT,
    fecha TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_transferencias_origen_fecha ON transferencias(origen_id, fecha);
CREATE TABLE IF NOT EXISTS recargas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_operacion TEXT NOT NULL,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    celular TEXT NOT NULL,
    monto_cent INTEGER NOT NULL,
    bono_cent INTEGER NOT NULL,
    fecha TEXT NOT NULL,
    origen TEXT NOT NULL DEFAULT 'MANUAL',
    programada_id INTEGER
);
CREATE TABLE IF NOT EXISTS recargas_programadas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    celular TEXT NOT NULL,
    monto_cent INTEGER NOT NULL,
    dia INTEGER NOT NULL,
    alias TEXT,
    estado TEXT NOT NULL DEFAULT 'ACTIVA',
    proxima_ejecucion TEXT NOT NULL,
    ultimo_resultado TEXT,
    ultimo_detalle TEXT,
    ultima_ejecucion_en TEXT,
    creada_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS empresas_servicio (
    codigo TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    rubro TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deudas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa TEXT NOT NULL REFERENCES empresas_servicio(codigo),
    suministro TEXT NOT NULL,
    titular TEXT NOT NULL,
    periodo TEXT NOT NULL,
    monto_cent INTEGER NOT NULL,
    vencimiento TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'PENDIENTE',
    pagada_en TEXT
);
CREATE INDEX IF NOT EXISTS ix_deudas_suministro ON deudas(empresa, suministro);
CREATE TABLE IF NOT EXISTS pagos_servicio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_operacion TEXT NOT NULL,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    deuda_id INTEGER NOT NULL REFERENCES deudas(id),
    monto_cent INTEGER NOT NULL,
    mora_cent INTEGER NOT NULL,
    total_cent INTEGER NOT NULL,
    fecha TEXT NOT NULL,
    origen TEXT NOT NULL DEFAULT 'MANUAL'
);
CREATE TABLE IF NOT EXISTS afiliaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    empresa TEXT NOT NULL REFERENCES empresas_servicio(codigo),
    suministro TEXT NOT NULL,
    alias TEXT NOT NULL,
    debito_automatico INTEGER NOT NULL DEFAULT 0,
    creada_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS categorias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    nombre TEXT NOT NULL,
    color TEXT NOT NULL,
    creada_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS contactos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    contacto_usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    alias TEXT NOT NULL,
    favorito INTEGER NOT NULL DEFAULT 0,
    creado_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS solicitudes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    solicitante_id INTEGER NOT NULL REFERENCES usuarios(id),
    destinatario_id INTEGER NOT NULL REFERENCES usuarios(id),
    monto_cent INTEGER NOT NULL,
    motivo TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'PENDIENTE',
    creada_en TEXT NOT NULL,
    vence_en TEXT NOT NULL,
    resuelta_en TEXT,
    motivo_rechazo TEXT,
    codigo_operacion TEXT
);
CREATE TABLE IF NOT EXISTS alertas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    tipo TEXT NOT NULL,
    umbral_cent INTEGER NOT NULL,
    estado TEXT NOT NULL DEFAULT 'ACTIVA',
    ultima_notificacion TEXT,
    creada_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dispositivos (
    id TEXT PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    nombre TEXT NOT NULL,
    tipo TEXT NOT NULL,
    registrado_en TEXT NOT NULL,
    ultimo_ingreso TEXT
);
CREATE TABLE IF NOT EXISTS sesiones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    jti TEXT NOT NULL UNIQUE,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    dispositivo_id TEXT,
    iniciada_en TEXT NOT NULL,
    expira_en TEXT NOT NULL,
    cerrada_en TEXT
);
CREATE INDEX IF NOT EXISTS ix_sesiones_usuario ON sesiones(usuario_id);
CREATE TABLE IF NOT EXISTS historial_pin (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    pin_hash TEXT NOT NULL,
    creado_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tokens_revocados (
    jti TEXT PRIMARY KEY,
    revocado_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS codigos_desbloqueo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    codigo TEXT NOT NULL,
    expira_en TEXT NOT NULL,
    intentos INTEGER NOT NULL DEFAULT 0,
    estado TEXT NOT NULL DEFAULT 'ACTIVO'
);
CREATE TABLE IF NOT EXISTS notificaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    celular TEXT NOT NULL,
    mensaje TEXT NOT NULL,
    fecha TEXT NOT NULL
);
"""

VERSION_ESQUEMA = 2


def conectar() -> sqlite3.Connection:
    config.RUTA_BD.parent.mkdir(parents=True, exist_ok=True)
    conexion = sqlite3.connect(config.RUTA_BD, timeout=10, check_same_thread=False)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    conexion.execute("PRAGMA busy_timeout = 10000")
    return conexion


def obtener_bd() -> Iterator[sqlite3.Connection]:
    """Dependencia de FastAPI: una conexión por solicitud, con commit al final."""
    conexion = conectar()
    try:
        yield conexion
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def crear_esquema(conexion: sqlite3.Connection) -> None:
    conexion.executescript(ESQUEMA)
    conexion.execute(f"PRAGMA user_version = {VERSION_ESQUEMA}")


def version_esquema(conexion: sqlite3.Connection) -> int:
    return conexion.execute("PRAGMA user_version").fetchone()[0]
