# CS5383 · WebdriverIO en Qolqe

[![Pruebas](https://github.com/Maykol-Morales/cs5383-webdriverio/actions/workflows/pruebas.yml/badge.svg)](https://github.com/Maykol-Morales/cs5383-webdriverio/actions/workflows/pruebas.yml)

Laboratorio de automatización web de **CS5383 Pruebas y Verificación de Software** (UTEC, Clase 11).
**Grupo 3 · Sebastian y Maykol** · Herramienta: **WebdriverIO 10** · Módulo: **G3 Historial y categorías**.

Automatiza un *happy path* de Qolqe Wallet con **BDD (Cucumber + Gherkin)**, el patrón **Page Object + Fixture** y reportería con **Allure**:

```gherkin
Scenario: Crear la categoría "Viajes" y clasificar el último movimiento
  Given que inicié sesión como Ana
  And estoy en la sección Movimientos
  When creo la categoría "Viajes" de color "#1E88E5"
  And clasifico mi movimiento más reciente en "Viajes" con la nota "Pasaje a Cusco"
  Then la fila del movimiento muestra la categoría "Viajes" y la nota "Pasaje a Cusco"
  And la categoría "Viajes" cuenta 1 movimientos
```

Cubre HU-G3-03 (crear categoría) y HU-G3-07 (clasificar movimiento). Flujo de una ejecución: **escenario → paso → Page Object → WebdriverIO → navegador**.

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
2. Muestra el escenario de IA (`browser.act()`) escrito en lenguaje natural; sin clave queda *skipped*.
3. Muestra el escenario Gherkin y lo corre con Chrome visible.
4. Cambia el escenario a "cuenta 2 movimientos" para mostrar que la prueba falla y deja una captura en `evidencia/`.
5. Genera el reporte Allure y lo abre en el navegador.
6. Restaura el escenario, también si se interrumpe con Ctrl+C.

## 3. Ejecución manual

**Terminal 1: levantar Qolqe** (déjela abierta)

```bash
.venv\Scripts\python -m uvicorn qolqe.main:app --port 8000     # Windows
.venv/bin/python -m uvicorn qolqe.main:app --port 8000          # Linux / macOS
```

Qolqe queda en http://localhost:8000; la API está documentada en http://localhost:8000/docs.

**Terminal 2: correr los escenarios y ver el reporte**

```bash
npm test             # corre features/clasificar.feature
npm run reporte      # genera reportes/allure/index.html
```

Para ver el navegador, active `HEADED` antes de `npm test`:

| Terminal | Comando |
|---|---|
| PowerShell | `$env:HEADED=1; npm test` |
| CMD | `set HEADED=1 && npm test` |
| Linux / macOS | `HEADED=1 npm test` |

Resultado esperado:

```
Crear la categoría "Viajes" y clasificar el último movimiento
   ✓ Given que inicié sesión como Ana
   ✓ And estoy en la sección Movimientos
   ✓ When creo la categoría "Viajes" de color "#1E88E5"
   ✓ And clasifico mi movimiento más reciente en "Viajes" con la nota "Pasaje a Cusco"
   ✓ Then la fila del movimiento muestra la categoría "Viajes" y la nota "Pasaje a Cusco"
   ✓ And la categoría "Viajes" cuenta 1 movimientos
6 passing (5.1s)
```

Antes de cada escenario se reinician los datos de Qolqe (`POST /api/pruebas/reiniciar`), así que se puede ejecutar las veces que se quiera. Si una prueba falla, la captura queda en `evidencia/`.

| Variable | Uso |
|---|---|
| `HEADED` | Cualquier valor: ejecuta con ventana |
| `QOLQE_URL` | URL de Qolqe (por defecto `http://localhost:8000`) |
| `CHROME_BIN` | Ruta del navegador, si no es el Chrome por defecto |

## 4. Reportería

| Reporte | Dónde | Qué muestra |
|---|---|---|
| Consola (`spec`) | la terminal | cada paso Given/When/Then con ✓ o ✖ |
| **Allure** | `npm run reporte` → `reportes/allure/index.html` (un solo archivo, se abre con doble clic) | escenarios agrupados por épica e historia (`@epic=`, `@story=`), severidad, pasos con su duración y la **captura adjunta** del paso que falló |
| Evidencia | `evidencia/*.png` | captura del navegador cuando un paso falla |
| CI | pestaña *Actions* de GitHub | corre en Windows y Linux y publica el reporte Allure como artefacto descargable |

Las etiquetas del `.feature` alimentan el reporte: `@HU-G3-03` filtra en Cucumber y `@story=HU-G3-03` agrupa en Allure. El reporte acumula el historial de corridas en `reportes/allure-historial.jsonl`.

## 5. Capacidad de IA: `browser.act()`

`features/clasificar-ia.feature` repite el mismo flujo, pero sus pasos (`steps/ia.steps.js`) usan `browser.act()` de `@wdio/ai-service`: la acción se escribe como intención en lenguaje natural. La primera ejecución usa un modelo para manejar el navegador y graba los comandos en `features/__act__/`; las siguientes los repiten sin modelo y sin tokens. `act` solo ejecuta: los pasos `Then` siguen verificando con `expect` en código.

Necesita una clave de API, que este repositorio **no incluye**. Sin clave ni caché, el escenario `@ia` se marca como *skipped*:

```bash
export ANTHROPIC_API_KEY=...       # PowerShell: $env:ANTHROPIC_API_KEY="..."
npm run test:ia                    # 1ª vez: graba · siguientes: repite desde la caché
npm run test:ia:regrabar           # vuelve a grabar
```

## Estructura

```
qolqe/                        Qolqe Wallet (SUT, copia sin modificar del Proyecto 2)
docs/requisitos.md            historias de usuario y reglas (G3 en la sección 6)
features/                     ¿QUÉ se prueba? escenarios en Gherkin
  clasificar.feature          happy path G3
  clasificar-ia.feature       mismo flujo con pasos de IA (@ia)
steps/                        traduce cada paso Given / When / Then a código
  clasificar.steps.js         llama a los Page Objects y verifica con expect
  ia.steps.js                 pasos con browser.act()
pages/                        ¿CÓMO se usa la pantalla? Page Objects
  login.page.js               ingresarComo(celular, pin)
  historial.page.js           abrir, crearCategoria, abrirPrimerMovimiento, clasificar
wdio.conf.js                  navegador, Cucumber, Allure, IA y fixture
allurerc.mjs                  configuración del reporte Allure 3
demo.mjs                      guion de la demo en vivo (npm run demo)
```

## Fuentes

- ISTQB (2024). *Certified Tester Foundation Level Syllabus* v4.0.1.
- W3C (2018). *WebDriver*. https://www.w3.org/TR/webdriver1/ · W3C (2025). *WebDriver BiDi*. https://www.w3.org/TR/webdriver-bidi/
- WebdriverIO: [Automation Protocols](https://webdriver.io/docs/automationProtocols) · [Auto-waiting](https://webdriver.io/docs/autowait) · [AI Steps in Tests](https://webdriver.io/docs/ai-steps) · [v10 release](https://webdriver.io/blog/2026/10/05/webdriverio-v10-release)
- Fowler, M. (2013). *PageObject* · selenium.dev, *Page object models*.
- WebdriverIO: [Cucumber Framework](https://webdriver.io/docs/frameworks#using-cucumber) · [Allure Reporter](https://webdriver.io/docs/allure-reporter) · Allure Report 3: https://allurereport.org
