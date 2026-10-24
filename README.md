# CS5383 · WebdriverIO en Qolqe

Laboratorio de automatización web de **CS5383 Pruebas y Verificación de Software** (UTEC, Clase 11).
**Grupo 3 · Sebastian y Maykol** · Herramienta: **WebdriverIO 10** · Módulo: **G3 Historial y categorías**.

Automatiza un *happy path* de Qolqe Wallet con el patrón **Page Object + Fixture**:

> Ana inicia sesión → va a *Movimientos* → crea la categoría "Viajes" → abre su último movimiento → lo clasifica en "Viajes" con la nota "Pasaje a Cusco" → se verifica el mensaje "Clasificación guardada", la fila actualizada y que la categoría cuenta "1 movimientos" (HU-G3-03 + HU-G3-07).

**Presentación:** https://claude.ai/artifact/LSnrwobCbcGrUv6VPg2Qu2

El repositorio es autocontenido: incluye una copia **sin modificar** del sistema bajo prueba (`qolqe/`), así que basta con clonar, instalar y ejecutar.

## Requisitos

| Herramienta | Versión |
|---|---|
| Python | 3.11 o superior (para Qolqe) |
| Node.js | **22.19 o superior** (lo exige WebdriverIO 10) |
| Navegador | Chrome o Chromium. Si no se encuentra, WebdriverIO descarga *Chrome for Testing* la primera vez. |

## 1. Instalación

```bash
git clone https://github.com/Maykol-Morales/cs5383-webdriverio.git
cd cs5383-webdriverio

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

npm install
```

## 2. Ejecución

**Terminal 1: levantar Qolqe** (déjela abierta)

```bash
source .venv/bin/activate          # Windows: .venv\Scripts\activate
uvicorn qolqe.main:app --port 8000
```

Qolqe queda en http://localhost:8000; la API está documentada en http://localhost:8000/docs.

**Terminal 2: correr la prueba**

```bash
npm test                           # sin ventana (headless)
HEADED=1 npm test                  # con ventana (Windows PowerShell: $env:HEADED=1; npm test)
```

Resultado esperado:

```
G3 · Historial y categorías
   ✓ Ana crea la categoría "Viajes" y clasifica su último movimiento
1 passing (3.3s)
```

Antes de cada prueba se reinician los datos de Qolqe (`POST /api/pruebas/reiniciar`), así que se puede ejecutar las veces que se quiera. Si una prueba falla, la captura queda en `evidencia/`.

| Variable | Uso |
|---|---|
| `HEADED` | Cualquier valor: ejecuta con ventana |
| `QOLQE_URL` | URL de Qolqe (por defecto `http://localhost:8000`) |
| `CHROME_BIN` | Ruta del navegador, si no es el Chrome por defecto (ej. `/usr/bin/chromium`) |

## 3. Demo guiada (Linux / macOS)

```bash
./demo.sh
```

Avanza con Enter: levanta Qolqe si no está corriendo (con la base de datos en `/tmp`), muestra la spec de IA, corre el flujo con ventana y luego cambia el oráculo a "2 movimientos" para mostrar que la prueba falla y deja evidencia. Al terminar, o con Ctrl+C, restaura la spec.

## 4. Capacidad de IA: `browser.act()`

`test/specs/clasificar-ia.e2e.js` repite el mismo flujo escrito como intención en lenguaje natural, con `@wdio/ai-service`. La primera ejecución usa un modelo para manejar el navegador y graba los comandos en `test/specs/__act__/`; las siguientes los repiten sin modelo y sin tokens. `act` solo ejecuta: las verificaciones siguen siendo `expect` en código.

Necesita una clave de API, que este repositorio **no incluye**. Sin clave ni caché, la spec se marca como *skipped*:

```bash
export ANTHROPIC_API_KEY=...       # o WDIO_AI_MODEL=ollama:<modelo> para uno local
npm run test:ia                    # 1ª vez: graba · siguientes: repite desde la caché
npm run test:ia:regrabar           # vuelve a grabar
npm run eject                      # convierte los pasos grabados en código WebdriverIO normal
```

## Estructura

```
qolqe/                        Qolqe Wallet (SUT, copia sin modificar del Proyecto 2)
docs/requisitos.md            historias de usuario y reglas (G3 en la sección 6)
wdio.conf.js                  navegador, URL, servicio de IA y fixture
test/pageobjects/
  login.page.js               ingresarComo(celular, pin)
  historial.page.js           abrir, crearCategoria, abrirPrimerMovimiento, clasificar
test/specs/
  clasificar.e2e.js           happy path con Page Objects
  clasificar-ia.e2e.js        mismo flujo con browser.act()
demo.sh                       guion de la demo en vivo
```

## Fuentes

- ISTQB (2024). *Certified Tester Foundation Level Syllabus* v4.0.1.
- W3C (2018). *WebDriver*. https://www.w3.org/TR/webdriver1/ · W3C (2025). *WebDriver BiDi*. https://www.w3.org/TR/webdriver-bidi/
- WebdriverIO: [Automation Protocols](https://webdriver.io/docs/automationProtocols) · [Auto-waiting](https://webdriver.io/docs/autowait) · [AI Steps in Tests](https://webdriver.io/docs/ai-steps) · [v10 release](https://webdriver.io/blog/2026/10/05/webdriverio-v10-release)
- Fowler, M. (2013). *PageObject* · selenium.dev, *Page object models*.
