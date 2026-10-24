class LoginPage {
    get celular() { return $('aria/Celular') }
    get pin() { return $('aria/PIN') }
    get ingresar() { return $('aria/Ingresar') }

    async ingresarComo(celular, pin) {
        await browser.url('/login')
        await this.celular.setValue(celular)
        await this.pin.setValue(pin)
        await this.ingresar.click()
        await expect(browser).toHaveUrl(expect.stringContaining('/inicio'))
    }
}

export default new LoginPage()
