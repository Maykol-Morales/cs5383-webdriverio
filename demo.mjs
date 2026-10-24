// Guion de la demo en vivo (Windows, Linux y macOS). Uso: npm run demo
// Cada paso espera Enter. Levanta Qolqe si no está corriendo y lo apaga al final.
// Termina generando y abriendo el reporte Allure de las corridas de la demo.
import { spawn, spawnSync } from 'node:child_process'
import { existsSync, readFileSync, writeFileSync, readdirSync, rmSync, mkdirSync, openSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createInterface } from 'node:readline/promises'

const URL = 'http://localhost:8000'
const SPEC = 'features/clasificar.feature'
const SPEC_IA = 'features/clasificar-ia.feature'
const original = readFileSync(SPEC, 'utf8')
const rl = createInterface({ input: process.stdin, output: process.stdout })

// Si la entrada se cierra (stdin redirigido o CI), la demo sigue sin esperar.
const paso = (titulo) => rl.question(`\n\x1b[1;31m▸ ${titulo}\x1b[0m\n  [Enter] `).catch(() => {})
// Un solo string con shell: npx es npx.cmd en Windows.
const wdio = (spec, env = {}) => spawnSync(`npx wdio run wdio.conf.js --spec ${spec}`,
    { stdio: 'inherit', shell: true, env: { ...process.env, ...env } })
const npx = (comando) => spawnSync(`npx ${comando}`, { stdio: 'inherit', shell: true })
const abrir = { win32: 'start ""', darwin: 'open' }[process.platform] ?? 'xdg-open'
const qolqeVivo = () => fetch(`${URL}/api/salud`).then((r) => r.ok, () => false)

let qolqe
function terminar() {
    writeFileSync(SPEC, original) // deja el escenario como estaba, aun con Ctrl+C
    qolqe?.kill()
    rl.close()
}
process.on('SIGINT', () => { terminar(); process.exit(130) })

// 0. SUT: reusar Qolqe si ya corre; si no, levantarlo con una BD aparte.
if (!await qolqeVivo()) {
    const python = ['.venv/Scripts/python.exe', '.venv/bin/python'].find(existsSync) ?? 'python'
    console.log('Levantando Qolqe en :8000...')
    mkdirSync('reportes', { recursive: true })
    const log = openSync('reportes/qolqe.log', 'w') // peticiones al servidor, para diagnosticar fallas
    qolqe = spawn(python, ['-m', 'uvicorn', 'qolqe.main:app', '--port', '8000'],
        { env: { ...process.env, QOLQE_BD: join(tmpdir(), 'qolqe-demo.db') }, stdio: ['ignore', log, log] })
    for (let i = 0; i < 60 && !await qolqeVivo(); i++) await new Promise((r) => setTimeout(r, 500))
    if (!await qolqeVivo()) { console.error('Qolqe no arrancó. ¿Instalaste requirements.txt?'); terminar(); process.exit(1) }
}
console.log('Qolqe OK en', URL)
rmSync('reportes/allure-results', { recursive: true, force: true }) // el reporte muestra solo esta demo
rmSync('evidencia', { recursive: true, force: true })

await paso('IA: browser.act() escribe los pasos en lenguaje natural')
console.log(readFileSync(SPEC_IA, 'utf8').split('\n').slice(8).join('\n'))
console.log(readFileSync('steps/ia.steps.js', 'utf8').split('\n').slice(13, 19).join('\n'))
if (process.env.ANTHROPIC_API_KEY) {
    await paso('IA en vivo: el modelo maneja Chrome y graba los pasos en features/__act__/')
    wdio(SPEC_IA, { HEADED: '1' })
} else {
    console.log('\n  Sin ANTHROPIC_API_KEY: el escenario @ia se marca como skipped.')
    console.log('  Con la clave: la 1ª corrida graba los pasos con el modelo y las siguientes')
    console.log('  los repiten desde features/__act__/ sin modelo y sin tokens.')
    wdio(SPEC_IA) // queda como "skipped" en el reporte
}

await paso('BDD: el escenario en Gherkin es la especificación')
console.log(readFileSync(SPEC, 'utf8'))

await paso('Demo del flujo: escenario → pasos → Page Objects → Chrome')
const flujo = wdio(SPEC, { HEADED: '1' })

await paso("¿Detecta fallos? Cambiamos el escenario a 'cuenta 2 movimientos'")
writeFileSync(SPEC, original.replace('cuenta 1 movimientos', 'cuenta 2 movimientos'))
wdio(SPEC)
writeFileSync(SPEC, original)
console.log(existsSync('evidencia') ? readdirSync('evidencia').map((f) => `  evidencia/${f}`).join('\n') : '  (sin capturas)')

await paso('Reporte Allure: escenarios, pasos, historias y la captura de la falla')
npx('allure generate --clean reportes/allure-results')
const reporte = join(process.cwd(), 'reportes', 'allure', 'index.html')
if (!process.env.CI) spawnSync(`${abrir} "${reporte}"`, { shell: true })
console.log(`  ${reporte}`)

terminar()
console.log('Escenario restaurado. Fin de la demo.')
process.exitCode = flujo.status // la demo falla si el flujo (no la mutación) falló
