#!/usr/bin/env bash
# Guion de la demo en vivo. Cada paso espera Enter.
# Uso: ./demo.sh
set -u
cd "$(dirname "$0")"

# Sin CHROME_BIN, WebdriverIO descarga Chrome for Testing la primera vez.
[ -z "${CHROME_BIN:-}" ] && command -v chromium >/dev/null && export CHROME_BIN=$(command -v chromium)
UVICORN=uvicorn; [ -x .venv/bin/uvicorn ] && UVICORN=.venv/bin/uvicorn
SPEC=test/specs/clasificar.e2e.js

paso() { printf '\n\033[1;31m▸ %s\033[0m\n' "$1"; read -rp "  [Enter] "; }
correr() { printf '\033[2m$ %s\033[0m\n' "$*"; "$@"; }

# Si se interrumpe a mitad de la mutación, deja la spec como estaba.
trap 'sed -i "s/2 movimientos/1 movimientos/" $SPEC' EXIT

# 0. SUT: reusar Qolqe si ya corre; si no, levantarlo con una BD aparte.
if ! curl -sf localhost:8000/api/salud >/dev/null; then
    echo "Levantando Qolqe en :8000 (BD en /tmp/qolqe-demo.db)..."
    QOLQE_BD=/tmp/qolqe-demo.db $UVICORN qolqe.main:app --port 8000 >/tmp/qolqe-demo.log 2>&1 &
    until curl -sf localhost:8000/api/salud >/dev/null; do sleep 0.5; done
fi
echo "Qolqe OK: $(curl -s localhost:8000/api/salud)"

paso "IA: browser.act() escribe los pasos en lenguaje natural"
correr sed -n '15,30p' test/specs/clasificar-ia.e2e.js
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    paso "IA en vivo: el modelo maneja Chrome y graba los pasos en __act__/"
    HEADED=1 correr npm run --silent test:ia
else
    echo
    echo "  Sin ANTHROPIC_API_KEY: la spec de IA se marca como skipped."
    echo "  Con la clave: 1ª corrida graba los pasos con el modelo, las siguientes"
    echo "  los repiten desde test/specs/__act__/ sin modelo y sin tokens."
fi

paso "Demo del flujo: Page Object + Fixture, con ventana"
HEADED=1 correr npm run --silent test

paso "¿Detecta fallos? Cambiamos el oráculo a '2 movimientos'"
correr sed -i 's/1 movimientos/2 movimientos/' "$SPEC"
correr npm run --silent test

paso "Evidencia de la falla"
correr ls -l evidencia/
correr sed -i 's/2 movimientos/1 movimientos/' "$SPEC"
echo "Spec restaurada. Fin de la demo."
