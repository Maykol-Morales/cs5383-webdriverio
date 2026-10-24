import { mkdirSync } from 'node:fs'

export const baseUrl = process.env.QOLQE_URL ?? 'http://localhost:8000'

export const config = {
    runner: 'local',
    specs: ['./features/**/*.feature'],
    maxInstances: 1,
    capabilities: [{
        browserName: 'chrome',
        webSocketUrl: true, // WebDriver BiDi, lo usa @wdio/ai-service
        'goog:chromeOptions': {
            binary: process.env.CHROME_BIN,
            args: process.env.HEADED ? [] : ['--headless=new', '--window-size=1280,900'],
        },
    }],
    baseUrl,
    waitforTimeout: 5000,

    // BDD: escenarios Gherkin en features/, pasos en steps/, Page Objects en pages/.
    framework: 'cucumber',
    cucumberOpts: { require: ['./steps/*.js'], timeout: 60000 },

    // Reportería: consola + Allure (npm run reporte genera reportes/allure/index.html).
    reporters: ['spec', ['allure', {
        outputDir: 'reportes/allure-results',
        useCucumberStepReporter: true,     // los pasos Given/When/Then son los pasos del reporte
        disableWebdriverStepsReporting: true,
    }]],

    // IA: browser.act() pide los pasos al modelo una vez y los repite desde features/__act__/
    services: [['ai', { model: process.env.WDIO_AI_MODEL ?? 'anthropic:claude-sonnet-5' }]],
    logLevel: 'warn',

    // Fixture: cada escenario parte de los datos semilla de Qolqe (ver README del SUT).
    beforeScenario: async () => {
        const res = await fetch(`${baseUrl}/api/pruebas/reiniciar`, { method: 'POST' })
        if (!res.ok) throw new Error(`No se pudo reiniciar Qolqe: HTTP ${res.status}`)
    },
    // Evidencia: captura del paso que falló, en evidencia/ y adjunta en el reporte Allure.
    afterStep: async (step, scenario, { error }) => {
        if (!error) return
        mkdirSync('evidencia', { recursive: true })
        await browser.saveScreenshot(`./evidencia/${scenario.name.replace(/\W+/g, '_')}.png`)
    },
}
