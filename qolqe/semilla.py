"""Datos semilla de Qolqe.

Los usuarios de carga y su historial (volumen alto) se generan una sola vez en una base
plantilla. Al reiniciar se copia la plantilla y se agregan los datos que dependen de la
fecha actual (deudas, movimientos recientes, bloqueos, programadas, solicitudes, etc.).
"""
import random
import sqlite3
import threading
from datetime import date, datetime, timedelta

from qolqe import config, reloj
from qolqe.bd import VERSION_ESQUEMA, conectar, crear_esquema, version_esquema
from qolqe.credenciales import hash_pin
from qolqe.operaciones import generar_codigo_operacion
from qolqe.reglas.contactos import vencimiento_solicitud
from qolqe.reglas.recargas import proxima_ejecucion

DIAS_VIGENCIA_PLANTILLA = 7
USUARIOS_DE_CARGA = 200
MOVIMIENTOS_POR_USUARIO_DE_CARGA = 1000
PIN_USUARIOS_DE_CARGA = "2580"

EMPRESAS = [
    ("ELECTRO", "Electro Andina", "Luz"),
    ("AGUA", "Agua Clara", "Agua"),
    ("INTERNET", "NetAndes", "Internet"),
]

VERSION_PLANTILLA = "2"

# (id, dni, nombres, celular, correo, pin actual, pines anteriores, saldo, límite diario, estado)
USUARIOS_BASE = [
    (1, "45678912", "Ana Torres Quispe", "987654321", "ana.torres@correo.pe", "4826", ["1357", "2468"], 150000, 200000, "ACTIVA"),
    (2, "40123456", "Bruno Díaz Mendoza", "912345678", "bruno.diaz@correo.pe", "7391", [], 80000, 200000, "ACTIVA"),
    (3, "47896541", "Carla Ramos Huamán", "956781234", "carla.ramos@correo.pe", "5917", [], 5000, 200000, "ACTIVA"),
    (4, "41239876", "Diego Salas Paredes", "998877665", "diego.salas@correo.pe", "3604", [], 250000, 100000, "ACTIVA"),
    (5, "46543210", "Elena Vargas Ccori", "923456789", "elena.vargas@correo.pe", "8152", [], 30000, 200000, "ACTIVA"),
    (6, "43215678", "Fabián Rojas Núñez", "934567812", "fabian.rojas@correo.pe", "6029", [], 0, 200000, "CERRADA"),
]
DISPOSITIVO_ANA = "a1b2c3d4e5f60718"

_bloqueo = threading.Lock()


def _texto(momento: datetime) -> str:
    return reloj.a_texto(momento)


def _plantilla_vigente() -> bool:
    if not config.RUTA_PLANTILLA.exists():
        return False
    try:
        with sqlite3.connect(config.RUTA_PLANTILLA) as conexion:
            fila = conexion.execute("SELECT valor FROM meta WHERE clave = 'creada'").fetchone()
            version = conexion.execute("SELECT valor FROM meta WHERE clave = 'version'").fetchone()
    except sqlite3.Error:
        return False
    if fila is None or version is None or version[0] != VERSION_PLANTILLA:
        return False
    return (date.today() - date.fromisoformat(fila[0])).days < DIAS_VIGENCIA_PLANTILLA


def _construir_plantilla() -> None:
    config.RUTA_PLANTILLA.parent.mkdir(parents=True, exist_ok=True)
    temporal = config.RUTA_PLANTILLA.with_suffix(".tmp")
    temporal.unlink(missing_ok=True)
    conexion = sqlite3.connect(temporal)
    crear_esquema(conexion)
    conexion.execute("CREATE TABLE meta (clave TEXT PRIMARY KEY, valor TEXT)")
    conexion.execute("INSERT INTO meta VALUES ('creada', ?)", (date.today().isoformat(),))
    conexion.execute("INSERT INTO meta VALUES ('version', ?)", (VERSION_PLANTILLA,))
    conexion.executemany("INSERT INTO empresas_servicio VALUES (?, ?, ?)", EMPRESAS)

    base = datetime.now(reloj.ZONA_LIMA).replace(microsecond=0) - timedelta(days=200)
    for uid, dni, nombres, celular, correo, pin, anteriores, saldo, limite, estado in USUARIOS_BASE:
        pin_hash = hash_pin(pin)
        cerrada = _texto(base + timedelta(days=150)) if estado == "CERRADA" else None
        conexion.execute(
            """INSERT INTO usuarios (id, dni, nombres, celular, correo, pin_hash, estado, cerrada_en, creado_en)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (uid, dni, nombres, celular, correo, pin_hash, estado, cerrada, _texto(base)),
        )
        conexion.execute("INSERT INTO cuentas VALUES (?, ?, ?)", (uid, saldo, _texto(base)))
        conexion.execute("INSERT INTO limites (usuario_id, limite_diario_cent) VALUES (?, ?)", (uid, limite))
        for indice, anterior in enumerate(anteriores):
            conexion.execute("INSERT INTO historial_pin (usuario_id, pin_hash, creado_en) VALUES (?, ?, ?)",
                             (uid, hash_pin(anterior), _texto(base + timedelta(days=indice))))
        conexion.execute("INSERT INTO historial_pin (usuario_id, pin_hash, creado_en) VALUES (?, ?, ?)",
                         (uid, pin_hash, _texto(base + timedelta(days=len(anteriores)))))

    _usuarios_de_carga(conexion)
    conexion.commit()
    conexion.close()
    temporal.replace(config.RUTA_PLANTILLA)


def _usuarios_de_carga(conexion: sqlite3.Connection) -> None:
    """Usuarios para pruebas de rendimiento: celulares 900000001 a 900000200, PIN 2580."""
    azar = random.Random(2026)
    pin_hash = hash_pin(PIN_USUARIOS_DE_CARGA)
    ahora = datetime.now(reloj.ZONA_LIMA).replace(microsecond=0)
    creado = _texto(ahora - timedelta(days=200))
    tipos = [("RECARGA", "REC", -1), ("PAGO_SERVICIO", "PAG", -1),
             ("TRANSFERENCIA_ENVIADA", "TRF", -1), ("TRANSFERENCIA_RECIBIDA", "TRF", 1)]
    for n in range(1, USUARIOS_DE_CARGA + 1):
        uid = len(USUARIOS_BASE) + n
        celular = f"9{n:08d}"
        conexion.execute(
            "INSERT INTO usuarios (id, dni, nombres, celular, pin_hash, creado_en) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, f"7{n:07d}", f"Usuario Carga {n:03d}", celular, pin_hash, creado),
        )
        conexion.execute("INSERT INTO cuentas VALUES (?, ?, ?)", (uid, 1_000_000, creado))
        conexion.execute("INSERT INTO limites (usuario_id, limite_diario_cent) VALUES (?, ?)", (uid, 200000))
        conexion.execute("INSERT INTO historial_pin (usuario_id, pin_hash, creado_en) VALUES (?, ?, ?)", (uid, pin_hash, creado))
        filas = []
        for _ in range(MOVIMIENTOS_POR_USUARIO_DE_CARGA):
            momento = ahora - timedelta(seconds=azar.randint(3600, 120 * 86400))
            tipo, prefijo, signo = azar.choices(tipos, weights=[3, 2, 3, 2])[0]
            monto = azar.randint(5, 300) * 100
            filas.append((uid, generar_codigo_operacion(prefijo, uid, momento), tipo, f"Movimiento {tipo.lower()}",
                          None, monto, 0, signo * monto, _texto(momento)))
        conexion.executemany(
            """INSERT INTO movimientos (usuario_id, codigo_operacion, tipo, descripcion, contraparte,
                                        monto_cent, comision_cent, importe_cent, fecha)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            filas,
        )


def _datos_relativos(conexion: sqlite3.Connection, ahora: datetime) -> None:
    hoy = ahora.date()

    deudas = [
        ("ELECTRO", "10000001", "Ana Torres Quispe", 12000, 10),
        ("ELECTRO", "10000002", "Ana Torres Quispe", 8550, 0),
        ("ELECTRO", "10000003", "Bruno Díaz Mendoza", 20000, -1),
        ("AGUA", "20000004", "Carla Ramos Huamán", 6420, -10),
        ("AGUA", "20000005", "Diego Salas Paredes", 15000, -30),
        ("INTERNET", "300000000006", "Elena Vargas Ccori", 9990, -60),
        ("INTERNET", "300000000007", "Ana Torres Quispe", 9990, -61),
        ("AGUA", "2000000008", "Bruno Díaz Mendoza", 4500, 3),
        ("ELECTRO", "100000009", "Diego Salas Paredes", 7830, -5),
        ("ELECTRO", "100000009", "Diego Salas Paredes", 8120, 25),
    ]
    for empresa, suministro, titular, monto, dias in deudas:
        vencimiento = hoy + timedelta(days=dias)
        conexion.execute(
            "INSERT INTO deudas (empresa, suministro, titular, periodo, monto_cent, vencimiento) VALUES (?, ?, ?, ?, ?, ?)",
            (empresa, suministro, titular, f"{vencimiento:%Y-%m}", monto, vencimiento.isoformat()),
        )
    conexion.executemany(
        "INSERT INTO deudas (empresa, suministro, titular, periodo, monto_cent, vencimiento) VALUES (?, ?, ?, ?, ?, ?)",
        [("AGUA", f"40000{n:05d}", f"Usuario Carga {n:03d}", f"{hoy:%Y-%m}", 5000 + n * 10,
          (hoy - timedelta(days=5)).isoformat()) for n in range(1, USUARIOS_DE_CARGA + 1)],
    )

    conexion.executemany(
        "INSERT INTO contactos (usuario_id, contacto_usuario_id, alias, favorito, creado_en) VALUES (?, ?, ?, ?, ?)",
        [(1, 2, "Bruno", 1, _texto(ahora - timedelta(days=40))),
         (1, 3, "Prima Carla", 0, _texto(ahora - timedelta(days=20))),
         (2, 1, "Ana", 0, _texto(ahora - timedelta(days=40))),
         (3, 1, "Prima Ana", 0, _texto(ahora - timedelta(days=20))),
         (4, 6, "Fabián", 0, _texto(ahora - timedelta(days=90)))],
    )

    azar = random.Random(9)
    movimientos = []
    for dias in range(58, 0, -3):
        momento = (ahora - timedelta(days=dias)).replace(hour=azar.randint(8, 21), minute=azar.randint(0, 59))
        opcion = dias % 4
        if opcion == 0:
            monto = azar.choice([1000, 2000, 3000, 5000])
            movimientos.append((1, generar_codigo_operacion("REC", 1, momento), "RECARGA", "Recarga al 987111222",
                                "987111222", monto, 0, -monto, _texto(momento)))
        elif opcion == 1:
            monto = azar.randint(40, 180) * 100
            movimientos.append((1, generar_codigo_operacion("PAG", 1, momento), "PAGO_SERVICIO",
                                "Pago Electro Andina", "10000001", monto, 0, -monto, _texto(momento)))
        elif opcion == 2:
            monto = azar.randint(20, 150) * 100
            codigo = generar_codigo_operacion("TRF", 2, momento)
            movimientos.append((1, codigo, "TRANSFERENCIA_RECIBIDA", "Transferencia de Bruno D.",
                                "912345678", monto, 0, monto, _texto(momento)))
            movimientos.append((2, codigo, "TRANSFERENCIA_ENVIADA", "Transferencia a Ana T.",
                                "987654321", monto, 0, -monto, _texto(momento)))
        else:
            monto = azar.randint(10, 90) * 100
            codigo = generar_codigo_operacion("TRF", 1, momento)
            movimientos.append((1, codigo, "TRANSFERENCIA_ENVIADA", "Transferencia a Carla R.",
                                "956781234", monto, 0, -monto, _texto(momento)))
            movimientos.append((3, codigo, "TRANSFERENCIA_RECIBIDA", "Transferencia de Ana T.",
                                "987654321", monto, 0, monto, _texto(momento)))

    momento_hoy = max(ahora - timedelta(hours=1), ahora.replace(hour=0, minute=1, second=0))
    if momento_hoy > ahora:
        momento_hoy = ahora
    codigo_hoy = generar_codigo_operacion("REC", 1, momento_hoy)
    movimientos.append((1, codigo_hoy, "RECARGA", "Recarga al 999000111", "999000111", 1000, 0, -1000, _texto(momento_hoy)))
    conexion.execute(
        "INSERT INTO recargas (codigo_operacion, usuario_id, celular, monto_cent, bono_cent, fecha) VALUES (?, 1, '999000111', 1000, 0, ?)",
        (codigo_hoy, _texto(momento_hoy)),
    )
    conexion.executemany(
        """INSERT INTO movimientos (usuario_id, codigo_operacion, tipo, descripcion, contraparte,
                                    monto_cent, comision_cent, importe_cent, fecha)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        movimientos,
    )

    _datos_de_modulos(conexion, ahora)
    conexion.execute("UPDATE usuarios SET bloqueado_hasta = ? WHERE id = 5", (_texto(ahora + timedelta(minutes=15)),))
    conexion.execute("UPDATE cuentas SET actualizado_en = ? WHERE usuario_id <= ?", (_texto(ahora), len(USUARIOS_BASE)))


def _datos_de_modulos(conexion: sqlite3.Connection, ahora: datetime) -> None:
    """Programadas, afiliaciones, categorías, solicitudes, alertas y dispositivos de ejemplo."""
    hoy = ahora.date()
    creado = _texto(ahora - timedelta(days=30))

    conexion.executemany(
        """INSERT INTO recargas_programadas (usuario_id, celular, monto_cent, dia, alias, estado, proxima_ejecucion, creada_en)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [(1, "987111222", 2000, 15, "Mamá", "ACTIVA", proxima_ejecucion(15, hoy).isoformat(), creado),
         (1, "999000111", 1000, 5, "Trabajo", "PAUSADA", proxima_ejecucion(5, hoy).isoformat(), creado)],
    )

    conexion.executemany(
        "INSERT INTO afiliaciones (usuario_id, empresa, suministro, alias, debito_automatico, creada_en) VALUES (?, ?, ?, ?, ?, ?)",
        [(1, "ELECTRO", "10000001", "Luz casa", 0, creado),
         (1, "AGUA", "2000000008", "Agua depa", 1, creado),
         (1, "INTERNET", "300000000007", "Internet casa", 0, creado)],
    )

    categorias = {}
    for nombre, color in (("Servicios", "#1E88E5"), ("Familia", "#43A047"), ("Comida", "#E53935")):
        categorias[nombre] = conexion.execute(
            "INSERT INTO categorias (usuario_id, nombre, color, creada_en) VALUES (1, ?, ?, ?)", (nombre, color, creado)
        ).lastrowid
    conexion.execute("UPDATE movimientos SET categoria_id = ? WHERE usuario_id = 1 AND tipo = 'PAGO_SERVICIO'",
                     (categorias["Servicios"],))
    conexion.execute(
        "UPDATE movimientos SET categoria_id = ? WHERE usuario_id = 1 AND tipo = 'TRANSFERENCIA_ENVIADA' AND contraparte = '956781234'",
        (categorias["Familia"],),
    )
    conexion.execute(
        """UPDATE movimientos SET nota = 'Cumpleaños de Carla' WHERE id = (
               SELECT id FROM movimientos WHERE usuario_id = 1 AND contraparte = '956781234' ORDER BY fecha DESC LIMIT 1)"""
    )

    solicitudes = [
        (2, 1, 4500, "Almuerzo del viernes", ahora - timedelta(hours=2)),
        (3, 1, 3000, "Entradas al cine", ahora - timedelta(hours=50)),
        (1, 2, 2000, "Taxi al aeropuerto", ahora - timedelta(hours=1)),
    ]
    conexion.executemany(
        "INSERT INTO solicitudes (solicitante_id, destinatario_id, monto_cent, motivo, creada_en, vence_en) VALUES (?, ?, ?, ?, ?, ?)",
        [(origen, destino, monto, motivo, _texto(creada), _texto(vencimiento_solicitud(creada)))
         for origen, destino, monto, motivo, creada in solicitudes],
    )

    conexion.execute("INSERT INTO alertas (usuario_id, tipo, umbral_cent, creada_en) VALUES (1, 'TRANSFERENCIAS', 30000, ?)",
                     (creado,))
    conexion.execute("INSERT INTO dispositivos (id, usuario_id, nombre, tipo, registrado_en) VALUES (?, 1, ?, ?, ?)",
                     (DISPOSITIVO_ANA, "Celular de Ana", "CELULAR", creado))


def reiniciar_datos() -> None:
    with _bloqueo:
        if not _plantilla_vigente():
            _construir_plantilla()
        config.RUTA_BD.parent.mkdir(parents=True, exist_ok=True)
        origen = sqlite3.connect(config.RUTA_PLANTILLA)
        destino = sqlite3.connect(config.RUTA_BD, timeout=30)
        origen.backup(destino)
        origen.close()
        destino.execute("DROP TABLE IF EXISTS meta")
        destino.execute("PRAGMA journal_mode = WAL")
        destino.commit()
        destino.close()

        conexion = conectar()
        _datos_relativos(conexion, reloj.ahora())
        conexion.commit()
        conexion.close()


def inicializar_si_es_necesario() -> None:
    if not config.RUTA_BD.exists():
        reiniciar_datos()
        return
    conexion = conectar()
    desactualizada = version_esquema(conexion) != VERSION_ESQUEMA
    conexion.close()
    if desactualizada:
        reiniciar_datos()
