// Pasos de @ia: browser.act() (WebdriverIO 10) ejecuta la intención; nunca verifica.
// Los Then son los mismos de clasificar.steps.js.
import { existsSync } from 'node:fs'
import { Before, Given, When } from '@wdio/cucumber-framework'
import HistorialPage from '../pages/historial.page.js'
import { USUARIOS } from './clasificar.steps.js'

const cache = 'features/__act__/clasificar-ia.feature.json'

Before({ tags: '@ia' }, () => {
    if (!process.env.ANTHROPIC_API_KEY && !existsSync(cache)) return 'skipped'
})

Given('la IA inicia sesión como {word} y abre Movimientos', async (nombre) => {
    await browser.url('/login')
    // Los valores sensibles van como placeholders: no se envían al modelo.
    await browser.act('Inicia sesión con el celular {{celular}} y el PIN {{pin}}', { values: USUARIOS[nombre] })
    await browser.act('Ve a la sección Movimientos')
})

When('la IA crea la categoría {string} de color azul', async (nombre) => {
    await browser.act(`Crea una categoría llamada "${nombre}" con el color azul #1E88E5`)
})

When('la IA clasifica el movimiento más reciente en {string} con la nota {string}', async function (categoria, nota) {
    this.codigo = await HistorialPage.filas[0].getAttribute('data-codigo')
    await browser.act(`Abre el movimiento más reciente y clasifícalo en "${categoria}" con la nota "${nota}"`)
})
