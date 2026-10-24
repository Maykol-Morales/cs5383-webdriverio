# language: en
@g3 @ia @epic=G3-Historial-y-categorias
Feature: Clasificar mis movimientos con pasos de IA (browser.act)
  El mismo happy path, pero las acciones se escriben como intención.
  La 1ª corrida usa el modelo y graba los comandos en features/__act__/;
  las siguientes los repiten sin modelo. Las verificaciones siguen siendo código.
  Sin ANTHROPIC_API_KEY ni caché, el escenario se omite.

  @HU-G3-03 @HU-G3-07 @story=HU-G3-03 @story=HU-G3-07 @severity=critical
  Scenario: La IA crea "Viajes" y clasifica el último movimiento
    Given la IA inicia sesión como Ana y abre Movimientos
    When la IA crea la categoría "Viajes" de color azul
    And la IA clasifica el movimiento más reciente en "Viajes" con la nota "Pasaje a Cusco"
    Then la fila del movimiento muestra la categoría "Viajes" y la nota "Pasaje a Cusco"
    And la categoría "Viajes" cuenta 1 movimientos
