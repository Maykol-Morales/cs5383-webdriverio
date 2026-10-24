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
        // Qolqe muestra el aviso antes de recargar los selects; la lista se pinta al final.
        await expect($('[data-testid=lista-categorias]')).toHaveText(expect.stringContaining(nombre))
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
