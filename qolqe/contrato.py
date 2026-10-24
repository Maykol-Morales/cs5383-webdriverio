"""Contrato OpenAPI de Qolqe Wallet.

Completa el esquema que genera FastAPI con la información del contrato:
descripción de cada operación (con su historia de usuario), respuestas de error posibles
con su código estable, restricciones y formatos de cada campo, y ejemplos.

Las restricciones documentadas aquí corresponden a la especificación (docs/requisitos.md).
La API las valida en sus reglas de negocio y responde con el código de error indicado.
"""
from copy import deepcopy

from fastapi.openapi.utils import get_openapi

# ======================================================================= formatos reutilizables

PATRON_MONTO = r"^-?\d+\.\d{2}$"
PATRON_FECHA_HORA = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$"
PATRON_FECHA = r"^\d{4}-\d{2}-\d{2}$"

MONTO_SALIDA = {"pattern": PATRON_MONTO, "description": "Monto en soles con 2 decimales"}
FECHA_HORA = {"pattern": PATRON_FECHA_HORA, "description": "Fecha y hora de Lima (UTC-5), formato AAAA-MM-DDTHH:MM:SS",
              "examples": ["2026-10-09T10:15:00"]}
FECHA = {"format": "date", "pattern": PATRON_FECHA, "description": "Fecha, formato AAAA-MM-DD", "examples": ["2026-11-15"]}
CELULAR = {"pattern": r"^9\d{8}$", "minLength": 9, "maxLength": 9,
           "description": "9 dígitos y empieza con 9", "examples": ["912345678"]}
PIN = {"pattern": r"^\d{4}$", "minLength": 4, "maxLength": 4, "description": "PIN de 4 dígitos", "examples": ["4826"]}
CODIGO_OPERACION = {"description": "Código único de operación", "examples": ["TRF26100910150000001"]}
MONTO_ENTRADA = "Monto en soles, como número o texto, mayor a 0 y con máximo 2 decimales"

ESTADOS_SOLICITUD = ["PENDIENTE", "ACEPTADA", "RECHAZADA", "CANCELADA", "VENCIDA"]
TIPOS_MOVIMIENTO = ["TRANSFERENCIA_ENVIADA", "TRANSFERENCIA_RECIBIDA", "RECARGA", "PAGO_SERVICIO"]
TIPOS_ALERTA = ["TRANSFERENCIAS", "RECARGAS", "PAGOS", "TODAS"]
TIPOS_DISPOSITIVO = ["CELULAR", "TABLET", "COMPUTADORA"]
PALETA = ["#E53935", "#FB8C00", "#FDD835", "#43A047", "#00897B", "#1E88E5", "#8E24AA", "#6D4C41"]
MONTOS_RECARGA = "Uno de los montos permitidos: 5, 10, 20, 30, 50 o 100"

# ======================================================================= catálogo de errores

ERRORES = {
    # 401
    "NO_AUTENTICADO": (401, "Falta el token de autenticación, es inválido, venció o su sesión fue cerrada"),
    "CREDENCIALES_INVALIDAS": (401, "Celular o PIN incorrectos"),
    "CUENTA_CERRADA": (401, "La cuenta fue cerrada"),
    # 403
    "OPERACION_RECHAZADA": (403, "La operación fue rechazada por seguridad"),
    # 404
    "AFILIACION_NO_ENCONTRADA": (404, "La afiliación no existe"),
    "ALERTA_NO_ENCONTRADA": (404, "La alerta no existe"),
    "CATEGORIA_NO_ENCONTRADA": (404, "La categoría no existe"),
    "CELULAR_NO_REGISTRADO": (404, "El celular no está registrado en Qolqe"),
    "CONTACTO_NO_ENCONTRADO": (404, "El contacto no existe"),
    "DESTINO_NO_REGISTRADO": (404, "El celular de destino no está registrado en Qolqe"),
    "DEUDA_NO_ENCONTRADA": (404, "La deuda no existe"),
    "DISPOSITIVO_NO_ENCONTRADO": (404, "El dispositivo no existe"),
    "EMPRESA_NO_ENCONTRADA": (404, "La empresa no existe"),
    "MOVIMIENTO_NO_ENCONTRADO": (404, "El movimiento no existe"),
    "PAGO_NO_ENCONTRADO": (404, "El pago no existe"),
    "PROGRAMADA_NO_ENCONTRADA": (404, "La recarga programada no existe"),
    "SESION_NO_ENCONTRADA": (404, "La sesión no existe o ya fue cerrada"),
    "SIN_DEUDA_PENDIENTE": (404, "El suministro no tiene deudas pendientes"),
    "SOLICITUD_NO_ENCONTRADA": (404, "La solicitud no existe"),
    "SUMINISTRO_NO_ENCONTRADO": (404, "El suministro no existe en la empresa"),
    "USUARIO_NO_ENCONTRADO": (404, "No existe un usuario con ese celular"),
    # 409
    "AFILIACION_DUPLICADA": (409, "Ya tienes afiliado ese suministro"),
    "ALERTA_DUPLICADA": (409, "Ya tienes una alerta con ese tipo y umbral"),
    "ALIAS_DUPLICADO": (409, "Ya tienes un contacto con ese alias"),
    "CATEGORIA_DUPLICADA": (409, "Ya tienes una categoría con ese nombre"),
    "CELULAR_REGISTRADO": (409, "El celular ya está registrado"),
    "CONTACTO_EXISTENTE": (409, "Ese celular ya está en tus contactos"),
    "CORREO_REGISTRADO": (409, "El correo ya está registrado en otra cuenta"),
    "DEBITO_ACTIVO": (409, "Desactiva el débito automático antes de desafiliar el servicio"),
    "DEUDA_YA_PAGADA": (409, "La deuda ya fue pagada"),
    "DISPOSITIVO_DUPLICADO": (409, "Ya tienes un dispositivo con ese nombre"),
    "ESTADO_INVALIDO": (409, "La operación no está permitida en el estado actual"),
    "PROGRAMACION_DUPLICADA": (409, "Ya tienes una recarga programada a ese número ese día"),
    "SOLICITUDES_PENDIENTES": (409, "Tienes solicitudes de dinero pendientes"),
    # 423
    "CUENTA_BLOQUEADA": (423, "Tu cuenta está bloqueada hasta las 10:45. Puedes solicitar un código de desbloqueo."),
    # 422
    "AFILIACION_INVALIDA": (422, "El alias debe tener entre 3 y 20 caracteres"),
    "ALERTA_INVALIDA": (422, "El umbral debe ser múltiplo de S/ 10"),
    "ALIAS_INVALIDO": (422, "El alias debe tener entre 3 y 20 caracteres"),
    "CATEGORIA_INVALIDA": (422, "El nombre de la categoría debe tener entre 3 y 20 caracteres"),
    "CCI_INVALIDO": (422, "El CCI debe tener 20 dígitos"),
    "CELULAR_INVALIDO": (422, "El celular debe tener 9 dígitos y empezar con 9"),
    "CODIGO_ANULADO": (422, "Superaste los intentos permitidos. Solicita un nuevo código"),
    "CODIGO_EXPIRADO": (422, "El código expiró. Solicita uno nuevo"),
    "CODIGO_INCORRECTO": (422, "Código incorrecto. Te quedan 2 intentos"),
    "CODIGO_INVALIDO": (422, "No hay un código de desbloqueo activo para este celular"),
    "CONTACTO_PROPIO": (422, "No puedes agregarte como contacto"),
    "CORREO_INVALIDO": (422, "El correo no tiene un formato válido"),
    "DESTINO_INACTIVO": (422, "La cuenta de destino está cerrada"),
    "DESTINO_REQUERIDO": (422, "Indica el celular de destino o un contacto"),
    "DEUDA_EN_COBRANZA": (422, "Deuda enviada a cobranza. Comunícate con la empresa."),
    "DISPOSITIVO_INVALIDO": (422, "El nombre del dispositivo debe tener entre 3 y 30 caracteres"),
    "DNI_INVALIDO": (422, "El DNI debe tener exactamente 8 dígitos"),
    "FILTRO_INVALIDO": (422, "El rango máximo de consulta es de 90 días"),
    "LIMITE_AFILIACIONES": (422, "Solo puedes afiliar 8 servicios"),
    "LIMITE_ALERTAS": (422, "Solo puedes tener 5 alertas"),
    "LIMITE_CATEGORIAS": (422, "Solo puedes tener 10 categorías"),
    "LIMITE_CONTACTOS": (422, "Solo se permiten 15 contactos"),
    "LIMITE_DIARIO_EXCEDIDO": (422, "La operación supera tu límite diario de S/ 2000.00"),
    "LIMITE_DISPOSITIVOS": (422, "Solo puedes registrar 3 dispositivos"),
    "LIMITE_FAVORITOS": (422, "Solo puedes tener 5 contactos favoritos"),
    "LIMITE_INVALIDO": (422, "El límite diario debe ser múltiplo de S/ 50"),
    "LIMITE_PROGRAMADAS": (422, "Solo puedes tener 3 recargas programadas activas"),
    "LIMITE_RECARGAS": (422, "Alcanzaste el máximo de recargas diarias a este número"),
    "LIMITE_SOLICITUDES": (422, "Solo puedes tener 10 solicitudes pendientes enviadas"),
    "MONTO_INVALIDO": (422, "El monto supera el límite por operación de S/ 500.00"),
    "MONTO_NO_PERMITIDO": (422, "Monto no permitido. Montos válidos: S/ 5, 10, 20, 30, 50, 100"),
    "NOTA_INVALIDA": (422, "La nota admite como máximo 100 caracteres"),
    "PERFIL_INVALIDO": (422, "Los nombres deben tener entre 2 y 80 caracteres"),
    "PIN_ACTUAL_INCORRECTO": (422, "El PIN actual no es correcto"),
    "PIN_INCORRECTO": (422, "El PIN no es correcto"),
    "PIN_INVALIDO": (422, "El PIN no puede ser una secuencia de dígitos"),
    "PIN_REUTILIZADO": (422, "El nuevo PIN no puede ser igual a uno de tus últimos 3 PIN"),
    "PROGRAMACION_INVALIDA": (422, "El día de ejecución debe estar entre 1 y 28"),
    "SALDO_INSUFICIENTE": (422, "Saldo insuficiente para realizar la operación"),
    "SALDO_INVALIDO": (422, "El saldo no puede ser negativo"),
    "SALDO_PENDIENTE": (422, "Para cerrar tu cuenta el saldo debe ser S/ 0.00"),
    "SOLICITUD_INVALIDA": (422, "La solicitud tiene datos inválidos"),
    "SUMINISTRO_INVALIDO": (422, "El código de suministro debe tener entre 8 y 12 dígitos"),
    "TRANSFERENCIA_A_SI_MISMO": (422, "No puedes transferirte a ti mismo"),
}

DESCRIPCION_ESTADOS = {
    401: "No autenticado",
    403: "Rechazada por seguridad",
    404: "Recurso inexistente o de otro usuario",
    409: "Conflicto con el estado actual",
    422: "Datos inválidos o regla de negocio incumplida",
    423: "Cuenta bloqueada",
}

ERRORES_TRANSFERENCIA = ["MONTO_INVALIDO", "SALDO_INSUFICIENTE", "LIMITE_DIARIO_EXCEDIDO", "OPERACION_RECHAZADA"]

# ======================================================================= operaciones

OPERACIONES = {
    # ------------------------------------------------------------- núcleo
    ("post", "/api/usuarios"): {
        "hu": "HU-N-01", "respuesta": "Cuenta creada con saldo S/ 0.00 y límite diario de S/ 2,000.00",
        "descripcion": "Registra un cliente. El DNI debe tener 8 dígitos; el celular debe ser único y el PIN debe cumplir "
                       "el formato requerido. Los nombres admiten de 2 a 80 caracteres y el correo es opcional y único "
                       "entre cuentas activas, sin distinguir mayúsculas. "
                       "Envía un SMS de bienvenida.",
        "errores": ["DNI_INVALIDO", "CELULAR_INVALIDO", "PIN_INVALIDO", "CORREO_INVALIDO", "CELULAR_REGISTRADO",
                    "CORREO_REGISTRADO"],
    },
    ("post", "/api/auth/login"): {
        "hu": "HU-N-02", "respuesta": "Credenciales correctas: token JWT (30 minutos) y sesión creada",
        "descripcion": "Inicia sesión y crea una sesión activa. Tras 3 intentos fallidos consecutivos, la cuenta se bloquea "
                       "durante 15 minutos. Si se envía un `dispositivo_id` que no pertenece a un dispositivo de confianza del "
                       "usuario, se permite el ingreso y se envía un SMS de alerta de nuevo dispositivo.",
        "errores": ["CREDENCIALES_INVALIDAS", "CUENTA_CERRADA", "CUENTA_BLOQUEADA"],
    },
    ("post", "/api/auth/logout"): {
        "hu": "HU-N-03", "respuesta": "Sesión cerrada: el token deja de ser válido",
        "descripcion": "Cierra la sesión del token enviado. No afecta a las demás sesiones del usuario.",
        "errores": [],
    },
    ("get", "/api/cuentas/me"): {
        "hu": "HU-N-04", "respuesta": "Perfil del usuario autenticado (DNI enmascarado)",
        "descripcion": "Devuelve el perfil: nombres, celular, correo y DNI enmascarado (solo los últimos 4 dígitos).",
        "errores": [],
    },
    ("put", "/api/cuentas/me"): {
        "hu": "HU-N-05", "respuesta": "Perfil actualizado",
        "descripcion": "Actualiza solo los campos enviados (nombres, correo). El DNI y el celular no se pueden modificar: "
                       "si se envían, se ignoran. Al cambiar el correo se envía un SMS de aviso.",
        "errores": ["PERFIL_INVALIDO", "CORREO_INVALIDO", "CORREO_REGISTRADO"],
    },
    ("get", "/api/cuentas/me/saldo"): {
        "hu": "HU-N-04", "respuesta": "Saldo disponible",
        "descripcion": "Saldo disponible, moneda (PEN) y fecha de la última actualización.",
        "errores": [],
    },
    ("post", "/api/cuentas/me/cierre"): {
        "hu": "HU-N-06", "respuesta": "Cuenta cerrada y todas sus sesiones cerradas",
        "descripcion": "Cierra la cuenta. Requiere el PIN, saldo exactamente S/ 0.00 y no tener solicitudes de dinero "
                       "pendientes (no vencidas), enviadas o recibidas. Después no se pueden realizar transferencias "
                       "hacia esa cuenta.",
        "errores": ["PIN_INCORRECTO", "SALDO_PENDIENTE", "SOLICITUDES_PENDIENTES"],
    },
    ("get", "/api/transferencias/comision"): {
        "hu": "HU-N-09", "respuesta": "Simulación: monto, comisión y total",
        "descripcion": "Calcula la comisión de una transferencia sin realizarla: S/ 0.00 entre cuentas Qolqe; "
                       "1.5 % a otros bancos, mínimo S/ 1.00 y máximo S/ 5.00, redondeo comercial.",
        "errores": ["MONTO_INVALIDO"],
    },
    ("post", "/api/transferencias"): {
        "hu": "HU-N-07, HU-N-08, HU-G4-05", "respuesta": "Transferencia realizada: comprobante",
        "descripcion": "Transfiere a otro usuario Qolqe (`celular_destino` o `contacto_id`) o a otro banco (`cci`). "
                       "Valida el monto, el límite diario vigente, el destinatario y el saldo disponible, incluida la "
                       "comisión. Las transferencias Qolqe generan movimientos relacionados con el mismo código de "
                       "operación. Las validaciones se mantienen ante solicitudes simultáneas.",
        "errores": ERRORES_TRANSFERENCIA + ["CELULAR_INVALIDO", "CCI_INVALIDO", "DESTINO_REQUERIDO",
                                            "TRANSFERENCIA_A_SI_MISMO", "DESTINO_INACTIVO", "DESTINO_NO_REGISTRADO",
                                            "CONTACTO_NO_ENCONTRADO"],
    },
    # ------------------------------------------------------------- G3 historial y categorías
    ("get", "/api/movimientos"): {
        "hu": "HU-G3-01", "respuesta": "Página de movimientos, del más reciente al más antiguo",
        "descripcion": "Historial con filtros: `desde` ≤ `hasta`, máximo 90 días, `hasta` no futura; por defecto "
                       "los últimos 30 días hasta hoy, incluidos los movimientos de hoy. El rango incluye completos los "
                       "días `desde` y `hasta`. Devuelve 10 movimientos por página.",
        "errores": ["FILTRO_INVALIDO"],
    },
    ("get", "/api/movimientos/recientes"): {
        "hu": "HU-N-04", "respuesta": "Últimos movimientos",
        "descripcion": "Últimos movimientos del usuario, para la pantalla de inicio.",
        "errores": [],
    },
    ("get", "/api/movimientos/exportar"): {
        "hu": "HU-G3-08", "respuesta": "Archivo CSV (UTF-8, separador punto y coma, con encabezado)",
        "descripcion": "Exporta los movimientos con los mismos filtros y reglas de rango del historial, sin paginar. "
                       "Columnas: `fecha;codigo_operacion;tipo;descripcion;monto;comision;importe;categoria;nota`. "
                       "Sin movimientos, el archivo contiene solo el encabezado.",
        "errores": ["FILTRO_INVALIDO"],
    },
    ("get", "/api/movimientos/{codigo_operacion}"): {
        "hu": "HU-G3-02", "respuesta": "Detalle del movimiento",
        "descripcion": "Detalle de **un movimiento propio** por su código de operación. El de otro usuario responde 404.",
        "errores": ["MOVIMIENTO_NO_ENCONTRADO"],
    },
    ("put", "/api/movimientos/{codigo_operacion}/clasificacion"): {
        "hu": "HU-G3-07", "respuesta": "Movimiento clasificado",
        "descripcion": "Asigna o quita una categoría propia y agrega, edita o elimina una nota. Solo se actualizan los "
                       "campos enviados; no se modifican el monto, la fecha ni el tipo del movimiento.",
        "errores": ["MOVIMIENTO_NO_ENCONTRADO", "CATEGORIA_NO_ENCONTRADA", "NOTA_INVALIDA"],
    },
    ("get", "/api/categorias"): {
        "hu": "HU-G3-04", "respuesta": "Categorías en orden alfabético",
        "descripcion": "Categorías del usuario con la cantidad de movimientos asignados.",
        "errores": [],
    },
    ("post", "/api/categorias"): {
        "hu": "HU-G3-03", "respuesta": "Categoría creada",
        "descripcion": "Crea una categoría: máximo 10 por usuario, nombre de 3 a 20 caracteres único sin distinguir "
                       "mayúsculas y color de la paleta fija.",
        "errores": ["CATEGORIA_INVALIDA", "LIMITE_CATEGORIAS", "CATEGORIA_DUPLICADA"],
    },
    ("put", "/api/categorias/{categoria_id}"): {
        "hu": "HU-G3-05", "respuesta": "Categoría actualizada",
        "descripcion": "Cambia el nombre o el color de la categoría; el nombre debe ser único entre las demás categorías.",
        "errores": ["CATEGORIA_NO_ENCONTRADA", "CATEGORIA_INVALIDA", "CATEGORIA_DUPLICADA"],
    },
    ("delete", "/api/categorias/{categoria_id}"): {
        "hu": "HU-G3-06", "respuesta": "Categoría eliminada; sus movimientos quedan sin categoría",
        "descripcion": "Elimina la categoría. Sus movimientos quedan sin categoría; no se borran ni cambian de monto.",
        "errores": ["CATEGORIA_NO_ENCONTRADA"],
    },
    # ------------------------------------------------------------- G1 recargas
    ("get", "/api/recargas/configuracion"): {
        "hu": "HU-G1-01", "respuesta": "Montos permitidos, bono y máximo diario",
        "descripcion": "Devuelve los montos permitidos, el bono aplicable y el máximo diario de recargas. No requiere token.",
        "errores": [],
    },
    ("get", "/api/recargas"): {
        "hu": "HU-G1-02", "respuesta": "Últimas 20 recargas, de la más reciente a la más antigua",
        "descripcion": "Recargas del usuario, manuales y programadas.",
        "errores": [],
    },
    ("post", "/api/recargas"): {
        "hu": "HU-G1-01", "respuesta": "Recarga realizada: comprobante",
        "descripcion": "Recarga un celular con un monto permitido. Las recargas desde S/ 30 reciben un bono "
                       "de 5 % con tope de S/ 4.00. Se permiten hasta 5 recargas por día al mismo número. "
                       "El número recargado recibe un SMS.",
        "errores": ["CELULAR_INVALIDO", "MONTO_NO_PERMITIDO", "LIMITE_RECARGAS", "SALDO_INSUFICIENTE"],
    },
    ("get", "/api/recargas/programadas"): {
        "hu": "HU-G1-04", "respuesta": "Recargas programadas (no eliminadas)",
        "descripcion": "Programadas con su estado, próxima ejecución y resultado de la última ejecución.",
        "errores": [],
    },
    ("post", "/api/recargas/programadas"): {
        "hu": "HU-G1-03", "respuesta": "Recarga programada en estado ACTIVA",
        "descripcion": "Programa una recarga mensual. La próxima ejecución es la siguiente fecha con ese día: este mes si "
                       "el día aún no pasó, o el mes siguiente si ya pasó o es hoy. Se permiten hasta 3 programadas "
                       "ACTIVAS y no se puede repetir número y día.",
        "errores": ["PROGRAMACION_INVALIDA", "PROGRAMACION_DUPLICADA", "LIMITE_PROGRAMADAS"],
    },
    ("put", "/api/recargas/programadas/{programada_id}"): {
        "hu": "HU-G1-05", "respuesta": "Recarga programada actualizada",
        "descripcion": "Cambia el monto, el día o el alias (solo los campos enviados). Si cambia el día, la próxima "
                       "ejecución se recalcula como al crearla.",
        "errores": ["PROGRAMADA_NO_ENCONTRADA", "PROGRAMACION_INVALIDA", "PROGRAMACION_DUPLICADA"],
    },
    ("delete", "/api/recargas/programadas/{programada_id}"): {
        "hu": "HU-G1-06", "respuesta": "Recarga programada eliminada",
        "descripcion": "La programada deja de mostrarse y no se vuelve a ejecutar. Las recargas realizadas se conservan.",
        "errores": ["PROGRAMADA_NO_ENCONTRADA"],
    },
    ("post", "/api/recargas/programadas/{programada_id}/pausar"): {
        "hu": "HU-G1-05", "respuesta": "Recarga programada en estado PAUSADA",
        "descripcion": "Pausa una programada ACTIVA: no se ejecuta mientras esté pausada.",
        "errores": ["PROGRAMADA_NO_ENCONTRADA", "ESTADO_INVALIDO"],
    },
    ("post", "/api/recargas/programadas/{programada_id}/reanudar"): {
        "hu": "HU-G1-05", "respuesta": "Recarga programada en estado ACTIVA",
        "descripcion": "Reanuda una programada PAUSADA, siempre que no se supere el máximo de 3 activas. La próxima ejecución se "
                       "recalcula desde hoy.",
        "errores": ["PROGRAMADA_NO_ENCONTRADA", "ESTADO_INVALIDO", "LIMITE_PROGRAMADAS"],
    },
    # ------------------------------------------------------------- G2 servicios
    ("get", "/api/servicios/empresas"): {
        "hu": "HU-G2-01", "respuesta": "Empresas de servicios",
        "descripcion": "Empresas cuyas deudas se pueden consultar y pagar. No requiere token.",
        "errores": [],
    },
    ("get", "/api/servicios/deudas"): {
        "hu": "HU-G2-01", "respuesta": "Deudas pendientes, de la más antigua a la más reciente",
        "descripcion": "Devuelve las deudas pendientes de un suministro. La mora es de 0.5 % por día de atraso después del "
                       "vencimiento, con tope de 10 %. Con más de 60 días de atraso la deuda está EN_COBRANZA "
                       "y no muestra mora ni total.",
        "errores": ["EMPRESA_NO_ENCONTRADA", "SUMINISTRO_INVALIDO", "SIN_DEUDA_PENDIENTE"],
    },
    ("post", "/api/servicios/pagos"): {
        "hu": "HU-G2-02", "respuesta": "Pago realizado: comprobante",
        "descripcion": "Paga una deuda pendiente por su monto más la mora. Dos pagos simultáneos de la "
                       "misma deuda: solo uno es exitoso.",
        "errores": ["DEUDA_NO_ENCONTRADA", "DEUDA_YA_PAGADA", "DEUDA_EN_COBRANZA", "SALDO_INSUFICIENTE"],
    },
    ("get", "/api/servicios/pagos"): {
        "hu": "HU-G2-07", "respuesta": "Pagos del usuario, del más reciente al más antiguo",
        "descripcion": "Pagos realizados (manuales y por débito automático), opcionalmente filtrados por afiliación.",
        "errores": ["AFILIACION_NO_ENCONTRADA"],
    },
    ("get", "/api/servicios/pagos/{codigo_operacion}"): {
        "hu": "HU-G2-07", "respuesta": "Comprobante del pago",
        "descripcion": "Comprobante de un pago propio. El de otro usuario responde 404.",
        "errores": ["PAGO_NO_ENCONTRADO"],
    },
    ("get", "/api/servicios/afiliaciones"): {
        "hu": "HU-G2-04", "respuesta": "Servicios afiliados",
        "descripcion": "Afiliaciones con total pendiente, próximo vencimiento, débito automático y situación "
                       "(AL_DIA, CON_DEUDA o EN_COBRANZA).",
        "errores": [],
    },
    ("post", "/api/servicios/afiliaciones"): {
        "hu": "HU-G2-03", "respuesta": "Servicio afiliado con débito automático desactivado",
        "descripcion": "Afilia un suministro existente (con al menos un recibo, pendiente o pagado). Máximo 8, sin repetir "
                       "empresa y suministro.",
        "errores": ["EMPRESA_NO_ENCONTRADA", "AFILIACION_INVALIDA", "SUMINISTRO_NO_ENCONTRADO", "LIMITE_AFILIACIONES",
                    "AFILIACION_DUPLICADA"],
    },
    ("put", "/api/servicios/afiliaciones/{afiliacion_id}"): {
        "hu": "HU-G2-05", "respuesta": "Afiliación actualizada",
        "descripcion": "Cambia el alias o activa/desactiva el débito automático (solo los campos enviados). Con el débito "
                       "activo, el proceso diario paga las deudas pendientes el **día de su vencimiento**, sin mora; las "
                       "deudas ya vencidas no se pagan automáticamente.",
        "errores": ["AFILIACION_NO_ENCONTRADA", "AFILIACION_INVALIDA"],
    },
    ("delete", "/api/servicios/afiliaciones/{afiliacion_id}"): {
        "hu": "HU-G2-06", "respuesta": "Servicio desafiliado",
        "descripcion": "Elimina la afiliación; las deudas y los pagos no cambian. Con el débito activo no se puede eliminar.",
        "errores": ["AFILIACION_NO_ENCONTRADA", "DEBITO_ACTIVO"],
    },
    # ------------------------------------------------------------- G4 contactos y solicitudes
    ("get", "/api/contactos"): {
        "hu": "HU-G4-02", "respuesta": "Página de contactos: favoritos primero, luego por alias",
        "descripcion": "Contactos del usuario, 10 por página. La búsqueda por alias no distingue mayúsculas ni tildes.",
        "errores": [],
    },
    ("post", "/api/contactos"): {
        "hu": "HU-G4-01", "respuesta": "Contacto agregado",
        "descripcion": "Agrega un contacto con celular registrado y activo, distinto del propio y sin repetir; alias "
                       "de 3 a 20 caracteres; máximo 15 contactos. Una cuenta cerrada se trata como no registrada.",
        "errores": ["CELULAR_INVALIDO", "CONTACTO_PROPIO", "CELULAR_NO_REGISTRADO", "CONTACTO_EXISTENTE", "ALIAS_INVALIDO",
                    "ALIAS_DUPLICADO", "LIMITE_CONTACTOS"],
    },
    ("put", "/api/contactos/{contacto_id}"): {
        "hu": "HU-G4-03", "respuesta": "Contacto actualizado",
        "descripcion": "Cambia el alias y marca o desmarca el contacto como favorito (máximo 5 favoritos). "
                       "Solo se actualizan los campos enviados.",
        "errores": ["CONTACTO_NO_ENCONTRADO", "ALIAS_INVALIDO", "ALIAS_DUPLICADO", "LIMITE_FAVORITOS"],
    },
    ("delete", "/api/contactos/{contacto_id}"): {
        "hu": "HU-G4-04", "respuesta": "Contacto eliminado",
        "descripcion": "Elimina el contacto. No se puede si hay solicitudes PENDIENTES (no vencidas) con él, enviadas o "
                       "recibidas. Las transferencias realizadas se conservan.",
        "errores": ["CONTACTO_NO_ENCONTRADO", "SOLICITUDES_PENDIENTES"],
    },
    ("get", "/api/solicitudes"): {
        "hu": "HU-G4-07", "respuesta": "Solicitudes enviadas y recibidas",
        "descripcion": "Solicitudes enviadas y recibidas por separado, con filtro opcional por estado. Una solicitud "
                       "PENDIENTE cuyo plazo de 48 horas ya pasó se muestra como VENCIDA.",
        "errores": ["FILTRO_INVALIDO"],
    },
    ("post", "/api/solicitudes"): {
        "hu": "HU-G4-06", "respuesta": "Solicitud creada en estado PENDIENTE (vence en 48 horas)",
        "descripcion": "Pide dinero a un contacto propio con un monto válido y un motivo de 3 a 60 caracteres. Máximo 10 "
                       "solicitudes pendientes enviadas. El destinatario recibe un SMS.",
        "errores": ["CONTACTO_NO_ENCONTRADO", "SOLICITUD_INVALIDA", "DESTINO_INACTIVO", "LIMITE_SOLICITUDES"],
    },
    ("post", "/api/solicitudes/{solicitud_id}/aceptar"): {
        "hu": "HU-G4-08", "respuesta": "Solicitud ACEPTADA, asociada al código de la transferencia",
        "descripcion": "Solo el destinatario (para cualquier otro usuario responde 404) y solo si está PENDIENTE y no "
                       "vencida. Realiza una transferencia al solicitante; si la "
                       "transferencia falla, la solicitud sigue PENDIENTE y se devuelve el error de la transferencia.",
        "errores": ["SOLICITUD_NO_ENCONTRADA", "ESTADO_INVALIDO"] + ERRORES_TRANSFERENCIA,
    },
    ("post", "/api/solicitudes/{solicitud_id}/rechazar"): {
        "hu": "HU-G4-09", "respuesta": "Solicitud RECHAZADA",
        "descripcion": "Solo el destinatario y solo si está PENDIENTE y no vencida. Motivo opcional de hasta 60 caracteres. "
                       "El solicitante recibe un SMS.",
        "errores": ["SOLICITUD_NO_ENCONTRADA", "ESTADO_INVALIDO", "SOLICITUD_INVALIDA"],
    },
    ("post", "/api/solicitudes/{solicitud_id}/cancelar"): {
        "hu": "HU-G4-10", "respuesta": "Solicitud CANCELADA",
        "descripcion": "Solo el solicitante y solo si está PENDIENTE y no vencida.",
        "errores": ["SOLICITUD_NO_ENCONTRADA", "ESTADO_INVALIDO"],
    },
    # ------------------------------------------------------------- G5 límites y alertas
    ("get", "/api/limites"): {
        "hu": "HU-G5-01", "respuesta": "Límites vigentes y consumo del día",
        "descripcion": "Límite por operación (S/ 500.00), límite diario vigente, aumento pendiente, lo usado hoy ("
                       "transferencias Qolqe e interbancarias) y lo disponible.",
        "errores": [],
    },
    ("put", "/api/limites"): {
        "hu": "HU-G5-02", "respuesta": "Cambio aplicado: INMEDIATO o PROGRAMADO",
        "descripcion": "Cambia el límite diario (S/ 100 a S/ 2,000, múltiplos de S/ 50). Una reducción es inmediata "
                       "y cancela cualquier aumento pendiente; un aumento entra en vigencia 24 horas después. "
                       "Una reducción pausa las alertas de TRANSFERENCIAS o TODAS cuyo umbral quede por encima del límite.",
        "errores": ["LIMITE_INVALIDO"],
    },
    ("get", "/api/limites/alertas"): {
        "hu": "HU-G5-05", "respuesta": "Alertas de consumo",
        "descripcion": "Alertas con su estado, el gasto de hoy de su tipo y la fecha de su última notificación.",
        "errores": [],
    },
    ("post", "/api/limites/alertas"): {
        "hu": "HU-G5-04", "respuesta": "Alerta creada en estado ACTIVA",
        "descripcion": "Crea una alerta: máximo 5; umbral de S/ 10 a S/ 2,000 en múltiplos de S/ 10, sin "
                       "repetir tipo + umbral; para TRANSFERENCIAS y TODAS, el umbral no supera el límite diario vigente. "
                       "Cuando una operación hace que el gasto del día alcance el umbral, se envía un SMS (como máximo "
                       "una vez por día por alerta).",
        "errores": ["ALERTA_INVALIDA", "ALERTA_DUPLICADA", "LIMITE_ALERTAS"],
    },
    ("put", "/api/limites/alertas/{alerta_id}"): {
        "hu": "HU-G5-06", "respuesta": "Alerta actualizada",
        "descripcion": "Cambia el umbral y/o el estado (ACTIVA para reanudar, PAUSADA para pausar). Solo se actualizan los "
                       "campos enviados. No se puede reanudar una alerta cuyo umbral supera el límite vigente.",
        "errores": ["ALERTA_NO_ENCONTRADA", "ALERTA_INVALIDA", "ALERTA_DUPLICADA"],
    },
    ("delete", "/api/limites/alertas/{alerta_id}"): {
        "hu": "HU-G5-07", "respuesta": "Alerta eliminada",
        "descripcion": "Elimina la alerta: deja de notificar.",
        "errores": ["ALERTA_NO_ENCONTRADA"],
    },
    # ------------------------------------------------------------- G6 seguridad
    ("put", "/api/seguridad/pin"): {
        "hu": "HU-G6-01", "respuesta": "PIN actualizado",
        "descripcion": "Cambia el PIN: debe cumplir el formato requerido, ser distinto de los últimos 3 PIN (incluido el actual) "
                       "y distinto "
                       "de los últimos 4 dígitos del celular. Envía un SMS y cierra todas las demás sesiones; la actual "
                       "sigue activa.",
        "errores": ["PIN_ACTUAL_INCORRECTO", "PIN_INVALIDO", "PIN_REUTILIZADO"],
    },
    ("post", "/api/seguridad/desbloqueo/solicitar"): {
        "hu": "HU-G6-03", "respuesta": "Respuesta siempre igual, exista o no la cuenta y esté o no bloqueada",
        "descripcion": "Si la cuenta está bloqueada, envía por SMS un código de 6 dígitos que vence a los 5 minutos y admite "
                       "3 intentos. Un código nuevo invalida el anterior. No requiere token.",
        "errores": [],
    },
    ("post", "/api/seguridad/desbloqueo/confirmar"): {
        "hu": "HU-G6-04", "respuesta": "Cuenta desbloqueada",
        "descripcion": "Desbloquea la cuenta con el código vigente. No requiere token.",
        "errores": ["CODIGO_INVALIDO", "CODIGO_EXPIRADO", "CODIGO_INCORRECTO", "CODIGO_ANULADO"],
    },
    ("get", "/api/seguridad/dispositivos"): {
        "hu": "HU-G6-06", "respuesta": "Dispositivos de confianza",
        "descripcion": "Dispositivos con su tipo, fecha de registro y fecha del último inicio de sesión desde cada uno.",
        "errores": [],
    },
    ("post", "/api/seguridad/dispositivos"): {
        "hu": "HU-G6-05", "respuesta": "Dispositivo registrado: su `id` se envía como `dispositivo_id` en el login",
        "descripcion": "Registra un dispositivo de confianza confirmando con el PIN: máximo 3, nombre de 3 a 30 "
                       "caracteres único sin distinguir mayúsculas.",
        "errores": ["DISPOSITIVO_INVALIDO", "PIN_INCORRECTO", "LIMITE_DISPOSITIVOS", "DISPOSITIVO_DUPLICADO"],
    },
    ("put", "/api/seguridad/dispositivos/{dispositivo_id}"): {
        "hu": "HU-G6-07", "respuesta": "Dispositivo renombrado",
        "descripcion": "Cambia el nombre del dispositivo; debe tener de 3 a 30 caracteres y ser único.",
        "errores": ["DISPOSITIVO_NO_ENCONTRADO", "DISPOSITIVO_INVALIDO", "DISPOSITIVO_DUPLICADO"],
    },
    ("delete", "/api/seguridad/dispositivos/{dispositivo_id}"): {
        "hu": "HU-G6-08", "respuesta": "Dispositivo eliminado",
        "descripcion": "Elimina el dispositivo. Los inicios de sesión posteriores con ese identificador generan la alerta de "
                       "nuevo dispositivo.",
        "errores": ["DISPOSITIVO_NO_ENCONTRADO"],
    },
    ("get", "/api/seguridad/sesiones"): {
        "hu": "HU-G6-09", "respuesta": "Sesiones vigentes; `actual` indica la del token usado",
        "descripcion": "Sesiones activas del usuario. Las cerradas o vencidas no se muestran.",
        "errores": [],
    },
    ("delete", "/api/seguridad/sesiones"): {
        "hu": "HU-G6-10", "respuesta": "Cantidad de sesiones cerradas",
        "descripcion": "Cierra todas las sesiones del usuario excepto la actual. Sus tokens dejan de funcionar de inmediato.",
        "errores": [],
    },
    ("delete", "/api/seguridad/sesiones/{sesion_id}"): {
        "hu": "HU-G6-10", "respuesta": "Sesión cerrada",
        "descripcion": "Cierra una sesión propia; su token deja de funcionar de inmediato.",
        "errores": ["SESION_NO_ENCONTRADA"],
    },
    # ------------------------------------------------------------- soporte para pruebas
    ("put", "/api/pruebas/reloj"): {"errores": ["SOLICITUD_INVALIDA"]},
    ("put", "/api/pruebas/saldo"): {"errores": ["SALDO_INVALIDO", "USUARIO_NO_ENCONTRADO"]},
}

# ======================================================================= parámetros de consulta y de ruta

PARAMETROS = {
    "monto": {"description": f"{MONTO_ENTRADA}; máximo S/ 500.00"},
    "tipo@/api/transferencias/comision": {"description": "QOLQE (sin comisión) o INTERBANCARIA"},
    "desde": {"description": "Fecha inicial AAAA-MM-DD (por defecto, 30 días antes de `hasta`)", "schema": {"format": "date"}},
    "hasta": {"description": "Fecha final AAAA-MM-DD, incluida y no futura (por defecto, hoy)", "schema": {"format": "date"}},
    "tipo": {"description": "Tipo de movimiento", "schema": {"enum": TIPOS_MOVIMIENTO + [None]}},
    "categoria_id": {"description": "Id de una categoría propia"},
    "pagina": {"description": "Número de página, mayor o igual a 1", "schema": {"minimum": 1}},
    "limite": {"description": "Cantidad de movimientos (1 a 20)"},
    "codigo_operacion": {"description": "Código de operación", "example": "TRF26100910150000001"},
    "empresa": {"description": "Código de la empresa (ver `GET /api/servicios/empresas`)", "example": "ELECTRO"},
    "suministro": {"description": "Código de suministro de 8 a 12 dígitos", "example": "10000001",
                   "schema": {"pattern": r"^\d{8,12}$"}},
    "afiliacion_id": {"description": "Id de una afiliación propia"},
    "buscar": {"description": "Parte del alias, sin distinguir mayúsculas ni tildes", "example": "jose"},
    "estado": {"description": "Estado de la solicitud", "schema": {"enum": ESTADOS_SOLICITUD + [None]}},
    "celular": {"description": "Celular del usuario", "example": "987654321"},
    "programada_id": {"description": "Id de una recarga programada propia"},
    "categoria_id@path": {"description": "Id de una categoría propia"},
    "contacto_id": {"description": "Id de un contacto propio"},
    "solicitud_id": {"description": "Id de la solicitud"},
    "alerta_id": {"description": "Id de una alerta propia"},
    "dispositivo_id": {"description": "Identificador del dispositivo", "example": "a1b2c3d4e5f60718"},
    "sesion_id": {"description": "Id de una sesión propia"},
}

# ======================================================================= esquemas (cuerpos y respuestas)

ESQUEMAS = {
    # ------------------------------------------------------------- solicitudes (cuerpos de entrada)
    "SolicitudRegistro": {
        "_": "Datos para crear una cuenta",
        "dni": {"pattern": r"^\d{8}$", "minLength": 8, "maxLength": 8, "description": "8 dígitos", "examples": ["45678912"]},
        "nombres": {"minLength": 2, "maxLength": 80, "description": "De 2 a 80 caracteres"},
        "celular": {**CELULAR, "description": "9 dígitos, empieza con 9 y no debe estar registrado", "examples": ["987000111"]},
        "pin": {**PIN, "description": "4 dígitos, no todos iguales ni secuencia ascendente o descendente"},
        "correo": {"format": "email", "maxLength": 100,
                   "description": "Opcional. Único entre cuentas activas, sin distinguir mayúsculas. Se guarda en minúsculas"},
    },
    "SolicitudLogin": {
        "_": "Credenciales de acceso",
        "celular": CELULAR,
        "pin": PIN,
        "dispositivo_id": {"description": "Opcional: `id` de un dispositivo de confianza. Si no es uno de los "
                                          "dispositivos del usuario, se envía un SMS de alerta",
                           "examples": ["a1b2c3d4e5f60718"]},
    },
    "CambioPerfil": {
        "_": "Campos del perfil que se pueden modificar. Solo se actualizan los enviados",
        "nombres": {"minLength": 2, "maxLength": 80, "description": "De 2 a 80 caracteres"},
        "correo": {"format": "email", "maxLength": 100, "description": "Único entre cuentas activas. `null` o vacío lo quita"},
    },
    "SolicitudCierre": {"_": "Confirmación del cierre de cuenta", "pin": {**PIN, "description": "PIN actual"}},
    "SolicitudTransferencia": {
        "_": "Datos de la transferencia. Para QOLQE indicar `celular_destino` o `contacto_id`; para INTERBANCARIA, `cci`",
        "tipo": {"description": "QOLQE: a otro usuario de Qolqe; INTERBANCARIA: a una cuenta de otro banco"},
        "celular_destino": {**CELULAR, "description": "Celular del destinatario (tipo QOLQE)"},
        "contacto_id": {"description": "Alternativa a `celular_destino`: id de un contacto propio (tipo QOLQE)", "examples": [1]},
        "cci": {"pattern": r"^\d{20}$", "minLength": 20, "maxLength": 20, "description": "CCI de 20 dígitos (tipo INTERBANCARIA)",
                "examples": ["00219300123456789012"]},
        "monto": {"description": f"{MONTO_ENTRADA}; máximo S/ 500.00 por operación", "examples": ["100.00"]},
        "descripcion": {"maxLength": 60, "description": "Opcional, hasta 60 caracteres", "examples": ["Almuerzo"]},
    },
    "Clasificacion": {
        "_": "Clasificación de un movimiento. Solo se actualizan los campos enviados",
        "categoria_id": {"description": "Id de una categoría propia; `null` quita la categoría", "examples": [1]},
        "nota": {"maxLength": 100, "description": "Hasta 100 caracteres; `null` o vacío la quita",
                 "examples": ["Cumpleaños de Carla"]},
    },
    "SolicitudCategoria": {
        "_": "Nueva categoría",
        "nombre": {"minLength": 3, "maxLength": 20, "description": "De 3 a 20 caracteres, único sin distinguir mayúsculas"},
        "color": {"enum": PALETA, "description": "Color de la paleta fija de 8 colores"},
    },
    "CambioCategoria": {
        "_": "Cambios de una categoría. Solo se actualizan los campos enviados",
        "nombre": {"minLength": 3, "maxLength": 20, "description": "De 3 a 20 caracteres, único sin distinguir mayúsculas"},
        "color": {"enum": PALETA, "description": "Color de la paleta fija de 8 colores"},
    },
    "SolicitudRecarga": {
        "_": "Datos de la recarga",
        "celular": {**CELULAR, "description": "Celular a recargar", "examples": ["987111222"]},
        "monto": {"description": MONTOS_RECARGA, "examples": ["30"]},
    },
    "SolicitudProgramada": {
        "_": "Nueva recarga programada mensual",
        "celular": {**CELULAR, "description": "Celular a recargar", "examples": ["987111222"]},
        "monto": {"description": MONTOS_RECARGA, "examples": ["20"]},
        "dia": {"minimum": 1, "maximum": 28, "description": "Día del mes en que se ejecuta, de 1 a 28"},
        "alias": {"maxLength": 20, "description": "Opcional, hasta 20 caracteres"},
    },
    "CambioProgramada": {
        "_": "Cambios de una recarga programada. Solo se actualizan los campos enviados",
        "monto": {"description": MONTOS_RECARGA},
        "dia": {"minimum": 1, "maximum": 28, "description": "Día del mes, de 1 a 28. Recalcula la próxima ejecución"},
        "alias": {"maxLength": 20, "description": "Hasta 20 caracteres"},
    },
    "SolicitudPago": {"_": "Deuda a pagar", "deuda_id": {"description": "Id de la deuda (ver `GET /api/servicios/deudas`)", "examples": [1]}},
    "SolicitudAfiliacion": {
        "_": "Servicio a afiliar",
        "empresa": {"description": "Código de la empresa (ver `GET /api/servicios/empresas`)"},
        "suministro": {"pattern": r"^\d{8,12}$", "minLength": 8, "maxLength": 12,
                       "description": "De 8 a 12 dígitos; debe tener al menos un recibo en la empresa"},
        "alias": {"minLength": 3, "maxLength": 20, "description": "De 3 a 20 caracteres"},
    },
    "CambioAfiliacion": {
        "_": "Cambios de una afiliación. Solo se actualizan los campos enviados",
        "alias": {"minLength": 3, "maxLength": 20, "description": "De 3 a 20 caracteres"},
        "debito_automatico": {"description": "true activa y false desactiva el débito automático", "examples": [True]},
    },
    "SolicitudContacto": {
        "_": "Nuevo contacto",
        "celular": {**CELULAR, "description": "Celular registrado y activo, distinto del propio"},
        "alias": {"minLength": 3, "maxLength": 20, "pattern": r"^\s*[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 ]+\s*$",
                  "description": "Sin espacios al inicio ni al final, de 3 a 20 caracteres; letras (incluidas tildes y ñ), "
                                 "números y espacios; único sin distinguir mayúsculas"},
    },
    "CambioContacto": {
        "_": "Cambios de un contacto. Solo se actualizan los campos enviados",
        "alias": {"minLength": 3, "maxLength": 20, "description": "Mismas reglas que al agregar"},
        "favorito": {"description": "Máximo 5 favoritos", "examples": [True]},
    },
    "SolicitudDinero": {
        "_": "Solicitud de dinero a un contacto",
        "contacto_id": {"description": "Id de un contacto propio", "examples": [2]},
        "monto": {"description": f"{MONTO_ENTRADA}; máximo S/ 500.00"},
        "motivo": {"minLength": 3, "maxLength": 60, "description": "De 3 a 60 caracteres"},
    },
    "Rechazo": {"_": "Cuerpo opcional del rechazo",
                "motivo": {"maxLength": 60, "description": "Opcional, hasta 60 caracteres"}},
    "SolicitudLimite": {"_": "Nuevo límite diario",
                        "limite_diario": {"description": "De S/ 100 a S/ 2,000, en múltiplos de S/ 50"}},
    "SolicitudAlerta": {
        "_": "Nueva alerta de consumo",
        "tipo": {"enum": TIPOS_ALERTA, "description": "Tipo de gasto que se vigila"},
        "umbral": {"description": "De S/ 10 a S/ 2,000 en múltiplos de S/ 10; para TRANSFERENCIAS y TODAS, no mayor al "
                                  "límite diario vigente"},
    },
    "CambioAlerta": {
        "_": "Cambios de una alerta. Solo se actualizan los campos enviados",
        "umbral": {"description": "Mismas reglas que al crear"},
        "estado": {"enum": ["ACTIVA", "PAUSADA"], "description": "ACTIVA para reanudar, PAUSADA para pausar"},
    },
    "SolicitudCambioPin": {
        "_": "Cambio de PIN",
        "pin_actual": {**PIN, "description": "PIN actual"},
        "pin_nuevo": {**PIN, "description": "Distinto de los últimos 3 PIN y de los últimos 4 dígitos del celular",
                      "examples": ["7305"]},
    },
    "SolicitudCodigo": {"_": "Celular de la cuenta bloqueada", "celular": {**CELULAR, "examples": ["923456789"]}},
    "ConfirmacionCodigo": {
        "_": "Código de desbloqueo recibido por SMS",
        "celular": {**CELULAR, "examples": ["923456789"]},
        "codigo": {"pattern": r"^\d{6}$", "minLength": 6, "maxLength": 6, "description": "Código de 6 dígitos"},
    },
    "SolicitudDispositivo": {
        "_": "Nuevo dispositivo de confianza",
        "nombre": {"minLength": 3, "maxLength": 30, "description": "De 3 a 30 caracteres, único sin distinguir mayúsculas"},
        "tipo": {"enum": TIPOS_DISPOSITIVO, "description": "Tipo de dispositivo"},
        "pin": {**PIN, "description": "PIN actual, para confirmar"},
    },
    "CambioDispositivo": {"_": "Nuevo nombre del dispositivo",
                          "nombre": {"minLength": 3, "maxLength": 30, "description": "De 3 a 30 caracteres, único sin distinguir mayúsculas"}},
    # ------------------------------------------------------------- respuestas
    "UsuarioRegistrado": {"_": "Cuenta creada", "celular": CELULAR, "creado_en": FECHA_HORA,
                          "correo": {"description": "Correo en minúsculas, o null"}},
    "RespuestaLogin": {
        "_": "Token de acceso y datos del usuario",
        "access_token": {"description": "Token JWT. Enviarlo en `Authorization: Bearer <token>`"},
        "token_type": {"enum": ["bearer"]},
        "expires_in": {"description": "Segundos de vigencia del token (1800 = 30 minutos)", "examples": [1800]},
        "sesion_id": {"description": "Id de la sesión creada (ver `GET /api/seguridad/sesiones`)"},
    },
    "DatosUsuario": {"_": "Datos básicos del usuario", "celular": CELULAR},
    "Perfil": {
        "_": "Perfil del usuario",
        "celular": CELULAR,
        "dni": {"pattern": r"^\*{4}\d{4}$", "description": "DNI enmascarado: solo los últimos 4 dígitos", "examples": ["****8912"]},
        "correo": {"description": "Correo o null"},
        "estado": {"enum": ["ACTIVA", "CERRADA"]},
        "creado_en": FECHA_HORA,
    },
    "Saldo": {"_": "Saldo disponible", "saldo": MONTO_SALIDA, "moneda": {"enum": ["PEN"]}, "actualizado_en": FECHA_HORA},
    "Comision": {"_": "Simulación de la comisión", "monto": MONTO_SALIDA, "comision": MONTO_SALIDA,
                 "total": {**MONTO_SALIDA, "description": "Monto + comisión"}},
    "Destinatario": {
        "_": "Destinatario: nombre y celular (Qolqe) o CCI enmascarado (interbancaria)",
        "nombre": {"description": "Nombre enmascarado (primer nombre e inicial del apellido)", "examples": ["Bruno D."]},
        "celular": {"description": "Celular del destinatario (Qolqe)"},
        "cci": {"description": "CCI enmascarado: solo los últimos 4 dígitos (interbancaria), o null"},
    },
    "TransferenciaRealizada": {
        "_": "Comprobante de la transferencia",
        "codigo_operacion": CODIGO_OPERACION, "tipo": {"enum": ["QOLQE", "INTERBANCARIA"]},
        "monto": MONTO_SALIDA, "comision": MONTO_SALIDA, "total": {**MONTO_SALIDA, "description": "Monto + comisión"},
        "saldo": {**MONTO_SALIDA, "description": "Nuevo saldo del origen"}, "fecha": FECHA_HORA,
    },
    "Movimiento": {
        "_": "Movimiento de la cuenta",
        "codigo_operacion": CODIGO_OPERACION, "fecha": FECHA_HORA, "tipo": {"enum": TIPOS_MOVIMIENTO},
        "contraparte": {"description": "Celular, CCI enmascarado o suministro relacionado"},
        "monto": MONTO_SALIDA, "comision": MONTO_SALIDA,
        "importe": {**MONTO_SALIDA, "description": "Efecto en el saldo: negativo si es un cargo"},
        "saldo_posterior": {**MONTO_SALIDA, "description": "Saldo después del movimiento (solo en el historial)"},
        "categoria": {"description": "Categoría asignada, o null"},
        "nota": {"maxLength": 100, "description": "Nota del usuario, o null"},
    },
    "CategoriaAsignada": {"_": "Categoría asignada a un movimiento", "color": {"enum": PALETA}},
    "PaginaMovimientos": {
        "_": "Página del historial",
        "desde": FECHA, "hasta": FECHA, "tipo": {"enum": TIPOS_MOVIMIENTO + [None]},
        "pagina": {"minimum": 1}, "por_pagina": {"enum": [10]},
        "total": {"description": "Total de movimientos del filtro"}, "total_paginas": {"minimum": 1},
    },
    "Categoria": {"_": "Categoría del usuario", "color": {"enum": PALETA},
                  "cantidad_movimientos": {"minimum": 0, "description": "Movimientos asignados"}, "creada_en": FECHA_HORA},
    "ConfiguracionRecargas": {"_": "Configuración de recargas",
                              "montos": {"description": "Montos permitidos", "examples": [["5", "10", "20", "30", "50", "100"]]},
                              "max_recargas_diarias_mismo_numero": {"examples": [5]}},
    "InfoBono": {"_": "Bono de recarga", "monto_minimo": {"description": "Monto desde el que se da el bono"},
                 "porcentaje": {"description": "Porcentaje del bono"}, "tope": {"description": "Bono máximo"}},
    "RecargaRealizada": {"_": "Comprobante de la recarga", "codigo_operacion": CODIGO_OPERACION, "celular": CELULAR,
                         "monto": MONTO_SALIDA, "bono": MONTO_SALIDA, "origen": {"enum": ["MANUAL", "PROGRAMADA"]},
                         "saldo": {**MONTO_SALIDA, "description": "Nuevo saldo"}, "fecha": FECHA_HORA},
    "RecargaListada": {"_": "Recarga realizada", "codigo_operacion": CODIGO_OPERACION, "celular": CELULAR,
                       "monto": MONTO_SALIDA, "bono": MONTO_SALIDA, "origen": {"enum": ["MANUAL", "PROGRAMADA"]}, "fecha": FECHA_HORA},
    "Programada": {
        "_": "Recarga programada",
        "celular": CELULAR, "monto": MONTO_SALIDA, "dia": {"minimum": 1, "maximum": 28},
        "estado": {"enum": ["ACTIVA", "PAUSADA"]},
        "proxima_ejecucion": {**FECHA, "description": "Fecha de la próxima ejecución"},
        "ultimo_resultado": {"enum": ["EXITOSA", "FALLIDA", "SIN_EJECUCIONES"]},
        "ultimo_detalle": {"description": "Motivo de la última ejecución FALLIDA, o null"},
        "ultima_ejecucion_en": {**FECHA_HORA, "description": "Fecha y hora de la última ejecución, o null"},
        "creada_en": FECHA_HORA,
    },
    "Empresa": {"_": "Empresa de servicios", "codigo": {"examples": ["ELECTRO"]}, "rubro": {"examples": ["Luz"]}},
    "Deuda": {
        "_": "Deuda pendiente de un suministro",
        "titular": {"description": "Nombre del titular enmascarado", "examples": ["Ana T."]},
        "periodo": {"pattern": r"^\d{4}-\d{2}$", "examples": ["2026-10"]},
        "monto": MONTO_SALIDA, "vencimiento": FECHA,
        "dias_atraso": {"minimum": 0, "description": "Días después del vencimiento"},
        "mora": {**MONTO_SALIDA, "description": "0.5 % por día de atraso con tope de 10 %; null si está en cobranza"},
        "total": {**MONTO_SALIDA, "description": "Monto + mora; null si está en cobranza"},
        "estado": {"enum": ["PENDIENTE", "EN_COBRANZA"]},
    },
    "PagoRealizado": {"_": "Comprobante del pago", "codigo_operacion": CODIGO_OPERACION, "monto": MONTO_SALIDA,
                      "mora": MONTO_SALIDA, "total": MONTO_SALIDA, "origen": {"enum": ["MANUAL", "DEBITO_AUTOMATICO"]},
                      "saldo": {**MONTO_SALIDA, "description": "Nuevo saldo"}, "fecha": FECHA_HORA,
                      "periodo": {"pattern": r"^\d{4}-\d{2}$"}},
    "PagoListado": {"_": "Pago realizado", "codigo_operacion": CODIGO_OPERACION, "monto": MONTO_SALIDA,
                    "mora": MONTO_SALIDA, "total": MONTO_SALIDA, "origen": {"enum": ["MANUAL", "DEBITO_AUTOMATICO"]},
                    "fecha": FECHA_HORA, "periodo": {"pattern": r"^\d{4}-\d{2}$"}},
    "Afiliacion": {
        "_": "Servicio afiliado",
        "total_pendiente": {**MONTO_SALIDA, "description": "Suma de los totales (monto + mora) de las deudas que se pueden pagar"},
        "proximo_vencimiento": {**FECHA, "description": "Vencimiento más cercano, desde hoy, de una deuda pendiente; o null"},
        "situacion": {"enum": ["AL_DIA", "CON_DEUDA", "EN_COBRANZA"],
                      "description": "AL_DIA: sin deudas; CON_DEUDA; EN_COBRANZA: alguna deuda en cobranza"},
        "creada_en": FECHA_HORA,
    },
    "Contacto": {"_": "Contacto", "celular": CELULAR,
                 "nombre": {"description": "Nombre enmascarado del contacto", "examples": ["Bruno D."]}},
    "PaginaContactos": {"_": "Página de contactos", "pagina": {"minimum": 1}, "por_pagina": {"enum": [10]},
                        "total_paginas": {"minimum": 1}},
    "Participante": {"_": "Participante de una solicitud", "nombre": {"description": "Nombre enmascarado"}, "celular": CELULAR},
    "Solicitud": {
        "_": "Solicitud de dinero",
        "monto": MONTO_SALIDA, "estado": {"enum": ESTADOS_SOLICITUD},
        "creada_en": FECHA_HORA, "vence_en": {**FECHA_HORA, "description": "48 horas después de creada",
                                               "examples": ["2026-10-11T10:15:00"]},
        "resuelta_en": {**FECHA_HORA, "description": "Fecha en que se aceptó, rechazó o canceló; o null"},
        "motivo_rechazo": {"description": "Motivo indicado al rechazar, o null"},
        "codigo_operacion": {"description": "Código de la transferencia si fue ACEPTADA; o null"},
    },
    "MisSolicitudes": {"_": "Solicitudes del usuario", "enviadas": {"description": "Solicitudes que el usuario envió"},
                       "recibidas": {"description": "Solicitudes que el usuario recibió"}},
    "EstadoLimites": {
        "_": "Límites y consumo del día",
        "limite_por_operacion": MONTO_SALIDA, "limite_diario": {**MONTO_SALIDA, "description": "Límite diario vigente"},
        "limite_pendiente": {**MONTO_SALIDA, "description": "Aumento solicitado que aún no está vigente, o null"},
        "pendiente_desde": {**FECHA_HORA, "description": "Desde cuándo rige el aumento pendiente, o null"},
        "usado_hoy": {**MONTO_SALIDA, "description": "Transferido hoy"}, "disponible_hoy": MONTO_SALIDA,
    },
    "CambioLimite": {
        "_": "Límites después del cambio",
        "limite_por_operacion": MONTO_SALIDA, "limite_diario": MONTO_SALIDA, "limite_pendiente": MONTO_SALIDA,
        "pendiente_desde": FECHA_HORA, "usado_hoy": MONTO_SALIDA, "disponible_hoy": MONTO_SALIDA,
        "aplicacion": {"enum": ["INMEDIATA", "PROGRAMADA"],
                       "description": "INMEDIATA (reducción) o PROGRAMADA (aumento, vigente en 24 horas)"},
    },
    "Alerta": {
        "_": "Alerta de consumo",
        "tipo": {"enum": TIPOS_ALERTA}, "umbral": MONTO_SALIDA, "estado": {"enum": ["ACTIVA", "PAUSADA"]},
        "gasto_hoy": {**MONTO_SALIDA, "description": "Gasto de hoy del tipo de la alerta"},
        "ultima_notificacion": {**FECHA_HORA, "description": "Fecha y hora del último SMS enviado, o null"},
        "creada_en": FECHA_HORA,
    },
    "Dispositivo": {"_": "Dispositivo de confianza",
                    "id": {"description": "Identificador que se envía en el login como `dispositivo_id`", "examples": ["a1b2c3d4e5f60718"]},
                    "tipo": {"enum": TIPOS_DISPOSITIVO}, "registrado_en": FECHA_HORA,
                    "ultimo_ingreso": {**FECHA_HORA, "description": "Último inicio de sesión desde este dispositivo, o null"}},
    "Sesion": {"_": "Sesión activa", "iniciada_en": FECHA_HORA,
               "expira_en": {**FECHA_HORA, "description": "30 minutos después de iniciada", "examples": ["2026-10-09T10:45:00"]}},
    "DispositivoDeSesion": {"_": "Dispositivo indicado al iniciar la sesión"},
    "SesionesCerradas": {"_": "Resultado del cierre de sesiones", "sesiones_cerradas": {"minimum": 0}},
    "Mensaje": {"_": "Mensaje para el usuario"},
    "Salud": {"_": "Estado del servicio"},
    "EstadoReloj": {"_": "Reloj de la aplicación", "ahora": FECHA_HORA},
    "Notificacion": {"_": "SMS simulado", "celular": CELULAR, "fecha": FECHA_HORA},
}

ESQUEMAS.update({
    "AjusteSaldo": {"_": "Saldo que se fija a un usuario", "celular": {**CELULAR, "description": "Celular del usuario"},
                    "saldo": {"description": "Nuevo saldo en soles, mayor o igual a 0", "examples": ["100.00"]}},
    "CambioReloj": {"_": "Enviar `ahora` para fijar el reloj o `avanzar_minutos` para adelantarlo",
                    "ahora": {"description": "Fecha y hora de Lima a fijar", "examples": ["2026-11-15T10:00:00"]},
                    "avanzar_minutos": {"description": "Minutos que se adelanta el reloj", "examples": [60]}},
    "Resultado": {"_": "Resultado de la operación de soporte"},
    "ResultadoProcesoDiario": {
        "_": "Resultado del proceso diario", "fecha": {**FECHA, "description": "Fecha (del reloj de la app) procesada"},
        "recargas_exitosas": {"description": "Recargas programadas ejecutadas con éxito"},
        "recargas_fallidas": {"description": "Recargas programadas que quedaron FALLIDAS"},
        "debitos_pagados": {"description": "Deudas pagadas por débito automático"},
        "debitos_fallidos": {"description": "Débitos que no se pudieron pagar (quedan pendientes)"},
    },
})

CAMPOS_COMUNES = {
    "id": "Identificador",
    "alias": "Alias que eligió el usuario",
    "nombre": "Nombre",
    "nombres": "Nombres y apellidos",
    "empresa": "Código de la empresa",
    "empresa_nombre": "Nombre de la empresa",
    "suministro": "Código de suministro",
    "periodo": "Periodo facturado (AAAA-MM)",
    "tipo": "Tipo",
    "estado": "Estado",
    "origen": "Quién inició la operación",
    "motivo": "Motivo",
    "mensaje": "Mensaje",
    "descripcion": "Descripción",
    "dia": "Día del mes de ejecución",
    "favorito": "Es un contacto favorito",
    "debito_automatico": "Débito automático activado",
    "usuario": "Datos del usuario autenticado",
    "destinatario": "Destinatario",
    "solicitante": "Usuario que pide el dinero",
    "dispositivo": "Dispositivo indicado en el login, o null",
    "bono": "Bono de recarga",
    "codigo": "Código",
    "rubro": "Rubro del servicio",
    "moneda": "Moneda (soles)",
    "token_type": "Tipo de token",
    "buscar": "Texto buscado, o null",
    "categoria_id": "Categoría filtrada, o null",
    "pagina": "Página actual",
    "por_pagina": "Elementos por página",
    "total": "Total de elementos",
    "total_paginas": "Total de páginas",
    "movimientos": "Movimientos de la página",
    "contactos": "Contactos de la página",
    "ultimo_resultado": "Resultado de la última ejecución",
    "max_recargas_diarias_mismo_numero": "Máximo de recargas por día al mismo número",
    "sesiones_cerradas": "Cantidad de sesiones cerradas",
    "desfasado": "true si el reloj fue fijado o adelantado",
    "version": "Versión de la API",
    "modo_prueba": "true si la API de soporte para pruebas está habilitada",
    "color": "Color de la paleta",
}

# ======================================================================= etiquetas

ETIQUETAS = [
    {"name": "Autenticación", "description": "Registro (HU-N-01), inicio y cierre de sesión (HU-N-02, HU-N-03)"},
    {"name": "Cuenta", "description": "Saldo, perfil y cierre de la cuenta (HU-N-04 a HU-N-06)"},
    {"name": "Transferencias", "description": "Transferencias Qolqe e interbancarias y simulación de comisión (HU-N-07 a HU-N-09)"},
    {"name": "Recargas", "description": "**G1** · Recargas de celular y recargas programadas"},
    {"name": "Pago de servicios", "description": "**G2** · Deudas, pagos, afiliaciones y débito automático"},
    {"name": "Movimientos", "description": "**G3** · Historial, detalle, clasificación y exportación"},
    {"name": "Categorías", "description": "**G3** · Categorías propias para clasificar movimientos"},
    {"name": "Contactos", "description": "**G4** · Contactos frecuentes y favoritos"},
    {"name": "Solicitudes de dinero", "description": "**G4** · Solicitudes de dinero entre contactos"},
    {"name": "Límites", "description": "**G5** · Límite diario y alertas de consumo"},
    {"name": "Seguridad", "description": "**G6** · PIN, desbloqueo, dispositivos de confianza y sesiones"},
    {"name": "Soporte para pruebas", "description": "Solo con `QOLQE_MODO_PRUEBA=1`. **No forma parte del producto**: "
                                                    "permite repetir las pruebas (datos, reloj, SMS, saldo y proceso diario)"},
    {"name": "Salud", "description": "Estado del servicio"},
]

# ======================================================================= componentes de error

ESQUEMA_ERROR = {
    "title": "Error",
    "type": "object",
    "description": "Formato de todas las respuestas de error",
    "required": ["codigo", "detail"],
    "properties": {
        "codigo": {"type": "string", "description": "Código estable del error (ver la descripción de cada operación)",
                   "examples": ["SALDO_INSUFICIENTE"]},
        "detail": {"type": "string", "description": "Mensaje para el usuario", "examples": ["Saldo insuficiente para realizar la operación"]},
        "errores": {"type": "array", "description": "Solo en SOLICITUD_INVALIDA: campos con formato o tipo inválido",
                    "items": {"$ref": "#/components/schemas/ErrorDeCampo"}},
    },
}
ESQUEMA_ERROR_CAMPO = {
    "title": "ErrorDeCampo", "type": "object", "required": ["campo", "mensaje"],
    "properties": {
        "campo": {"type": "string", "description": "Ubicación del campo", "examples": ["body.monto"]},
        "mensaje": {"type": "string", "description": "Motivo", "examples": ["Input should be a valid decimal"]},
    },
}
EJEMPLO_SOLICITUD_INVALIDA = {
    "codigo": "SOLICITUD_INVALIDA", "detail": "La solicitud tiene datos inválidos",
    "errores": [{"campo": "body.monto", "mensaje": "Field required"}],
}


# ======================================================================= ejemplos de cuerpos y respuestas

EJEMPLOS_CUERPO = {
    ("post", "/api/auth/login"): {
        "Sin dispositivo": {"celular": "987654321", "pin": "4826"},
        "Con dispositivo de confianza": {"celular": "987654321", "pin": "4826", "dispositivo_id": "a1b2c3d4e5f60718"},
    },
    ("put", "/api/cuentas/me"): {
        "Cambiar nombres y correo": {"nombres": "Ana Lucía Torres Quispe", "correo": "ana.lucia@correo.pe"},
        "Quitar el correo": {"correo": None},
    },
    ("post", "/api/transferencias"): {
        "Qolqe por celular": {"tipo": "QOLQE", "celular_destino": "912345678", "monto": "100.00", "descripcion": "Almuerzo"},
        "Qolqe a un contacto": {"tipo": "QOLQE", "contacto_id": 1, "monto": "50"},
        "Interbancaria": {"tipo": "INTERBANCARIA", "cci": "00219300123456789012", "monto": "150.00"},
    },
    ("put", "/api/movimientos/{codigo_operacion}/clasificacion"): {
        "Asignar categoría y nota": {"categoria_id": 1, "nota": "Cumpleaños de Carla"},
        "Quitar la categoría": {"categoria_id": None},
    },
    ("put", "/api/categorias/{categoria_id}"): {
        "Cambiar nombre": {"nombre": "Restaurantes"},
        "Cambiar color": {"color": "#FB8C00"},
    },
    ("put", "/api/recargas/programadas/{programada_id}"): {
        "Cambiar día y monto": {"dia": 20, "monto": "30"},
        "Cambiar alias": {"alias": "Mamá celular"},
    },
    ("put", "/api/servicios/afiliaciones/{afiliacion_id}"): {
        "Activar débito automático": {"debito_automatico": True},
        "Cambiar alias": {"alias": "Luz depa"},
    },
    ("put", "/api/contactos/{contacto_id}"): {
        "Cambiar alias": {"alias": "Bruno oficina"},
        "Marcar como favorito": {"favorito": True},
    },
    ("post", "/api/solicitudes/{solicitud_id}/rechazar"): {
        "Con motivo": {"motivo": "Ya te pagué en efectivo"},
        "Sin motivo": {},
    },
    ("put", "/api/limites/alertas/{alerta_id}"): {
        "Cambiar umbral": {"umbral": "400"},
        "Pausar": {"estado": "PAUSADA"},
        "Reanudar": {"estado": "ACTIVA"},
    },
    ("put", "/api/pruebas/reloj"): {
        "Fijar fecha y hora": {"ahora": "2026-11-15T10:00:00"},
        "Adelantar 1 día": {"avanzar_minutos": 1440},
    },
}

VALORES_POR_CAMPO = {
    "id": 1, "alias": "Mamá", "nombre": "Bruno D.", "nombres": "Ana Torres Quispe", "empresa": "ELECTRO",
    "empresa_nombre": "Electro Andina", "suministro": "10000001", "motivo": "Almuerzo del viernes",
    "mensaje": "Operación realizada", "descripcion": "Transferencia a Bruno D.", "codigo": "ELECTRO", "rubro": "Luz",
    "dia": 15, "total": 12, "total_paginas": 2, "pagina": 1, "por_pagina": 10, "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "contraparte": "912345678", "celular": "912345678", "estado": "ok", "version": "1.0.0", "categoria_id": 1,
    "contacto_id": 1, "deuda_id": 1, "sesion_id": 7, "correo": "ana.torres@correo.pe", "cantidad_movimientos": 5,
    "dias_atraso": 0, "monto_minimo": "30", "porcentaje": "5", "tope": "4.00", "periodo": "2026-10",
    "codigo_operacion": "TRF26100910150000001", "titular": "Ana T.", "sesiones_cerradas": 2,
}
NULOS_POR_CAMPO = {"buscar", "tipo", "categoria_id", "ultimo_detalle", "motivo_rechazo", "ultima_ejecucion_en",
                   "resuelta_en", "codigo_operacion", "limite_pendiente", "pendiente_desde", "nota", "categoria",
                   "ultima_notificacion", "ultimo_ingreso", "cci", "dispositivo"}
MONTOS_POR_CAMPO = {
    "comision": "0.00", "mora": "0.00", "bono": "1.50", "saldo": "1400.00", "total": "100.00", "umbral": "300.00",
    "limite_diario": "2000.00", "limite_por_operacion": "500.00", "usado_hoy": "100.00", "disponible_hoy": "1900.00",
    "gasto_hoy": "120.00", "saldo_posterior": "1400.00", "importe": "-100.00", "total_pendiente": "120.00",
}


def _ejemplo(esquema: dict, componentes: dict, campo: str = "", profundidad: int = 0):
    """Construye un ejemplo realista a partir del esquema: ejemplos de cada campo, formatos, enums y nombres de campo."""
    if profundidad > 15:
        return None
    if "$ref" in esquema:
        return _ejemplo(componentes[esquema["$ref"].split("/")[-1]], componentes, campo, profundidad + 1)
    if "anyOf" in esquema and campo in NULOS_POR_CAMPO:
        return None
    if "examples" in esquema:
        return esquema["examples"][0]
    if "anyOf" in esquema:
        variante = next((v for v in esquema["anyOf"] if v.get("type") != "null"), {})
        resto = {k: v for k, v in esquema.items() if k not in ("anyOf", "enum")}
        return _ejemplo({**resto, **variante}, componentes, campo, profundidad + 1)
    patron = esquema.get("pattern")
    if patron == PATRON_MONTO:
        return MONTOS_POR_CAMPO.get(campo, "100.00")
    if patron == PATRON_FECHA_HORA:
        return "2026-10-09T10:15:00"
    if patron == PATRON_FECHA or esquema.get("format") == "date":
        return "2026-11-15"
    if "enum" in esquema:
        return next(v for v in esquema["enum"] if v is not None)
    if campo in VALORES_POR_CAMPO and esquema.get("type") != "array":
        return VALORES_POR_CAMPO[campo]
    if esquema.get("type") == "object" or "properties" in esquema:
        return {nombre: _ejemplo(propiedad, componentes, nombre, profundidad + 1)
                for nombre, propiedad in esquema.get("properties", {}).items()}
    if esquema.get("type") == "array":
        return [_ejemplo(esquema.get("items", {}), componentes, "", profundidad + 1)]
    return {"integer": 1, "number": 1, "boolean": True}.get(esquema.get("type"), "texto")


# ======================================================================= construcción

RESTRICCIONES_TEXTO = ("pattern", "minLength", "maxLength", "format")
RESTRICCIONES_NUMERO = ("minimum", "maximum")


def _aplicar_restricciones(propiedad: dict, extra: dict) -> None:
    """Agrega descripción, ejemplos y restricciones a una propiedad.

    En los campos opcionales (anyOf con null) las restricciones van en la variante de texto o
    de número que corresponda, y el enum incluye null.
    """
    extra = deepcopy(extra)
    variantes = propiedad.get("anyOf", [])
    for clave in ("description", "examples"):
        if clave in extra:
            propiedad[clave] = extra.pop(clave)
    if "enum" in extra:
        valores = extra.pop("enum")
        if any(v.get("type") == "null" for v in variantes) and None not in valores:
            valores = valores + [None]
        propiedad["enum"] = valores
    for claves, tipos in ((RESTRICCIONES_TEXTO, ("string",)), (RESTRICCIONES_NUMERO, ("integer", "number"))):
        valores = {k: extra[k] for k in claves if k in extra}
        if not valores:
            continue
        destinos = [v for v in variantes if v.get("type") in tipos] or [propiedad]
        for destino in destinos:
            destino.update(valores)


def _respuestas_de_error(codigos: list[str], protegida: bool, valida_entrada: bool) -> dict:
    por_estado: dict[int, dict] = {}
    todos = (["NO_AUTENTICADO"] if protegida else []) + codigos
    for codigo in todos:
        estado, mensaje = ERRORES[codigo]
        por_estado.setdefault(estado, {})[codigo] = {"summary": codigo, "value": {"codigo": codigo, "detail": mensaje}}
    if valida_entrada:
        por_estado.setdefault(422, {}).setdefault(
            "SOLICITUD_INVALIDA", {"summary": "SOLICITUD_INVALIDA (formato o tipo de dato)", "value": EJEMPLO_SOLICITUD_INVALIDA})
    respuestas = {}
    for estado in sorted(por_estado):
        ejemplos = por_estado[estado]
        respuestas[str(estado)] = {
            "description": f"{DESCRIPCION_ESTADOS[estado]}: " + ", ".join(f"`{c}`" for c in ejemplos),
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}, "examples": ejemplos}},
        }
    return respuestas


def generar_contrato(app) -> dict:
    esquema = get_openapi(title=app.title, version=app.version, description=app.description, routes=app.routes,
                          tags=ETIQUETAS)
    descripcion = esquema["info"].get("description", "").rstrip()
    esquema["info"]["description"] = (
        f"{descripcion}\n\nLas operaciones asociadas a historias de usuario las identifican en la extensión `x-hu`."
    )
    componentes = esquema.setdefault("components", {}).setdefault("schemas", {})
    componentes.pop("HTTPValidationError", None)
    componentes.pop("ValidationError", None)
    componentes["Error"] = ESQUEMA_ERROR
    componentes["ErrorDeCampo"] = ESQUEMA_ERROR_CAMPO

    for nombre, campos in ESQUEMAS.items():
        componente = componentes.get(nombre)
        if componente is None:
            continue
        if "_" in campos:
            componente["description"] = campos["_"]
        for campo, extra in campos.items():
            if campo != "_" and campo in componente.get("properties", {}):
                _aplicar_restricciones(componente["properties"][campo], extra)
    for componente in componentes.values():
        for campo, propiedad in componente.get("properties", {}).items():
            if "description" not in propiedad and campo in CAMPOS_COMUNES:
                propiedad["description"] = CAMPOS_COMUNES[campo]

    for ruta, metodos in esquema["paths"].items():
        for metodo, operacion in metodos.items():
            info = OPERACIONES.get((metodo, ruta), {})
            if info.get("hu"):
                operacion["x-hu"] = [hu.strip() for hu in info["hu"].split(",")]
            if info.get("descripcion"):
                operacion["description"] = info["descripcion"]

            for parametro in operacion.get("parameters", []):
                clave = parametro["name"]
                extra = (PARAMETROS.get(f"{clave}@{ruta}") or PARAMETROS.get(f"{clave}@path" if parametro["in"] == "path" else "")
                         or PARAMETROS.get(clave, {}))
                if "description" in extra:
                    parametro["description"] = extra["description"]
                if "example" in extra:
                    parametro["example"] = extra["example"]
                if "schema" in extra:
                    _aplicar_restricciones(parametro["schema"], extra["schema"])

            respuestas = operacion["responses"]
            respuestas.pop("422", None)
            exito = next(iter(respuestas))
            if info.get("respuesta"):
                respuestas[exito]["description"] = info["respuesta"]
            elif respuestas[exito].get("description") == "Successful Response":
                respuestas[exito]["description"] = "Operación correcta"
            cuerpo = operacion.get("requestBody", {}).get("content", {}).get("application/json")
            if cuerpo is not None:
                nombrados = EJEMPLOS_CUERPO.get((metodo, ruta))
                if nombrados:
                    cuerpo["examples"] = {nombre: {"summary": nombre, "value": valor} for nombre, valor in nombrados.items()}
                else:
                    cuerpo["example"] = _ejemplo(cuerpo["schema"], componentes)
            contenido_exito = respuestas[exito].get("content", {}).get("application/json")
            if contenido_exito and contenido_exito.get("schema"):
                contenido_exito["example"] = _ejemplo(contenido_exito["schema"], componentes)
            valida_entrada = "requestBody" in operacion or bool(operacion.get("parameters"))
            respuestas.update(_respuestas_de_error(info.get("errores", []), "security" in operacion, valida_entrada))

    exportar = esquema["paths"].get("/api/movimientos/exportar", {}).get("get")
    if exportar:
        exportar["responses"]["200"]["content"] = {"text/csv": {
            "schema": {"type": "string"},
            "example": "fecha;codigo_operacion;tipo;descripcion;monto;comision;importe;categoria;nota\n"
                       "2026-10-03T13:51:00;TRF26100313510000001;TRANSFERENCIA_ENVIADA;Transferencia a Carla R.;"
                       "15.00;0.00;-15.00;Familia;Cumpleaños de Carla\n",
        }}
    return esquema


def instalar(app) -> None:
    """Reemplaza la generación del esquema OpenAPI de la app por la versión con el contrato completo."""
    def openapi():
        if app.openapi_schema is None:
            app.openapi_schema = generar_contrato(app)
        return app.openapi_schema
    app.openapi = openapi
