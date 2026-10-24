// Allure 3 (sin Java). npm run reporte: reportes/allure-results → reportes/allure/index.html
// historyPath acumula una línea por corrida: da las tendencias entre corridas.
const nombre = 'Qolqe Wallet · G3 E2E con WebdriverIO'

export default {
    name: nombre,
    output: 'reportes/allure',
    historyPath: 'reportes/allure-historial.jsonl',
    plugins: {
        awesome: { options: { reportName: nombre, reportLanguage: 'es', singleFile: true, groupBy: ['epic', 'story'] } },
    },
}
