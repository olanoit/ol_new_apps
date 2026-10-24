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

## Herramientas y equipos

- **Herramientas manuales menores**: una línea en % de la mano de obra de la
  partida (unidad «%MO»), que es una bolsa en soles del plan. No se pide; con la
  **Categoría de herramientas manuales** en Ajustes ‣ Abastecimiento, las compras
  de esa categoría con la analítica de la obra son su comprometido (órdenes sin
  facturar) y su real (facturas), repartidos entre las bolsas de la obra.
- **Equipo propio**: en el producto, pestaña **Equipo de obra**, el valor de
  reposición, la vida útil, las horas por año, el interés, seguro y almacén, el
  mantenimiento y el combustible dan la **Tarifa interna por hora**, que es el
  costo del equipo en la receta y en el plan. En la línea del plan, **Uso del
  equipo** registra las horas (o días) de uso; cada uso se carga a la cuenta
  analítica de la obra y es el ejecutado y el real de la línea.
- **Equipo alquilado**: un equipo sin marcar como propio; se contrata con su
  orden de servicio.

## Modalidad de ejecución por partida

La receta trae su **Modalidad por defecto** y, para las contratas, su
**Actividad de la contrata**; cada partida tiene su **Modalidad de ejecución**,
que se cambia antes de aprobar el plan (después, en una nueva versión del plan):

| Modalidad | Lo que genera el plan |
|---|---|
| Personal propio | Una línea por recurso de la receta (materiales, personal propio, herramientas y equipos) |
| Contrata solo de mano de obra | Una línea de contrata con la mano de obra y las herramientas; los materiales y equipos, aparte |
| Contrata a todo costo | Una sola línea de contrata por el costo total de la receta; el detalle del APU queda como referencia y no se piden materiales |

**Importar recetas y niveles** pide la **Modalidad de las recetas** importadas.

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

## Costo real, holguras y precio

Cada línea de la cotización lleva tres capas, con columnas internas que no se
imprimen:

| Campo | Cálculo |
|---|---|
| Metrado real | Dato; es el que pasa al plan |
| Holgura de metrado | % o cantidad; la cantidad de la cotización es el metrado ofertado |
| Costo del APU | Costo por unidad de la receta |
| Holgura de costo | % o monto; da el costo ofertado (el costo del margen de ventas) |
| Margen | % o monto sobre el costo ofertado; da el precio unitario |

La cotización tiene **Tipo de contrato** (suma alzada o precios unitarios) y
**Formato de impresión** (solo precios o desglosado), y muestra el **Costo
directo real** y la **Reserva por holguras** (costo ofertado − costo real), que
también se ve en el plan. Avisa si el contrato es a precios unitarios con
holgura de metrado (no se cobra) y si hay margen por partida y además gastos
generales o utilidad en el pie.

Ejemplo de demostración: tabique de drywall con metrado real 90 y holgura de 20
→ 110 ofertados; costo del APU 58.04 y holgura de 5.00 → 63.04; costo real
5,223.60, costo ofertado 6,934.40 y reserva 1,710.80.

## Libro de APU y presupuesto

En la cotización, **Importar libro de APU y presupuesto** lee un libro con siete
hojas (**Descargar plantilla** da el libro vacío):

| Hoja | Una fila por | Se carga como |
|---|---|---|
| OBRA | Campo y valor | Tipo de contrato, formato y porcentajes del pie |
| INSUMOS | Recurso con código único | Productos (y actividades de mano de obra y contrata) |
| APU | Partida tipo | Receta con rendimiento, horas por jornada y modalidad |
| APU_DETALLE | Recurso del APU | Líneas de la receta: cuadrilla, % de la mano de obra o cantidad |
| PRESUPUESTO | Partida de la obra | Secciones, subsecciones y líneas de la cotización con sus capas |
| LISTAS | Valor válido | Tipos de insumo, modalidades y la tabla de equivalencias de unidades |
| INSTRUCCIONES | — | No se lee |

**Revisar** valida códigos únicos, insumos y APU existentes, unidades con
equivalencia y fórmulas sin error: los errores impiden enviar y los avisos se
aceptan. Con destino **Presupuesto** crea o actualiza insumos, recetas y la
cotización (con las líneas de gastos generales, imprevistos, utilidad y
descuento del pie); con **Presupuesto y plan**, además los niveles de la obra
con su receta, modalidad y metrado real, y genera el plan (con el plan aprobado,
una nueva versión con el **Motivo de la versión**; las partidas con compromisos
o avance no se regeneran y se listan). Con «Costo real» en el libro, si el costo
directo de la cotización no es el mismo (máximo S/ 0.01), el envío se revierte.
Volver a importar actualiza sin duplicar.

## Partidas en otra moneda

Una línea de la receta o del plan puede tener su costo en dólares: el costo
planificado es su conversión al tipo de cambio de la fecha del plan. La compra
masiva crea el requerimiento y la orden en dólares, y el control se lleva en la
moneda de la obra con el tipo de cambio de cada orden; la **diferencia de
cambio** se muestra aparte del **desvío de precio**.
