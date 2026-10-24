// Guion de la demo en vivo (Windows, Linux y macOS). Uso: npm run demo
// Cada paso espera Enter. Levanta Qolqe si no está corriendo y lo apaga al final.
import { spawn, spawnSync } from 'node:child_process'
import { existsSync, readFileSync, writeFileSync, readdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createInterface } from 'node:readline/promises'

const URL = 'http://localhost:8000'
const SPEC = 'test/specs/clasificar.e2e.js'
const original = readFileSync(SPEC, 'utf8')
const rl = createInterface({ input: process.stdin, output: process.stdout })

// Si la entrada se cierra (stdin redirigido o CI), la demo sigue sin esperar.
const paso = (titulo) => rl.question(`\n\x1b[1;31m▸ ${titulo}\x1b[0m\n  [Enter] `).catch(() => {})
// Un solo string con shell: npx es npx.cmd en Windows.
const wdio = (spec, env = {}) => spawnSync(`npx wdio run wdio.conf.js --spec ${spec}`,
    { stdio: 'inherit', shell: true, env: { ...process.env, ...env } })
const qolqeVivo = () => fetch(`${URL}/api/salud`).then((r) => r.ok, () => false)

let qolqe
function terminar() {
    writeFileSync(SPEC, original) // deja la spec como estaba, aun con Ctrl+C
    qolqe?.kill()
    rl.close()
}
process.on('SIGINT', () => { terminar(); process.exit(130) })

// 0. SUT: reusar Qolqe si ya corre; si no, levantarlo con una BD aparte.
if (!await qolqeVivo()) {
    const python = ['.venv/Scripts/python.exe', '.venv/bin/python'].find(existsSync) ?? 'python'
    console.log('Levantando Qolqe en :8000...')
    qolqe = spawn(python, ['-m', 'uvicorn', 'qolqe.main:app', '--port', '8000'],
        { env: { ...process.env, QOLQE_BD: join(tmpdir(), 'qolqe-demo.db') }, stdio: 'ignore' })
    for (let i = 0; i < 60 && !await qolqeVivo(); i++) await new Promise((r) => setTimeout(r, 500))
    if (!await qolqeVivo()) { console.error('Qolqe no arrancó. ¿Instalaste requirements.txt?'); terminar(); process.exit(1) }
}
console.log('Qolqe OK en', URL)

await paso('IA: browser.act() escribe los pasos en lenguaje natural')
console.log(readFileSync('test/specs/clasificar-ia.e2e.js', 'utf8').split('\n').slice(14, 30).join('\n'))
if (process.env.ANTHROPIC_API_KEY) {
    await paso('IA en vivo: el modelo maneja Chrome y graba los pasos en __act__/')
    wdio('test/specs/clasificar-ia.e2e.js', { HEADED: '1' })
} else {
    console.log('\n  Sin ANTHROPIC_API_KEY: la spec de IA se marca como skipped.')
    console.log('  Con la clave: la 1ª corrida graba los pasos con el modelo y las siguientes')
    console.log('  los repiten desde test/specs/__act__/ sin modelo y sin tokens.')
}

await paso('Demo del flujo: Page Object + Fixture, con ventana')
wdio(SPEC, { HEADED: '1' })

await paso("¿Detecta fallos? Cambiamos el oráculo a '2 movimientos'")
writeFileSync(SPEC, original.replace('1 movimientos', '2 movimientos'))
wdio(SPEC)

await paso('Evidencia de la falla')
console.log(existsSync('evidencia') ? readdirSync('evidencia').map((f) => `  evidencia/${f}`).join('\n') : '  (sin capturas)')
terminar()
console.log('Spec restaurada. Fin de la demo.')
