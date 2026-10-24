import { existsSync } from 'node:fs'
import HistorialPage from '../pageobjects/historial.page.js'

// Mismo happy path, pero los pasos se escriben como intención (browser.act, WebdriverIO v10).
// La primera vez llama al modelo y graba los comandos en __act__/; después se repiten sin IA.
// Las verificaciones siguen siendo código: act ejecuta, nunca asierta.
const cache = new URL('./__act__/clasificar-ia.e2e.js.json', import.meta.url)

describe('G3 · Historial y categorías (IA)', () => {
    before(function () {
        if (!process.env.ANTHROPIC_API_KEY && !existsSync(cache)) this.skip()
    })

    it('Ana crea la categoría "Viajes" y clasifica su último movimiento', async () => {
        await browser.url('/login')
        await browser.act('Inicia sesión con el celular {{celular}} y el PIN {{pin}}', {
            values: { celular: '987654321', pin: '4826' },
        })
        await browser.act('Ve a la sección Movimientos')
        await browser.act('Crea una categoría llamada "Viajes" con el color azul #1E88E5')

        const codigo = await HistorialPage.filas[0].getAttribute('data-codigo')
        await browser.act('Abre el movimiento más reciente y clasifícalo en "Viajes" con la nota "Pasaje a Cusco"')

        await expect(HistorialPage.mensajeClasificar).toHaveText('Clasificación guardada')
        await expect(HistorialPage.fila(codigo)).toHaveText(expect.stringContaining('Viajes'))
        await expect(await HistorialPage.categoria('Viajes')).toHaveText(expect.stringContaining('1 movimientos'))
    })
})
