# CS5383 · WebdriverIO en Qolqe

[![Pruebas](https://github.com/Maykol-Morales/cs5383-webdriverio/actions/workflows/pruebas.yml/badge.svg)](https://github.com/Maykol-Morales/cs5383-webdriverio/actions/workflows/pruebas.yml)

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

En Windows, instale Python marcando **"Add python.exe to PATH"**. Compruebe en una terminal nueva que `python --version` y `node --version` respondan.

## 1. Instalación

Probado en **Windows** y Linux (ver la insignia de CI). Los comandos no necesitan activar la `.venv`, así se evita el bloqueo de scripts de PowerShell.

**Windows (PowerShell o CMD)**

```powershell
git clone https://github.com/Maykol-Morales/cs5383-webdriverio.git
cd cs5383-webdriverio
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
npm install
```

**Linux / macOS**

```bash
git clone https://github.com/Maykol-Morales/cs5383-webdriverio.git
cd cs5383-webdriverio
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm install
```

## 2. Demo guiada (recomendado)

```bash
npm run demo
```

Funciona igual en Windows, Linux y macOS. Avanza con Enter:

1. Levanta Qolqe en http://localhost:8000 si no está corriendo (con una base de datos temporal) y lo apaga al terminar.
2. Muestra la spec de IA escrita en lenguaje natural.
3. Corre el happy path con Chrome visible.
4. Cambia el oráculo a "2 movimientos" para mostrar que la prueba falla y deja una captura en `evidencia/`.
5. Restaura la spec, también si se interrumpe con Ctrl+C.

## 3. Ejecución manual

**Terminal 1: levantar Qolqe** (déjela abierta)

```bash
.venv\Scripts\python -m uvicorn qolqe.main:app --port 8000     # Windows
.venv/bin/python -m uvicorn qolqe.main:app --port 8000          # Linux / macOS
```

Qolqe queda en http://localhost:8000; la API está documentada en http://localhost:8000/docs.

**Terminal 2: correr la prueba**

```bash
npm test
```

Para ver el navegador, active `HEADED` antes de `npm test`:

| Terminal | Comando |
|---|---|
| PowerShell | `$env:HEADED=1; npm test` |
| CMD | `set HEADED=1 && npm test` |
| Linux / macOS | `HEADED=1 npm test` |

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
| `CHROME_BIN` | Ruta del navegador, si no es el Chrome por defecto |

## 4. Capacidad de IA: `browser.act()`

`test/specs/clasificar-ia.e2e.js` repite el mismo flujo escrito como intención en lenguaje natural, con `@wdio/ai-service`. La primera ejecución usa un modelo para manejar el navegador y graba los comandos en `test/specs/__act__/`; las siguientes los repiten sin modelo y sin tokens. `act` solo ejecuta: las verificaciones siguen siendo `expect` en código.

Necesita una clave de API, que este repositorio **no incluye**. Sin clave ni caché, la spec se marca como *skipped*:

```bash
export ANTHROPIC_API_KEY=...       # PowerShell: $env:ANTHROPIC_API_KEY="..."
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
demo.mjs                      guion de la demo en vivo (npm run demo)
```

## Fuentes

- ISTQB (2024). *Certified Tester Foundation Level Syllabus* v4.0.1.
- W3C (2018). *WebDriver*. https://www.w3.org/TR/webdriver1/ · W3C (2025). *WebDriver BiDi*. https://www.w3.org/TR/webdriver-bidi/
- WebdriverIO: [Automation Protocols](https://webdriver.io/docs/automationProtocols) · [Auto-waiting](https://webdriver.io/docs/autowait) · [AI Steps in Tests](https://webdriver.io/docs/ai-steps) · [v10 release](https://webdriver.io/blog/2026/10/05/webdriverio-v10-release)
- Fowler, M. (2013). *PageObject* · selenium.dev, *Page object models*.
