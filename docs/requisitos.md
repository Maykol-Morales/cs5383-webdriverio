# Qolqe Wallet: Especificación de requisitos

## 1. Convenciones

| Tema | Convención |
|---|---|
| **Identificadores** | Historias: `HU-<módulo>-<n>` (por ejemplo, `HU-G1-03`). Criterios: `CA<n>` dentro de cada HU (por ejemplo, `HU-G1-03 CA2`). Reglas del núcleo: `RN-01` a `RN-11`. Reglas de cada módulo: `R-G<n>-<m>` |
| **Prioridad** | **Alta**: afecta dinero, seguridad o el flujo principal. **Media**: afecta una funcionalidad importante. **Baja**: comodidad o presentación. Sirve para priorizar las pruebas por riesgo |
| **Montos** | En soles (S/), con 2 decimales. La API los recibe como número o texto (`100`, `"100.50"`) y los devuelve como texto (`"100.50"`) |
| **Fechas** | Hora de Lima (UTC-5). Un "día" va de 00:00:00 a 23:59:59 en hora de Lima |
| **Errores** | Toda respuesta de error incluye un `codigo` estable y un mensaje (`detail`). En los criterios se indica el código esperado entre paréntesis, por ejemplo *(error `SALDO_INSUFICIENTE`)* |
| **Códigos HTTP** | 200 consulta o modificación correcta · 201 creación · 204 eliminación o cierre sin contenido · 401 no autenticado · 404 recurso inexistente **o de otro usuario** · 409 conflicto con el estado actual (duplicados, transiciones no permitidas) · 422 regla de negocio o dato inválido · 423 cuenta bloqueada |
| **Propiedad de los datos** | Un usuario **solo** puede ver o modificar sus propios recursos. Intentar acceder a un recurso de otro usuario responde como si no existiera (404) |
| **Notificaciones** | Los SMS son simulados. En el entorno de pruebas se consultan en `GET /api/pruebas/notificaciones?celular=...` |
| **Procesos diarios** | Las recargas programadas (G1) y los débitos automáticos (G2) los ejecuta un proceso diario. En el entorno de pruebas se dispara con `POST /api/pruebas/procesar-diario` |

### Actores

| Actor | Descripción |
|---|---|
| **Visitante** | Persona sin sesión iniciada |
| **Cliente** | Usuario registrado con sesión iniciada (token JWT vigente) |
| **Sistema** | Procesos automáticos: proceso diario, envío de SMS, antifraude |

---

## 2. Reglas de negocio del núcleo

| ID | Regla |
|---|---|
| RN-01 | El DNI tiene exactamente 8 dígitos numéricos. |
| RN-02 | El celular tiene 9 dígitos y empieza con 9. Es único en el sistema, incluso si la cuenta está cerrada. |
| RN-03 | El PIN tiene 4 dígitos. No puede tener todos los dígitos iguales (`1111`) ni ser una secuencia ascendente o descendente (`1234`, `4321`). |
| RN-04 | Tras **3 intentos fallidos consecutivos** de inicio de sesión, la cuenta se bloquea 15 minutos. Un inicio de sesión exitoso reinicia el conteo. |
| RN-05 | El monto de una transferencia es mayor a S/ 0.00, tiene como máximo 2 decimales y no supera **S/ 500.00 por operación**. |
| RN-06 | La suma de transferencias del día (a Qolqe e interbancarias) no supera el **límite diario vigente** del usuario (por defecto S/ 2,000.00). |
| RN-07 | No se puede transferir a uno mismo, a un celular no registrado ni a una cuenta cerrada. |
| RN-08 | El saldo nunca puede quedar negativo: el saldo debe cubrir el monto **más la comisión**. |
| RN-09 | Comisión: S/ 0.00 entre cuentas Qolqe. Las transferencias a otros bancos pagan 1.5 % del monto, con un mínimo de S/ 1.00 y un máximo de S/ 5.00, redondeado a 2 decimales (redondeo comercial: 0.005 sube). |
| RN-10 | Toda operación exitosa genera un movimiento con un **código de operación único**. Una transferencia entre cuentas Qolqe genera un movimiento en cada cuenta, con el mismo código. |
| RN-11 | Las operaciones financieras realizadas (transferencias, recargas, pagos) **no se pueden modificar ni eliminar**. |

---

## 3. Núcleo común (todos los grupos)

### HU-N-01 · Registrarme · Prioridad Alta
**Como** visitante **quiero** crear una cuenta con mi DNI y celular **para** usar la billetera.
- **CA1.** Con DNI, nombres (2 a 80 caracteres), celular, PIN y correo opcional válidos, la cuenta se crea con saldo S/ 0.00 y límite diario de S/ 2,000.00.
- **CA2.** DNI que no cumple RN-01 *(error `DNI_INVALIDO`)*.
- **CA3.** Celular que no cumple RN-02 *(error `CELULAR_INVALIDO`)*, o que ya está registrado *(error `CELULAR_REGISTRADO`, 409)*.
- **CA4.** PIN que no cumple RN-03 *(error `PIN_INVALIDO`)*.
- **CA5.** Correo con formato inválido *(error `CORREO_INVALIDO`)* o ya usado por otra cuenta activa, sin distinguir mayúsculas *(error `CORREO_REGISTRADO`, 409)*.
- **CA6.** Se envía un SMS de bienvenida al celular registrado.

### HU-N-02 · Iniciar sesión · Prioridad Alta
**Como** cliente **quiero** ingresar con mi celular y PIN **para** acceder a mi cuenta de forma segura.
- **CA1.** Con credenciales correctas recibo un token válido por 30 minutos y se crea una **sesión activa**.
- **CA2.** Con celular inexistente o PIN incorrecto recibo un mensaje genérico, sin revelar cuál dato falló *(error `CREDENCIALES_INVALIDAS`, 401)*.
- **CA3.** Se aplica RN-04. Al tercer intento fallido consecutivo la respuesta es *(error `CUENTA_BLOQUEADA`, 423)* y se envía un SMS de aviso.
- **CA4.** Durante el bloqueo, ni siquiera el PIN correcto permite ingresar (423). Pasados los 15 minutos puedo ingresar normalmente.
- **CA5.** Una cuenta cerrada no puede iniciar sesión *(error `CUENTA_CERRADA`, 401)*.
- **CA6.** Si envío el identificador de un dispositivo que **no** está en mis dispositivos de confianza (HU-G6-05), puedo ingresar, pero recibo un SMS de alerta de "nuevo dispositivo".

### HU-N-03 · Cerrar sesión · Prioridad Alta
**Como** cliente **quiero** cerrar mi sesión **para** que nadie use mi cuenta desde este equipo.
- **CA1.** Al cerrar sesión, el token deja de ser válido: cualquier uso posterior responde 401.
- **CA2.** Cerrar sesión no afecta mis otras sesiones activas.

### HU-N-04 · Consultar mi saldo y perfil · Prioridad Alta
- **CA1.** Veo mi saldo disponible, la moneda (PEN) y la fecha de la última actualización.
- **CA2.** Veo mi perfil: nombres, celular, correo y DNI **enmascarado** (solo los últimos 4 dígitos).
- **CA3.** Sin token o con token vencido o inválido *(error `NO_AUTENTICADO`, 401)*.

### HU-N-05 · Editar mi perfil · Prioridad Media
**Como** cliente **quiero** actualizar mis nombres y mi correo **para** mantener mis datos al día.
- **CA1.** Puedo modificar nombres (2 a 80 caracteres) y correo (formato válido, único entre cuentas activas sin distinguir mayúsculas) *(errores `PERFIL_INVALIDO`, `CORREO_INVALIDO`, `CORREO_REGISTRADO` 409)*.
- **CA2.** El DNI y el celular **no** se pueden modificar: si se envían, se ignoran.
- **CA3.** Al cambiar el correo se envía un SMS de aviso.

### HU-N-06 · Cerrar mi cuenta · Prioridad Media
**Como** cliente **quiero** cerrar mi cuenta **para** dejar de usar Qolqe.
- **CA1.** Debo confirmar con mi PIN *(error `PIN_INCORRECTO`)*.
- **CA2.** Solo puedo cerrarla con saldo exactamente S/ 0.00 *(error `SALDO_PENDIENTE`)*.
- **CA3.** No puedo cerrarla si tengo solicitudes de dinero pendientes (no vencidas), enviadas o recibidas *(error `SOLICITUDES_PENDIENTES`, 409)*.
- **CA4.** Al cerrarla, todas mis sesiones se cierran, no puedo volver a ingresar y nadie puede transferirme (RN-07).

### HU-N-07 · Transferir a otro usuario Qolqe · Prioridad Alta
**Como** cliente **quiero** enviar dinero a otro celular de Qolqe **para** pagarle de inmediato.
- **CA1.** Indico el celular de destino (o un contacto) y el monto; opcionalmente una descripción de hasta 60 caracteres.
- **CA2.** Se validan RN-05, RN-06, RN-07 y RN-08 *(errores `MONTO_INVALIDO`, `LIMITE_DIARIO_EXCEDIDO`, `TRANSFERENCIA_A_SI_MISMO`, `DESTINO_NO_REGISTRADO` 404, `DESTINO_INACTIVO`, `SALDO_INSUFICIENTE`)*.
- **CA3.** Si es exitosa: se debita mi saldo, se acredita al destinatario, ambos vemos el movimiento con el mismo código (RN-10) y el destinatario recibe un SMS.
- **CA4.** El comprobante muestra el código de operación, el destinatario (nombre enmascarado y celular), el monto, la comisión, el total, mi nuevo saldo y la fecha.
- **CA5.** Las reglas se cumplen **también bajo concurrencia**: varias transferencias simultáneas no pueden superar el límite diario ni dejar el saldo negativo.

### HU-N-08 · Transferir a otro banco · Prioridad Alta
- **CA1.** Indico un CCI de 20 dígitos *(error `CCI_INVALIDO`)* y el monto.
- **CA2.** Se cobra la comisión de RN-09 y se aplican RN-05, RN-06 y RN-08.
- **CA3.** El movimiento muestra el CCI enmascarado (solo los últimos 4 dígitos).

### HU-N-09 · Simular la comisión · Prioridad Media
- **CA1.** Antes de transferir puedo ver el monto, la comisión y el total según el tipo de transferencia, sin que se realice ninguna operación.

---

## 4. G1 · Recargas de celular

**Reglas del módulo**

| ID | Regla |
|---|---|
| R-G1-01 | Montos permitidos: S/ 5, 10, 20, 30, 50 y 100. |
| R-G1-02 | Recargas **desde** S/ 30 reciben un bono de 5 % del monto, redondeado a 2 decimales, con un tope de S/ 4.00. |
| R-G1-03 | Máximo **5 recargas por día** al mismo número, sumando las manuales y las programadas. |
| R-G1-04 | Máximo **3 recargas programadas en estado ACTIVA** por usuario. |
| R-G1-05 | El día de ejecución de una programada va de 1 a 28. No puede haber dos programadas (no eliminadas) al mismo número el mismo día. |

### HU-G1-01 · Recargar un celular · Prioridad Alta
- **CA1.** Indico un celular que cumpla RN-02 y un monto de R-G1-01 *(errores `CELULAR_INVALIDO`, `MONTO_NO_PERMITIDO`)*.
- **CA2.** Se descuenta el monto de mi saldo, se aplica el bono de R-G1-02 y el número recargado recibe un SMS con el monto y el bono.
- **CA3.** Se aplica R-G1-03 *(error `LIMITE_RECARGAS`)* y RN-08 *(error `SALDO_INSUFICIENTE`)*.
- **CA4.** La interfaz muestra el bono estimado antes de confirmar, y debe coincidir con el bono del comprobante.

### HU-G1-02 · Ver mis recargas · Prioridad Baja
- **CA1.** Veo mis últimas 20 recargas, de la más reciente a la más antigua, con número, monto, bono, fecha y origen (MANUAL o PROGRAMADA).

### HU-G1-03 · Programar una recarga · Prioridad Media
**Como** cliente **quiero** programar una recarga mensual **para** no quedarme sin saldo en mi línea.
- **CA1.** Indico el celular, un monto de R-G1-01, el día del mes (R-G1-05) y un alias opcional de hasta 20 caracteres *(error `PROGRAMACION_INVALIDA`)*.
- **CA2.** Se crea en estado **ACTIVA**, con la **próxima ejecución** en la siguiente fecha con ese día: este mes si el día aún no pasó, o el mes siguiente si ya pasó o es hoy.
- **CA3.** Se aplican R-G1-04 *(error `LIMITE_PROGRAMADAS`)* y la regla de duplicados de R-G1-05 *(error `PROGRAMACION_DUPLICADA`, 409)*.

### HU-G1-04 · Ver mis recargas programadas · Prioridad Media
- **CA1.** Veo cada programada con su número, alias, monto, día, estado, próxima ejecución y el resultado de su última ejecución (EXITOSA, FALLIDA o "sin ejecuciones").

### HU-G1-05 · Editar, pausar o reanudar una programada · Prioridad Media
- **CA1.** Puedo cambiar el monto, el día o el alias. Si cambio el día, la próxima ejecución se recalcula como en HU-G1-03 CA2.
- **CA2.** Al **pausar**, no se ejecuta mientras esté en ese estado. Al **reanudar**, se aplica R-G1-04 y la próxima ejecución se recalcula desde hoy.
- **CA3.** Pausar una programada ya pausada, o reanudar una activa, no está permitido *(error `ESTADO_INVALIDO`, 409)*.

### HU-G1-06 · Eliminar una programada · Prioridad Baja
- **CA1.** La programada deja de mostrarse y no se vuelve a ejecutar. Las recargas que ya realizó se conservan (RN-11).

### HU-G1-07 · Ejecución automática de programadas · Prioridad Alta · Actor: Sistema
- **CA1.** El proceso diario ejecuta las programadas **ACTIVAS** cuya próxima ejecución es hoy o una fecha anterior.
- **CA2.** La ejecución es una recarga normal: aplica el bono y cuenta para R-G1-03.
- **CA3.** Si no hay saldo suficiente o se alcanzó R-G1-03, la ejecución queda como **FALLIDA**, no se descuenta nada y el titular recibe un SMS con el motivo.
- **CA4.** Haya sido exitosa o fallida, la próxima ejecución pasa al mes siguiente. Si había varias ejecuciones atrasadas, **solo se ejecuta una vez**.
- **CA5.** Ejecutar el proceso dos veces el mismo día no duplica recargas.

---

## 5. G2 · Pago de servicios

**Reglas del módulo**

| ID | Regla |
|---|---|
| R-G2-01 | El código de suministro tiene entre 8 y 12 dígitos. |
| R-G2-02 | Solo se pagan deudas pendientes y por su monto total. |
| R-G2-03 | Mora de 0.5 % diario por cada día de atraso **después** del vencimiento, con un tope de 10 % del monto. Pagar el mismo día del vencimiento no genera mora. |
| R-G2-04 | Una deuda con **más de 60 días** de atraso pasa a cobranza y no se puede pagar en Qolqe (con 60 días todavía se puede). |
| R-G2-05 | Máximo **8 servicios afiliados** por usuario, sin repetir la combinación empresa + suministro. |

### HU-G2-01 · Consultar deudas de un suministro · Prioridad Alta
- **CA1.** Elijo la empresa *(error `EMPRESA_NO_ENCONTRADA`, 404)* e ingreso el suministro (R-G2-01) *(error `SUMINISTRO_INVALIDO`)*.
- **CA2.** Veo todas las deudas pendientes, de la más antigua a la más reciente, con periodo, titular enmascarado, monto, vencimiento, días de atraso, mora, total y estado (PENDIENTE o EN_COBRANZA).
- **CA3.** Si no hay deudas pendientes *(error `SIN_DEUDA_PENDIENTE`, 404)*.

### HU-G2-02 · Pagar una deuda · Prioridad Alta
- **CA1.** Se paga el monto más la mora (R-G2-03) y se descuenta de mi saldo. Aplica RN-08 *(error `SALDO_INSUFICIENTE`)*.
- **CA2.** Deuda inexistente *(error `DEUDA_NO_ENCONTRADA`, 404)*, ya pagada *(error `DEUDA_YA_PAGADA`, 409)* o en cobranza *(error `DEUDA_EN_COBRANZA`)*.
- **CA3.** Dos pagos simultáneos de la misma deuda: solo uno debe ser exitoso.
- **CA4.** El comprobante muestra el código de operación, la empresa, el suministro, el periodo, el monto, la mora, el total y mi nuevo saldo.

### HU-G2-03 · Afiliar un servicio · Prioridad Media
**Como** cliente **quiero** guardar mis servicios frecuentes **para** consultarlos y pagarlos sin escribir el suministro cada vez.
- **CA1.** Indico la empresa, el suministro (R-G2-01) y un alias de 3 a 20 caracteres *(error `AFILIACION_INVALIDA`)*.
- **CA2.** El suministro debe existir en la empresa, es decir, tener al menos un recibo registrado, pendiente o pagado *(error `SUMINISTRO_NO_ENCONTRADO`, 404)*.
- **CA3.** Se aplica R-G2-05 *(errores `LIMITE_AFILIACIONES`, `AFILIACION_DUPLICADA` 409)*.
- **CA4.** La afiliación se crea con el débito automático **desactivado**.

### HU-G2-04 · Ver mis servicios afiliados · Prioridad Media
- **CA1.** Veo cada afiliación con alias, empresa, suministro, total pendiente, próximo vencimiento, estado del débito automático y una situación: **AL_DIA** (sin deudas), **CON_DEUDA** o **EN_COBRANZA** (alguna deuda en cobranza).

### HU-G2-05 · Editar una afiliación y su débito automático · Prioridad Media
- **CA1.** Puedo cambiar el alias y activar o desactivar el débito automático.
- **CA2.** **Débito automático (actor Sistema):** el proceso diario paga, el **día de su vencimiento**, las deudas pendientes de afiliaciones con débito activo (sin mora).
- **CA3.** Si no hay saldo, la deuda queda pendiente y el titular recibe un SMS.
- **CA4.** Las deudas ya vencidas antes de activar el débito **no** se pagan automáticamente.

### HU-G2-06 · Desafiliar un servicio · Prioridad Baja
- **CA1.** Puedo eliminar una afiliación. Las deudas y los pagos realizados no se modifican.
- **CA2.** No puedo desafiliar un servicio con el débito automático activo: primero debo desactivarlo *(error `DEBITO_ACTIVO`, 409)*.

### HU-G2-07 · Ver mis pagos y comprobantes · Prioridad Media
- **CA1.** Veo mis pagos realizados, del más reciente al más antiguo, y puedo filtrarlos por afiliación.
- **CA2.** Puedo ver el comprobante de un pago por su código de operación. El comprobante de un pago de otro usuario responde 404.

---

## 6. G3 · Historial y categorías

**Reglas del módulo**

| ID | Regla |
|---|---|
| R-G3-01 | Rango de consulta: `desde` ≤ `hasta`, máximo 90 días, `hasta` no puede ser futura. Por defecto, los últimos 30 días hasta hoy, **incluyendo los movimientos de hoy**. |
| R-G3-02 | 10 movimientos por página, del más reciente al más antiguo. La página es mayor o igual a 1. |
| R-G3-03 | Máximo **10 categorías** por usuario. Nombre de 3 a 20 caracteres, único sin distinguir mayúsculas. Color de una paleta fija de 8 colores. |
| R-G3-04 | La nota de un movimiento tiene como máximo 100 caracteres. |

### HU-G3-01 · Consultar mis movimientos · Prioridad Alta
- **CA1.** Puedo filtrar por rango de fechas (R-G3-01), por tipo (TRANSFERENCIA_ENVIADA, TRANSFERENCIA_RECIBIDA, RECARGA, PAGO_SERVICIO) y por categoría *(error `FILTRO_INVALIDO`)*.
- **CA2.** El rango incluye completos los días `desde` y `hasta`.
- **CA3.** Se pagina según R-G3-02, indicando el total de movimientos y el total de páginas.
- **CA4.** Cada movimiento muestra fecha, tipo, descripción, contraparte, monto, comisión, importe (negativo si es un cargo), saldo posterior, categoría y nota.

### HU-G3-02 · Ver el detalle de un movimiento · Prioridad Alta
- **CA1.** Por su código de operación veo el detalle de **mi** movimiento.
- **CA2.** El código de un movimiento de otro usuario responde 404 *(error `MOVIMIENTO_NO_ENCONTRADO`)*.

### HU-G3-03 · Crear una categoría · Prioridad Media
**Como** cliente **quiero** crear categorías propias **para** organizar mis gastos.
- **CA1.** Indico un nombre y un color de la paleta (R-G3-03) *(errores `CATEGORIA_INVALIDA`, `CATEGORIA_DUPLICADA` 409, `LIMITE_CATEGORIAS`)*.

### HU-G3-04 · Ver mis categorías · Prioridad Baja
- **CA1.** Veo mis categorías en orden alfabético, con la cantidad de movimientos asignados a cada una.

### HU-G3-05 · Editar una categoría · Prioridad Baja
- **CA1.** Puedo cambiar el nombre o el color, con las mismas reglas de R-G3-03 (sin compararla consigo misma).

### HU-G3-06 · Eliminar una categoría · Prioridad Media
- **CA1.** La categoría se elimina y sus movimientos quedan **sin categoría**; los movimientos no se borran ni cambian de monto.

### HU-G3-07 · Clasificar un movimiento · Prioridad Media
- **CA1.** Puedo asignar una de **mis** categorías a uno de **mis** movimientos, o quitarle la categoría.
- **CA2.** Puedo agregar o editar una nota (R-G3-04) *(error `NOTA_INVALIDA`)*.
- **CA3.** Una categoría de otro usuario o un movimiento ajeno responde 404.
- **CA4.** Clasificar no modifica el monto, la fecha ni el tipo del movimiento (RN-11).

### HU-G3-08 · Exportar mis movimientos · Prioridad Media
- **CA1.** Descargo un archivo CSV con los mismos filtros de HU-G3-01 (sin paginar) y las mismas reglas de rango.
- **CA2.** Columnas: `fecha;codigo_operacion;tipo;descripcion;monto;comision;importe;categoria;nota`. Separador punto y coma, punto decimal, codificación UTF-8 y una fila de encabezado.
- **CA3.** Si no hay movimientos, el archivo contiene solo el encabezado.

---

## 7. G4 · Contactos y solicitudes de dinero

**Reglas del módulo**

| ID | Regla |
|---|---|
| R-G4-01 | Un contacto es un celular registrado y activo, distinto del propio, sin repetirse. |
| R-G4-02 | Alias: se eliminan los espacios al inicio y al final; de 3 a 20 caracteres; solo letras (incluidas tildes y ñ), números y espacios; único sin distinguir mayúsculas. |
| R-G4-03 | Máximo **15 contactos** y **5 favoritos** por usuario. |
| R-G4-04 | Una solicitud de dinero se envía **a un contacto**, con un monto válido según RN-05 y un motivo de 3 a 60 caracteres. Máximo 10 solicitudes pendientes enviadas por usuario. |
| R-G4-05 | Estados de una solicitud: **PENDIENTE** → ACEPTADA, RECHAZADA, CANCELADA o VENCIDA. Una solicitud vence a las **48 horas** de creada. Solo una solicitud PENDIENTE puede cambiar de estado. |

### HU-G4-01 · Agregar un contacto · Prioridad Alta
- **CA1.** Indico el celular y un alias. Se aplican R-G4-01 a R-G4-03 *(errores `CELULAR_INVALIDO`, `CONTACTO_PROPIO`, `CELULAR_NO_REGISTRADO` 404, `CONTACTO_EXISTENTE` 409, `ALIAS_INVALIDO`, `ALIAS_DUPLICADO` 409, `LIMITE_CONTACTOS`)*. Un celular de una cuenta cerrada se trata como no registrado.

### HU-G4-02 · Ver y buscar mis contactos · Prioridad Media
- **CA1.** Veo mis contactos: primero los favoritos y luego el resto, ordenados por alias. 10 por página, indicando el total.
- **CA2.** Puedo buscar por parte del alias, sin distinguir mayúsculas ni tildes ("jose" encuentra "José").
- **CA3.** Cada contacto muestra alias, nombre enmascarado, celular y si es favorito.

### HU-G4-03 · Editar un contacto · Prioridad Media
- **CA1.** Puedo cambiar el alias (R-G4-02, sin compararlo consigo mismo) y marcarlo o desmarcarlo como favorito (R-G4-03 *(error `LIMITE_FAVORITOS`)*).

### HU-G4-04 · Eliminar un contacto · Prioridad Baja
- **CA1.** El contacto se elimina de mi lista. Las transferencias realizadas se conservan.
- **CA2.** No puedo eliminar un contacto con el que tengo solicitudes PENDIENTES (no vencidas), enviadas o recibidas *(error `SOLICITUDES_PENDIENTES`, 409)*.

### HU-G4-05 · Transferir a un contacto · Prioridad Alta
- **CA1.** Puedo transferir eligiendo un contacto en lugar de escribir el celular. Aplican todas las reglas de HU-N-07.

### HU-G4-06 · Solicitar dinero a un contacto · Prioridad Alta
**Como** cliente **quiero** pedirle dinero a un contacto **para** cobrarle una deuda sin tener que recordárselo.
- **CA1.** Indico el contacto, el monto y el motivo (R-G4-04) *(errores `SOLICITUD_INVALIDA`, `LIMITE_SOLICITUDES`)*.
- **CA2.** La solicitud se crea en estado PENDIENTE, con fecha de vencimiento a las 48 horas, y el destinatario recibe un SMS.

### HU-G4-07 · Ver mis solicitudes · Prioridad Media
- **CA1.** Veo las solicitudes **enviadas** y las **recibidas** por separado, y puedo filtrarlas por estado.
- **CA2.** Una solicitud PENDIENTE cuyo plazo ya pasó se muestra como **VENCIDA**.

### HU-G4-08 · Aceptar una solicitud recibida · Prioridad Alta
- **CA1.** Al aceptar, se realiza una transferencia de mi cuenta al solicitante por el monto pedido, con **todas** las reglas de HU-N-07 (saldo, límite diario, etc.).
- **CA2.** Si la transferencia no se puede realizar, la solicitud sigue PENDIENTE y recibo el error de la transferencia.
- **CA3.** Si se realiza, la solicitud pasa a ACEPTADA, queda asociada al código de operación y el solicitante recibe un SMS.
- **CA4.** Solo el destinatario puede aceptarla (para cualquier otro usuario responde 404), y solo si está PENDIENTE y no vencida *(error `ESTADO_INVALIDO`, 409)*.

### HU-G4-09 · Rechazar una solicitud recibida · Prioridad Media
- **CA1.** Puedo rechazarla con un motivo opcional de hasta 60 caracteres. Pasa a RECHAZADA y el solicitante recibe un SMS. Aplica la restricción de estado de HU-G4-08 CA4.

### HU-G4-10 · Cancelar una solicitud enviada · Prioridad Media
- **CA1.** Solo el solicitante puede cancelarla (para cualquier otro usuario responde 404), y solo si está PENDIENTE y no vencida *(error `ESTADO_INVALIDO`, 409)*. Pasa a CANCELADA.

---

## 8. G5 · Límites y alertas de consumo

**Reglas del módulo**

| ID | Regla |
|---|---|
| R-G5-01 | El límite diario va de S/ 100 a S/ 2,000, en múltiplos de S/ 50. |
| R-G5-02 | Una **reducción** del límite es inmediata y **cancela** cualquier aumento pendiente. Un **aumento** entra en vigencia 24 horas después; mientras tanto, rige el límite anterior. |
| R-G5-03 | Máximo **5 alertas** por usuario. Umbral de S/ 10 a S/ 2,000, en múltiplos de S/ 10. No puede haber dos alertas con el mismo tipo y el mismo umbral. |
| R-G5-04 | Tipos de alerta: TRANSFERENCIAS, RECARGAS, PAGOS o TODAS. Para TRANSFERENCIAS y TODAS, el umbral no puede superar el límite diario vigente. |
| R-G5-05 | Gasto del día por tipo, con las operaciones realizadas hoy: transferencias por su monto (sin comisión), recargas por su monto y pagos de servicios por su total pagado. TODAS suma los tres tipos. |

### HU-G5-01 · Ver mis límites · Prioridad Media
- **CA1.** Veo el límite por operación (S/ 500.00), el límite diario vigente, el aumento pendiente con su fecha de vigencia (si existe), lo usado hoy (RN-06) y lo disponible.

### HU-G5-02 · Cambiar mi límite diario · Prioridad Alta
- **CA1.** Se aplican R-G5-01 *(error `LIMITE_INVALIDO`)* y R-G5-02. La respuesta indica si el cambio fue INMEDIATO o PROGRAMADO.
- **CA2.** Recibo un SMS con el resultado del cambio.
- **CA3.** Si una reducción deja el límite por debajo del umbral de alertas de tipo TRANSFERENCIAS o TODAS, esas alertas pasan automáticamente a PAUSADA.

### HU-G5-03 · Respetar el límite al transferir · Prioridad Alta
- **CA1.** Toda transferencia (Qolqe, interbancaria o por solicitud aceptada) respeta RN-06 con el límite **vigente** al momento de la operación.
- **CA2.** La regla se cumple también con transferencias simultáneas (HU-N-07 CA5).

### HU-G5-04 · Crear una alerta de consumo · Prioridad Media
**Como** cliente **quiero** recibir un aviso cuando gasto más de cierto monto en el día **para** controlar mis gastos.
- **CA1.** Indico el tipo y el umbral (R-G5-03, R-G5-04) *(errores `ALERTA_INVALIDA`, `ALERTA_DUPLICADA` 409, `LIMITE_ALERTAS`)*.
- **CA2.** La alerta se crea en estado ACTIVA.

### HU-G5-05 · Ver mis alertas · Prioridad Baja
- **CA1.** Veo cada alerta con su tipo, umbral, estado (ACTIVA o PAUSADA), gasto de hoy de ese tipo y la fecha de su última notificación.

### HU-G5-06 · Editar, pausar o reanudar una alerta · Prioridad Media
- **CA1.** Puedo cambiar el umbral (con las reglas de R-G5-03 y R-G5-04) y pausarla o reanudarla.
- **CA2.** Reanudar una alerta cuyo umbral supera el límite vigente no está permitido *(error `ALERTA_INVALIDA`)*.

### HU-G5-07 · Eliminar una alerta · Prioridad Baja
- **CA1.** La alerta se elimina y deja de notificar.

### HU-G5-08 · Recibir la notificación de la alerta · Prioridad Alta · Actor: Sistema
- **CA1.** Cuando una operación hace que el gasto del día (R-G5-05) **alcance o supere** el umbral de una alerta ACTIVA de ese tipo, recibo un SMS.
- **CA2.** Cada alerta notifica **como máximo una vez por día**.
- **CA3.** Las alertas PAUSADAS no notifican.

---

## 9. G6 · Seguridad

**Reglas del módulo**

| ID | Regla |
|---|---|
| R-G6-01 | El nuevo PIN cumple RN-03, es distinto de los **últimos 3 PIN** usados (incluido el actual) y no coincide con los últimos 4 dígitos del celular. |
| R-G6-02 | El código de desbloqueo tiene 6 dígitos, vence a los 5 minutos y admite 3 intentos. Solicitar un código nuevo invalida el anterior. |
| R-G6-03 | Máximo **3 dispositivos de confianza**. Nombre de 3 a 30 caracteres, único sin distinguir mayúsculas. Tipo: CELULAR, TABLET o COMPUTADORA. |
| R-G6-04 | Cada inicio de sesión crea una **sesión**, que dura lo mismo que su token (30 minutos). Una sesión cerrada invalida su token de inmediato. |

### HU-G6-01 · Cambiar mi PIN · Prioridad Alta
- **CA1.** Debo indicar mi PIN actual *(error `PIN_ACTUAL_INCORRECTO`)* y un nuevo PIN que cumpla R-G6-01 *(errores `PIN_INVALIDO`, `PIN_REUTILIZADO`)*.
- **CA2.** Al cambiarlo, recibo un SMS y **se cierran todas mis demás sesiones**; la sesión actual sigue activa.
- **CA3.** Después del cambio solo funciona el nuevo PIN.

### HU-G6-02 · Bloqueo por intentos fallidos · Prioridad Alta
- **CA1.** Se cumple RN-04 tal como se describe en HU-N-02 CA3 y CA4.
- **CA2.** Los intentos deben ser **consecutivos**: un ingreso exitoso reinicia el conteo.

### HU-G6-03 · Solicitar un código de desbloqueo · Prioridad Alta
- **CA1.** Indico mi celular. Si la cuenta está bloqueada, recibo un SMS con un código (R-G6-02).
- **CA2.** La respuesta es siempre la misma, exista o no la cuenta y esté o no bloqueada, para no revelar información.

### HU-G6-04 · Desbloquear mi cuenta con el código · Prioridad Alta
- **CA1.** Con el código correcto y vigente, la cuenta se desbloquea y puedo ingresar.
- **CA2.** Código incorrecto *(error `CODIGO_INCORRECTO`, que indica los intentos restantes)*; al tercer error el código se anula *(error `CODIGO_ANULADO`)*; código vencido *(error `CODIGO_EXPIRADO`)*; sin código activo *(error `CODIGO_INVALIDO`)*.

### HU-G6-05 · Registrar un dispositivo de confianza · Prioridad Media
**Como** cliente **quiero** registrar mis dispositivos **para** que me avisen si alguien ingresa desde otro.
- **CA1.** Indico el nombre, el tipo (R-G6-03) y confirmo con mi PIN *(errores `DISPOSITIVO_INVALIDO`, `DISPOSITIVO_DUPLICADO` 409, `LIMITE_DISPOSITIVOS`, `PIN_INCORRECTO`)*.
- **CA2.** El sistema devuelve un **identificador de dispositivo**, que se envía al iniciar sesión (HU-N-02 CA6).

### HU-G6-06 · Ver mis dispositivos · Prioridad Baja
- **CA1.** Veo nombre, tipo, fecha de registro y fecha del último inicio de sesión desde cada dispositivo.

### HU-G6-07 · Renombrar un dispositivo · Prioridad Baja
- **CA1.** Puedo cambiar el nombre con las reglas de R-G6-03.

### HU-G6-08 · Eliminar un dispositivo · Prioridad Media
- **CA1.** El dispositivo se elimina. Los inicios de sesión posteriores desde ese identificador generan la alerta de "nuevo dispositivo".

### HU-G6-09 · Ver mis sesiones activas · Prioridad Media
- **CA1.** Veo mis sesiones vigentes con su fecha de inicio, fecha de vencimiento, el dispositivo (si se indicó) y cuál es la sesión **actual**.
- **CA2.** Las sesiones cerradas o vencidas no se muestran.

### HU-G6-10 · Cerrar sesiones · Prioridad Alta
- **CA1.** Puedo cerrar una sesión específica: su token deja de funcionar de inmediato (R-G6-04).
- **CA2.** Puedo cerrar **todas mis sesiones excepto la actual**.
- **CA3.** No puedo cerrar sesiones de otro usuario (404).

---

## Anexo A · Endpoints por historia de usuario

La documentación completa (esquemas de entrada y salida) está en `/docs` de la aplicación.

| Módulo | Historias | Endpoints |
|---|---|---|
| Núcleo | HU-N-01 | `POST /api/usuarios` |
| | HU-N-02, HU-N-03 | `POST /api/auth/login` · `POST /api/auth/logout` |
| | HU-N-04 a HU-N-06 | `GET /api/cuentas/me` · `GET /api/cuentas/me/saldo` · `PUT /api/cuentas/me` · `POST /api/cuentas/me/cierre` |
| | HU-N-07 a HU-N-09 | `POST /api/transferencias` · `GET /api/transferencias/comision` |
| G1 | HU-G1-01, HU-G1-02 | `GET /api/recargas/configuracion` · `GET /api/recargas` · `POST /api/recargas` |
| | HU-G1-03 a HU-G1-06 | `GET` · `POST /api/recargas/programadas` · `PUT` · `DELETE /api/recargas/programadas/{id}` · `POST /api/recargas/programadas/{id}/pausar` · `POST .../reanudar` |
| G2 | HU-G2-01, HU-G2-02 | `GET /api/servicios/empresas` · `GET /api/servicios/deudas` · `POST /api/servicios/pagos` |
| | HU-G2-03 a HU-G2-06 | `GET` · `POST /api/servicios/afiliaciones` · `PUT` · `DELETE /api/servicios/afiliaciones/{id}` |
| | HU-G2-07 | `GET /api/servicios/pagos` · `GET /api/servicios/pagos/{codigo_operacion}` |
| G3 | HU-G3-01, HU-G3-02 | `GET /api/movimientos` · `GET /api/movimientos/{codigo_operacion}` |
| | HU-G3-03 a HU-G3-06 | `GET` · `POST /api/categorias` · `PUT` · `DELETE /api/categorias/{id}` |
| | HU-G3-07, HU-G3-08 | `PUT /api/movimientos/{codigo_operacion}/clasificacion` · `GET /api/movimientos/exportar` |
| G4 | HU-G4-01 a HU-G4-04 | `GET` · `POST /api/contactos` · `PUT` · `DELETE /api/contactos/{id}` |
| | HU-G4-06 a HU-G4-10 | `GET` · `POST /api/solicitudes` · `POST /api/solicitudes/{id}/aceptar` · `.../rechazar` · `.../cancelar` |
| G5 | HU-G5-01, HU-G5-02 | `GET` · `PUT /api/limites` |
| | HU-G5-04 a HU-G5-07 | `GET` · `POST /api/limites/alertas` · `PUT` · `DELETE /api/limites/alertas/{id}` |
| G6 | HU-G6-01 | `PUT /api/seguridad/pin` |
| | HU-G6-03, HU-G6-04 | `POST /api/seguridad/desbloqueo/solicitar` · `POST /api/seguridad/desbloqueo/confirmar` |
| | HU-G6-05 a HU-G6-08 | `GET` · `POST /api/seguridad/dispositivos` · `PUT` · `DELETE /api/seguridad/dispositivos/{id}` |
| | HU-G6-09, HU-G6-10 | `GET /api/seguridad/sesiones` · `DELETE /api/seguridad/sesiones/{id}` · `DELETE /api/seguridad/sesiones` |
| Soporte de pruebas | — | `POST /api/pruebas/reiniciar` · `GET/PUT/DELETE /api/pruebas/reloj` · `GET /api/pruebas/notificaciones` · `PUT /api/pruebas/saldo` · `POST /api/pruebas/procesar-diario` |
