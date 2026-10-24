import LoginPage from '../pageobjects/login.page.js'
import HistorialPage from '../pageobjects/historial.page.js'

// HU-G3-03 + HU-G3-07 · happy path: crear una categoría y clasificar un movimiento con ella.
describe('G3 · Historial y categorías', () => {
    it('Ana crea la categoría "Viajes" y clasifica su último movimiento', async () => {
        await LoginPage.ingresarComo('987654321', '4826')
        await HistorialPage.abrir()

        await HistorialPage.crearCategoria('Viajes', '#1E88E5')
        await expect($('[data-testid=toast]')).toHaveText('Categoría "Viajes" creada')

        const codigo = await HistorialPage.abrirPrimerMovimiento()
        await HistorialPage.clasificar('Viajes', 'Pasaje a Cusco')

        await expect(HistorialPage.mensajeClasificar).toHaveText('Clasificación guardada')
        await expect(HistorialPage.fila(codigo)).toHaveText(expect.stringContaining('Viajes'))
        await expect(HistorialPage.fila(codigo)).toHaveText(expect.stringContaining('Pasaje a Cusco'))
        await expect(await HistorialPage.categoria('Viajes')).toHaveText(expect.stringContaining('1 movimientos'))
    })
})
