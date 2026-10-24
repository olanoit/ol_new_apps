---
modulos: [al_construction_planner, al_construction_planner_sale, al_construction_planner_purchase]
---

# Receta, rótulos, presupuesto y moneda

## Forma de cálculo de la receta

Cada línea de la receta (y del plan) tiene su **Forma de cálculo**:

- **Cantidad por unidad**: la cantidad escrita, como siempre.
- **Cuadrilla ÷ rendimiento**: personas × horas de la jornada (si la unidad es la
  hora) ÷ rendimiento.
- **% de la mano de obra**: el porcentaje del costo de la mano de obra de la
  partida (las herramientas manuales «%MO» del análisis de precio unitario).
- **% del costo directo de un grupo de partidas**: de las partidas del mismo
  nivel superior, del mismo nivel 1, de un **Nivel elegido** (la especialidad o
  sub-especialidad del campo **Nivel del porcentaje**) o de toda la obra.

Las líneas por porcentaje se recalculan al cambiar su base y no se piden ni se
compran.

Una línea marcada **Suministro del cliente** (por ejemplo, un equipo que entrega
el cliente) va a costo 0 sin bloquear la aprobación del plan, no entra a la
compra masiva ni a los requerimientos y su ejecutado es lo **Recibido del
cliente** en obra.

El **Costo unitario** de la línea de la receta y del plan guarda los decimales de
**Precio del producto** (Inventario ‣ Configuración ‣ Precisión decimal): un
ladrillo a 0.9661 no pasa a 0.97. El costo por unidad de la receta y el monto de
cada línea del plan se redondean una sola vez, a la moneda. En **Importar recetas y niveles**, las columnas **Forma de cálculo**,
**Porcentaje** y **Moneda**; la unidad «%MO» se lee como porcentaje de la mano de
obra.

En la hoja RECETAS, el **Código del recurso** de una línea de contrata o de
personal propio puede ser el de la actividad o el de su producto: la línea queda
con los dos. Un producto de servicio sin actividad crea su actividad (con la
etapa de la fila). Personal propio en cualquier unidad (horas, glb) se importa y
genera. Si una línea de contrata o de personal propio queda sin actividad,
**Generar desde la receta** dice cuál («R01, línea 3 (Operario)») y no genera
hasta completarla.

## Fuente del análisis de precio unitario

En la obra (**Ajustes** del proyecto), la **Fuente del análisis de precio
unitario**: Work Items de la venta (el cambio en la cotización llega al plan con
una nueva versión) o libro Excel.

## Rótulos de los niveles

Los campos, filtros y agrupaciones de nivel toman los nombres de la plantilla de
niveles de la obra (por ejemplo Especialidad, Sub-especialidad y Partida).

## Importar el presupuesto

En la cotización, **Importar presupuesto** lee un Excel (Ítem, Descripción,
Unidad, Metrado, Precio unitario, Parcial): el nivel 1 entra como sección, el
nivel 2 como subsección y cada partida como línea; avisa de ítems y títulos
repetidos y de partidas sin número antes de crear. Las unidades se leen con
**Configuración ‣ Equivalencias de unidades**. **Crear niveles de la obra** pasa
las secciones, subsecciones y partidas a los niveles del plan con su metrado.

## Partidas en otra moneda

Una línea de la receta o del plan puede tener su costo en dólares: el costo
planificado es su conversión al tipo de cambio de la fecha del plan. La compra
masiva crea el requerimiento y la orden en dólares, y el control se lleva en la
moneda de la obra con el tipo de cambio de cada orden; la **diferencia de
cambio** se muestra aparte del **desvío de precio**.
