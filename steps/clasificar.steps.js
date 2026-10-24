// Traduce cada paso de Gherkin a acciones de los Page Objects. Los pasos no tocan el HTML.
import { Given, When, Then } from '@wdio/cucumber-framework'
import LoginPage from '../pages/login.page.js'
import HistorialPage from '../pages/historial.page.js'

// Usuarios semilla de Qolqe (README del SUT, sección 4).
export const USUARIOS = { Ana: { celular: '987654321', pin: '4826' } }

Given('que inicié sesión como {word}', async (nombre) => {
    const { celular, pin } = USUARIOS[nombre]
    await LoginPage.ingresarComo(celular, pin)
})

Given('estoy en la sección Movimientos', async () => {
    await HistorialPage.abrir()
})

When('creo la categoría {string} de color {string}', async (nombre, color) => {
    await HistorialPage.crearCategoria(nombre, color)
})

// `this` es el World de Cucumber: comparte el código del movimiento con los pasos Then.
When('clasifico mi movimiento más reciente en {string} con la nota {string}', async function (categoria, nota) {
    this.codigo = await HistorialPage.abrirPrimerMovimiento()
    await HistorialPage.clasificar(categoria, nota)
})

// "Clasificación guardada" se oculta al repintar el detalle: se verifica el estado guardado.
Then('la fila del movimiento muestra la categoría {string} y la nota {string}', async function (categoria, nota) {
    await browser.refresh()
    await expect(HistorialPage.fila(this.codigo)).toHaveText(expect.stringContaining(categoria))
    await expect(HistorialPage.fila(this.codigo)).toHaveText(expect.stringContaining(nota))
})

// Tras recargar, como el paso anterior: en la CI de Windows la UI a veces no repintaba.
Then('la categoría {string} cuenta {int} movimientos', async (nombre, cantidad) => {
    await expect(HistorialPage.categoria(nombre)).toHaveText(expect.stringContaining(`${cantidad} movimientos`))
})
