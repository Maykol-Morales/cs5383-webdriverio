export const baseUrl = process.env.QOLQE_URL ?? 'http://localhost:8000'

export const config = {
    runner: 'local',
    specs: ['./test/specs/**/*.e2e.js'],
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
    framework: 'mocha',
    mochaOpts: { timeout: 60000 },
    reporters: ['spec'],
    // IA: browser.act() pide los pasos al modelo una vez y los repite desde test/specs/__act__/
    services: [['ai', { model: process.env.WDIO_AI_MODEL ?? 'anthropic:claude-sonnet-5' }]],
    logLevel: 'warn',

    // Fixture: cada prueba parte de los datos semilla de Qolqe (ver README del SUT).
    beforeTest: async () => {
        const res = await fetch(`${baseUrl}/api/pruebas/reiniciar`, { method: 'POST' })
        if (!res.ok) throw new Error(`No se pudo reiniciar Qolqe: HTTP ${res.status}`)
    },
    afterTest: async (test, context, { passed }) => {
        if (!passed) await browser.saveScreenshot(`./evidencia/${test.title.replace(/\W+/g, '_')}.png`)
    },
}
