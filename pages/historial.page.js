// Pantalla /historial (G3): movimientos, detalle, clasificación y categorías.
class HistorialPage {
    get filas() { return $$('[data-testid=fila-movimiento]') }

    fila(codigo) { return $(`[data-testid=fila-movimiento][data-codigo="${codigo}"]`) }
    // Selector, no elemento: expect lo vuelve a buscar en cada reintento aunque Qolqe repinte la lista.
    categoria(nombre) { return $(`//li[@data-testid="categoria"][contains(., "${nombre}")]`) }

    async abrir() {
        await $('aria/Movimientos').click()
        await expect(browser).toHaveUrl(expect.stringContaining('/historial'))
        await expect(this.filas).toBeElementsArrayOfSize({ gte: 1 })
    }

    async crearCategoria(nombre, color) {
        await $('aria/Nombre').setValue(nombre)
        await $(`aria/${color}`).parentElement().click()
        await $('aria/Crear categoría').click()
        // Qolqe responde con un aviso (éxito) o una alerta (error); el paso distingue ambos.
        const error = $('[data-testid=categoria-error]')
        const aviso = $('[data-testid=toast]')
        await browser.waitUntil(async () => await error.isDisplayed() || (await aviso.isDisplayed() && (await aviso.getText()).includes(nombre)),
            { timeoutMsg: `Qolqe no respondió al crear "${nombre}" (ni aviso ni error)` })
        if (await error.isDisplayed()) throw new Error(`Qolqe rechazó la categoría: ${await error.getText()}`)
        // La lista se pinta después del aviso; también los selects que usa clasificar().
        await expect($('[data-testid=lista-categorias]')).toHaveText(expect.stringContaining(nombre),
            { message: `Qolqe confirmó "${nombre}" pero la lista no se actualizó` })
    }

    // Abre el movimiento más reciente y devuelve su código de operación.
    async abrirPrimerMovimiento() {
        const fila = this.filas[0]
        const codigo = await fila.getAttribute('data-codigo')
        await fila.click()
        await expect($('[data-testid=detalle-codigo]')).toHaveText(codigo)
        return codigo
    }

    async clasificar(categoria, nota) {
        await $('[data-testid=select-clasificar-categoria]').selectByVisibleText(categoria)
        await $('[data-testid=input-nota]').setValue(nota)
        await $('aria/Guardar clasificación').click()
    }
}

export default new HistorialPage()
