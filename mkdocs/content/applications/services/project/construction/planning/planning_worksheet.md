---
modulos: [al_construction_planner, al_construction_planner_spreadsheet, al_construction_planner_spreadsheet_furniture, al_construction_planner_furniture]
---

# Pestaña Planificación y hoja de trabajo

## Pestaña Planificación de la obra

La ficha de la obra (**Obras ‣ Obras**) tiene la pestaña **Planificación**
con los accesos al **Árbol de recursos**, al **Cronograma** y a los planes, y
tres márgenes, cada uno con su ingreso, su costo, su margen y su porcentaje:

| Margen | Ingreso | Costo |
|---|---|---|
| Planificado | Contratos de obra con sus cambios aprobados o, sin contratos, la orden de venta de la obra (sin impuestos) | Líneas del plan vigente |
| Devengado | Valorizaciones confirmadas por el cliente o facturadas | Real de las líneas del plan: consumido, recibido en OC de servicio y horas |
| Contable | Apuntes analíticos positivos de la cuenta de la obra | Apuntes analíticos negativos de la cuenta de la obra |

Un margen negativo se muestra en rojo.

## Hoja de trabajo de presupuesto y plan (construcción)

Con **Documentos** y **Hoja de cálculo** (Odoo Enterprise) se instala solo
**Hoja de trabajo del planificador de obra**
(`al_construction_planner_spreadsheet`). En construcción, el presupuestador y la
oficina técnica trabajan el presupuesto, los APU y el plan en una hoja con las
mismas hojas y columnas del [libro de APU y presupuesto](recipe_calc.md#libro-de-apu-y-presupuesto):

- El botón **Hoja de trabajo** de la cotización crea la hoja en **Presupuestos ‣
  <cotización>** de Documentos con lo que ya tiene la cotización; desde la obra
  (pestaña Planificación) se abre la de su cotización o una propia.
- Pestañas: INSTRUCCIONES, OBRA, INSUMOS, APU, APU_DETALLE, PRESUPUESTO, PLAN
  (modalidad final y fechas de cada partida), LISTAS, REFERENCIAS (listas vivas
  de actividades, unidades, contratistas y productos) y ERRORES. Encabezados
  amarillos: datos; grises: fórmulas (cantidad y precio del recurso, parcial,
  costo unitario del APU, costo del APU y costo real de la partida).
- Menú **Planificación de obra** de la hoja:
    - **Validar plantilla**: los errores en ERRORES con su hoja, fila y columna.
    - **Enviar al planificador: presupuesto** o **presupuesto y plan**: abre la
      revisión del asistente del libro; los errores impiden enviar y los avisos
      se aceptan. Con el plan aprobado, pide el motivo de la nueva versión.
    - **Actualizar insumos**: el costo vigente del maestro en INSUMOS.
    - **Traer de Odoo**: los datos de la cotización y de las recetas de la obra.
    - **Nueva versión**: guarda una copia numerada en la misma carpeta, con el
      enlace en el historial de la cotización y del plan. Cada envío guarda
      también su copia.
- **Archivo ‣ Descargar** da el libro en Excel, que se puede volver a importar.

## Hoja de trabajo del maestro (mobiliario)

En las obras de mobiliario la hoja es el maestro de planificación, con el puente
`al_construction_planner_spreadsheet_furniture`, que se instala solo con el
planificador de mobiliario. En mobiliario, la Oficina Técnica
arma en ella todo el presupuesto y la carga de la obra, sin Excel: registra
datos crudos medidos sobre el plano y, aprobado el presupuesto por el cliente,
los envía al planificador.

El botón **Hoja de trabajo** de la pestaña Planificación crea, la primera vez,
la hoja de la obra en Documentos y la abre. Las demás veces abre la misma
hoja. La hoja se trabaja entre varios a la vez y guarda su historial.

!!! note "Nota"
    En una obra del perfil **Construcción por partidas** el botón abre la hoja
    de presupuesto y plan.

### Pestañas

| Pestaña | Qué registra el analista |
|---|---|
| LEEME | Instrucciones paso a paso |
| RESUMEN | Cuatro tablas dinámicas sobre la propia hoja: ambientes por tipología, costo por módulo y sub etapa, despiece por tablero y materiales por tipología, sin el grupo de las filas vacías |
| CATALOGO | Actividades de obra con su driver y su tarifa base |
| OBRA | Datos y condiciones de la obra (inicio, fin, cliente, adelanto %, fondo de garantía %) |
| ARBOL | Piso, departamento, ambiente, tipología y tipo de unidad |
| TIPOLOGIAS, MUEBLES y MODULOS | Código del módulo (el del ETO), nombre, mueble, tipo, ancho, grupo ML, tipo de módulo y método de unión |
| PIEZAS | Despiece de cada módulo: cantidad, largo, ancho, tipo de pieza, color, categoría, producto y cantos |
| BOM | Materiales por módulo: categoría, producto, cantidad, unidad y sub etapa |
| PRODUCTOS NUEVOS | Código provisional, nombre, unidad, categoría y costo estimado |
| ACTIVIDADES, TARIFAS, CONTRATOS, HITOS, VENTA y MO PROPIA | Contratas y su cantidad, tarifas de la obra, contrato con el cliente, hitos de cobro, precio por tipología y mano de obra propia |
| ETO y VARIANTES | Módulos reales de cada ambiente y variantes por unidad |
| REFERENCIAS | Listas vivas de Odoo: actividades, tipologías de la obra, el maestro de productos completo (código, nombre completo, unidad, costo y categoría), las categorías de último nivel y las sub etapas |

Cada pestaña tiene sus encabezados y 300 filas preparadas. Las únicas columnas
calculadas son el código del producto, los m² de la pieza (PIEZAS) y el costo
de la línea con el costo vivo del maestro (BOM); su encabezado va con fondo
verde.

### Elegir los materiales

En PIEZAS y BOM, el material se elige en dos pasos:

1. En **Categoría**, elija la categoría de último nivel del maestro (por
   ejemplo, «1011 TABLEROS»).
2. En **Producto**, elija el producto: la lista muestra solo los de esa
   categoría, con su código y su nombre completo, y se puede escribir para
   buscar. Los productos nuevos del maestro aparecen en la lista de su
   categoría.

La familia, el tipo de módulo, el método de unión, el grupo ML, la familia de
la tarifa y la sub etapa también se eligen de una lista. Las listas fijas rechazan al
escribir un valor que no está en la lista, para que no llegue a **Validar** ni al
envío. En una hoja ya creada, se activa con **Actualizar a la plantilla vigente**.

### Importar un Excel

**Planificación de obra ‣ Importar Excel a la hoja** trae un libro de carga, por
ejemplo el Excel descargado de otra hoja. Antes de escribir, la revisión dice qué
hace con cada pestaña del archivo:

| Acción | Pestañas |
|---|---|
| Importa por clave | Las del maestro y la columna Material de MATERIALES OBRA |
| Ignorada: es de la plantilla | INICIO, LEEME, RESUMEN, REFERENCIAS, FICHA, PROGRAMA, CONTROL, ERRORES, VENDIDO y las que empiezan con `_` |
| Ignorada: es de la hoja de venta | EDIFICIO, ACABADOS, TARIFARIO, PRECIOS, METRADO y RESUMEN VENTA |
| Se copia | Las pestañas propias, como FUENTES, si marca **Conservar columnas y pestañas que no son del maestro** |

La importación escribe solo en las columnas de dato: las fórmulas, las listas y
las marcas quedan como estaban. Al terminar, un mensaje resume las filas escritas
por pestaña, lo copiado, lo ignorado, los errores y los avisos, con un vínculo a
ERRORES.

### Restaurar una versión

Si importó el archivo equivocado, **Planificación de obra ‣ Restaurar versión**
vuelve atrás:

1. Elija la versión. La lista muestra su fecha y la acción que la originó.
2. Revise cuántas filas son nuevas, cambian o quedan iguales en cada pestaña, y
   pulse **Restaurar**.

La hoja sigue vinculada a su obra y guarda antes su estado actual, así que la
restauración también se puede deshacer. Solo se reescriben las columnas de dato;
las pestañas propias, como FUENTES, no cambian.

!!! note
    Las versiones anteriores a esta función no dicen de qué acción salieron.

### Enviar al planificador

En la hoja, **Archivo ‣ Enviar al planificador** lleva los valores de las
pestañas del maestro (no las demás) al asistente [Importar maestro y
ETO](import_master.md) de la obra. El asistente muestra lo que creará o
actualizará, las advertencias y los errores con su hoja y su fila, sin
escribir nada; **Importar** lo aplica. Si la orden de venta de la obra aún no
está confirmada, avisa que el presupuesto no está aprobado por el cliente. Se
puede enviar las veces que haga falta: no duplica.
