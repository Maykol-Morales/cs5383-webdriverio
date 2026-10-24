# language: en
@g3 @e2e @epic=G3-Historial-y-categorias
Feature: Clasificar mis movimientos en categorías propias
  Como cliente de Qolqe
  Quiero crear categorías y asignarlas a mis movimientos
  Para organizar mis gastos

  # Datos: Ana tiene 3 categorías (Comida, Familia y Servicios).
  # Qolqe se reinicia antes de cada escenario (fixture en wdio.conf.js).

  Background:
    Given que inicié sesión como Ana
    And estoy en la sección Movimientos

  @HU-G3-03 @HU-G3-07 @story=HU-G3-03 @story=HU-G3-07 @severity=critical
  Scenario: Clasificar el último movimiento en una categoría nueva
    When creo la categoría "Viajes" de color "#1E88E5"
    And clasifico mi movimiento más reciente en "Viajes" con la nota "Pasaje a Cusco"
    Then la fila del movimiento muestra la categoría "Viajes" y la nota "Pasaje a Cusco"
    And la categoría "Viajes" cuenta 1 movimientos
