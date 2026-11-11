# Diseño del paquete 1.17 · hojas de venta y de planificación, y requerimiento de obra

Fuente: «Requerimiento · paquete 1.17» (03-nov-2026, revisado el 04-nov), 25
requerimientos (M117-01 a M117-25). Este documento recoge cómo se desarrolla, lo
que se devuelve antes de programar y la estimación. Los nombres de obra, montos
y usuarios de las pruebas no se copian aquí: el repositorio es público.

Manda sobre este documento `ARQUITECTURA_COMUN.md`, en lo común.

## 1. Entregas

Se desarrolla por entregas. Cada una se prueba y se acepta antes de la siguiente.

| Entrega | Requerimientos | Qué resuelve | Estimación |
|---|---|---|---|
| 1 | M117-03, 04, 06, 10 | Lo que rompe la hoja o el plan | 2 a 3 días |
| 2 | M117-01, 02, 05, 07, 09, con la guía visual de M117-23 aplicada a la hoja de planificación | La usabilidad de la hoja de planificación | 6 a 8 días |
| 3 | M117-15, M117-16 a 22, con M117-23 en la hoja de venta | Parámetros, hoja de venta y paso a la planificación | 15 a 20 días |
| 4 | M117-08, 24, 25, 11, 12, 13, 14 | Avance visible, catálogo de tipos con migración, factura y ajustes del requerimiento | 8 a 10 días |

Total: 31 a 41 días de desarrollo, sin contar la espera de cada aceptación. Son
órdenes de magnitud: la entrega 3 es la menos segura, porque es la primera hoja
de Odoo que nace sin obra.

Lo que debe llegar de Oficina Técnica antes de cargar la entrega 3 en una base
real (puntos 11 a 16 de «Configuración y datos» del requerimiento): tarifario y
recargos, clientes con convenio, factor de venta y textos de la cotización. El
código no depende de esos valores.

## 2. Lo que se devuelve antes de programar

Son los puntos que el requerimiento pide proponer, o que el código contradice.
Ninguno detiene la entrega 1.

| # | Punto | Propuesta | Se necesita para |
|---|---|---|---|
| D1 | M117-21, punto 9: el factor de descuento del contrato guarda 4 decimales y no cuadra con la orden de venta | Guardar el factor con 6 decimales y llevar el resto a la última valorización, para que orden, contrato y resumen den el mismo total | Entrega 3 |
| D2 | M117-22, punto 4: una partida con dos líneas en la orden (la original y la del adicional) | Falta revisar cómo valoriza el planificador esa partida; se propone al empezar M117-22, con la lectura del código | Entrega 3 |
| D3 | M117-08: la meta de tiempo | Medir primero con la obra más grande; la meta propuesta en el requerimiento es menos de 60 s | Entrega 4 |
| D4 | M117-23: las hojas modelo de dev1 son la referencia, pero no se pueden leer sin conexión ni copiar al repositorio | Programar contra las fichas del Anexo A, que mandan sobre las hojas modelo; revisar contra estas en dev1 con permiso de solo lectura | Entrega 2 |

## 3. Entrega 1

### M117-03 · Importación que respeta la plantilla

- El asistente clasifica cada pestaña del archivo: `Importa por clave`, `Ignorada:
  es de la plantilla`, `Ignorada: es de la hoja de venta`, `Se copia`. Ignora
  `TEMPLATE_ONLY_SHEETS`, `VENDIDO` y lo que empieza con `_`.
- `MATERIALES OBRA` importa solo la columna Material; categoría y código los
  calcula la hoja. Antes se copiaba entera, encima de sus fórmulas.
- **Defecto adicional encontrado.** Una columna calculada que el archivo traía
  con el mismo encabezado se escribía como columna extra sobre la fórmula de la
  plantilla. Ahora no se escribe, y los encabezados `(calc.)` no cuentan como
  extra.
- **Restaurar versión.** `construction_version_reason` guarda la acción que
  originó cada versión. La hoja carga la versión sin mostrarla
  (`fetchSpreadsheetModel`), compara por clave y reescribe las columnas de dato
  con el mismo camino de la importación. Se compara en el navegador porque el
  contenido vigente de una hoja está en sus revisiones, que el servidor no
  reproduce.
- **Pendiente para la entrega 3:** reconocer la `OBRA` de un libro de venta, y
  importar `ACABADOS DE OBRA`. Esas pestañas todavía no existen.
- **Pendiente para la entrega 4:** la acción «Cancelar» de M117-08 usa esta misma
  restauración.

### M117-04 · Listas que sobreviven

La causa exacta es más estrecha que la del requerimiento: `DELETE_CONTENT` quita
de una regla de lista de valores cada celda **que ya estaba vacía**, igual que la
tecla Suprimir en la hoja (`o_spreadsheet.js`, `DataValidationPlugin`). Por eso se
perdían las listas de las filas sin dato.

`clearCells` vacía con `UPDATE_CELL` solo las celdas con contenido. La usan la
importación y `clearData` del puente común. Las listas fijas se crean con
`isBlocking: true` en las dos hojas; el bloqueo actúa al escribir en la celda, no
en las escrituras del sistema, así que la importación sigue pudiendo traer un
valor que después marca «Validar».

Las hojas ya creadas toman el rechazo con «Actualizar a la plantilla vigente».

### M117-06 · CONTROL

`updateControl` recibe el modelo de la acción. El entorno de la acción no lo tiene.

### M117-10 · Requerimiento aprobado después del plan

- La regularización incluye los requerimientos «En aprobación».
- `_construction_assign_request_lines` es la única regla de asignación, en la
  regularización y al aprobar.
- `_construction_settle_no_plan` corre al aprobarse un requerimiento «Sin plan»:
  lo asigna si hace falta, deja el control en «Aprobado» u «OK» y escribe el
  mensaje en el requerimiento y en el plan. Va en `_write_approved` del puente de
  compras, por donde pasan los dos motores de aprobación solo cuando la aprobación
  es definitiva.

## 3b. Entrega 2

### Diseño de la hoja de planificación (M117-01, M117-23)

`sheet_design.py` tiene la ficha de cada pestaña; la plantilla, la ampliación y
«Actualizar a la plantilla vigente» aplican lo mismo. `construction_sheet_layout`
pasa a 2 en la hoja de planificación: una hoja anterior tiene las columnas y
`_LISTAS` en otro orden, así que la ampliación pide actualizarla antes.

Diferencias con el Anexo A, para que Vicente las acepte o las devuelva:

| Ficha | Qué se hizo | Por qué |
|---|---|---|
| Porcentajes con formato `0%` (TARIFAS, CONTRATOS, HITOS) | Formato `0"%"` | El envío lee 30, no 0.30. Con `0%`, 30 se vería como 3000 %, y cambiar la lectura rompería los libros de carga |
| Línea superior al cambiar de tipología o de módulo (MODULOS, BOM) | No se hizo | El formato condicional de la hoja no admite bordes |
| Mueble de MODULOS «de la misma tipología» | Lista de todos los muebles de MUEBLES | Son pocos nombres que se repiten; una lista por fila agrega seis filas de `_LISTAS` a cada fila de datos |
| «Resumen del piso» (ARBOL) como columna fija | La sigue creando `floor_groups.js` al agrupar | Su presencia indica que la hoja está agrupada |
| Listas de Odoo: Cliente, Contratista, Unidad y Categoría de PRODUCTOS NUEVOS | Pendientes para la entrega 3 | Necesitan listas nuevas en REFERENCIAS, con costo al abrir la hoja |
| Páginas INICIO, FICHA, PROGRAMA, CONTROL | Solo la paleta | Su ruta y sus bloques nuevos son de M117-16, en la entrega 3 |
| Pestañas PARAMETROS, ACABADOS DE OBRA, VENDIDO; columnas nuevas de CONTRATOS; «Clase (calc.)» | No existen todavía | Son de las entregas 3 y 4 |

El nombre visible del estilo de tabla es «Hoja de trabajo», sin el nombre del
cliente, porque el repositorio es público.

### Orden de columnas y listas (M117-02)

El orden en pantalla (`COLUMN_ORDER`) no toca `SHEETS`: el libro de carga y el
importador no cambian. Los módulos por tipología siguen el patrón de las
categorías: una fila de `_LISTAS` por tipología, con su `FILTER`, y cada fila de
datos la busca con `INDEX`/`MATCH`.

### «Traer de Odoo» (M117-07)

Con recetas por módulo no se escribe ninguna línea de la receta de la tipología:
es la suma redondeada de los módulos. **Consecuencia:** una línea agregada a mano
a esa receta en Fabricación tampoco se trae; ya hoy «Validar» la rechaza porque no
llegaría al plan.

### Inicio (M117-09)

`project.project._construction_home_extra` es el gancho del núcleo: el puente de
la hoja aporta su estado y su acción, y el de ventas, la venta.

## 3c. Entrega 3

### Parámetros (M117-15)

`construction.sheet.parameter` guarda la lista por compañía y la exporta con el
perfil. Cada hoja copia los de su tipo a PARAMETROS; las fórmulas leen la columna
oculta I («Valor usado», vacío: el inicial) por `XLOOKUP` de la clave. Vaciar la
celda no vuelve a escribir el inicial, pero la hoja calcula con él. La columna
oculta J recibe al abrir el inicial vigente, para el aviso en ámbar. En un
porcentaje, la configuración guarda 18 y la celda 0.18.

### Hoja de venta (M117-16 a M117-20)

`sale_sheet.py` arma la plantilla y su registro propio de pestañas (`SALE_COLUMNS`);
`SHEETS` no cambia salvo una columna opcional. Las fases siguen a la cotización en
`sale.order.write` y `message_post`. Columnas ocultas agregadas respecto del Anexo A,
porque `XLOOKUP` no acepta rangos concatenados: Clave en TARIFARIO, Fila del
tarifario en PRECIOS, Fila de PRECIOS en METRADO y Partida en el resumen de METRADO.

### Cotización (M117-21)

El servidor no evalúa fórmulas de una hoja. «Pasar el resumen» lleva lo que muestra
la hoja a `sale.order.construction_sale_summary`; de ahí leen el PDF y «Traer la
venta». El orden del PDF sale de ese resumen, no de una lectura en vivo: una hoja
cambiada sin pasar el resumen no cambia el PDF.

### Traer la venta (M117-22)

La pestaña oculta `_HUELLA` guarda lo que se trajo por clave de fila. Lo que difiere
de la huella se muestra desmarcado; lo demás, marcado. Una fila que sobra se vacía en
su lugar y queda sin dato hasta que el envío la ignora.

### Propuestas devueltas: decisión pendiente de Vicente

- **D1, descuento.** El factor pasó a 6 decimales. El ajuste del último céntimo en la
  última valorización **no está programado**: con 6 decimales la diferencia del
  ejemplo baja de 4.81 a centavos, pero no llega a cero.
- **D2, partida con dos líneas.** Una tipología nueva de un adicional va a la línea
  más reciente de su partida. Una tipología que ya existía conserva su línea: si le
  cambian ambientes o precio, la valorización de esa partida no cuadra con las dos
  líneas de la orden hasta decidir cómo se reparte. CONTROL muestra la diferencia.

### Lo que queda distinto del Anexo A

| Ficha | Qué se hizo | Por qué |
|---|---|---|
| Línea superior al cambiar de módulo, tipología o bloque | No se hizo | El formato condicional de la hoja no admite bordes |
| «Siguiente» con borde negro en INICIO | Texto «◀ Siguiente» en «Qué falta» | Igual que el anterior |
| Fases como chip negro en INICIO | Celda con la fase | Un chip no existe en la hoja |
| Vaciar un parámetro vuelve a escribir el inicial | La celda queda vacía y la hoja calcula con el inicial | Reescribirla exigiría una regla en cada edición |
| «Departamentos vendidos» y «Subtotal de la cotización» en CONTROL | Filas nuevas en OBRA, que escribe «Traer la venta» | VENDIDO no tiene un total por obra |

## 3d. Entrega 4

| Código | Qué se hizo | Dónde |
|---|---|---|
| M117-08 | Cuadro de avance, Cancelar a la versión guardada, un recálculo por lote, reglas sin solape sin copia | `sheet_progress.js`, `sheet_import.js`, `send_to_planner.js` |
| M117-11 | Devolución descontada de lo entregado y «Cerrar con lo recibido» | `al_construction_material_request`, `al_construction_planner_purchase` |
| M117-12 | Precio del proveedor en la solicitud de presupuesto | `purchase_request_line_make_purchase_order.py`, `purchase_order_line.py` |
| M117-13 | Categoría y nombre propios para el requerimiento interno | `al_construction_planner_approvals` |
| M117-14 | Ruta completa del nivel en vales y requerimiento | `_get_report_level_label` |
| M117-24 | Catálogo `construction.furniture.type` | `al_construction_planner_furniture`, hoja |
| M117-25 | Factura por partida o de una línea, vista previa, anexo y registro `construction.valuation.invoiced` | `al_construction_planner_sale`, `_sale_furniture` |

### Medición de M117-08

La causa del congelamiento no era el tamaño de la escritura sino dos costos que
crecían con la hoja. La plantilla nace con 300 filas, así que toda importación
grande amplía antes de escribir:

1. **Dependencias celda por celda.** Un lote de 2,000 celdas actualizaba las
   dependencias de cada una y recalculaba las búsquedas que miran esas columnas. Un
   lote grande pide ahora un solo recálculo completo al terminar. Los lotes de menos
   de 200 comandos siguen siendo incrementales.
2. **Reglas de validación.** BOM y PIEZAS llevan tres reglas por fila. Cada regla
   nueva copiaba y recortaba todas las anteriores de la pestaña: con 10,000 reglas,
   varios minutos, también al reabrir la hoja antes de su siguiente instantánea.

El tamaño del lote (2,000 comandos) se revisó con 1,000, 2,000 y 10,000 y se
mantiene: uno mayor deja la pantalla quieta más tiempo sin ganar nada apreciable.

| Caso, en el recorrido automático con Chrome sin ventana | Antes | Después |
|---|---|---|
| Ampliar de 10 a 1,650 filas, con sus tablas dinámicas | más de 6 min, congelada | unos 40 s, con la pantalla viva |
| Escribir y validar 1,500 filas de ARBOL en una hoja ya ampliada | no medido por separado | unos 17 s |
| Cancelar a la mitad | no existía | unos 3 s |

**Medición del 11-nov-2026.** La plantilla vigente escribe unas 66,000 fórmulas, 152 bloques
de formato y 9,880 reglas al ampliar a 1,650 filas, y la ampliación había subido a unos 105 s.
El costo no estaba en escribir sino en evaluar: cada lote evaluaba las fórmulas nuevas, cada
`UPDATE_TABLE` recalculaba el libro entero (unos 17 s) y las tablas dinámicas lo recalculaban
otra vez al final. Ahora la ampliación escribe con la evaluación aplazada y evalúa el libro una
sola vez, al cerrar, junto con las tablas y las tablas dinámicas:

| Ampliar de 10 a 1,650 filas | Tiempo |
|---|---|
| Con la plantilla vigente, antes | unos 105 s |
| Tablas y tablas dinámicas en un solo lote | unos 62 s |
| Además, evaluación aplazada hasta el final | unos 48 s |

De esos 48 s, unos 20 s son el recálculo final del libro y unos 10 s el formato de las
columnas (un comando por celda en la hoja de Odoo, lo mismo con `SET_FORMATTING` que con
`UPDATE_CELL`). El recálculo crece con las fórmulas que miran columnas enteras
(`COUNTIF(ARBOL!$E:$E…)`, `SUMIFS`, `XLOOKUP`, `FILTER`); bajarlo es cambiar la plantilla.

**Importación sobre la hoja ya ampliada (11-nov-2026, segunda medición).** El tiempo no
estaba en escribir las celdas (unos 3 s) sino en los recálculos completos del libro: uno al
quitar las filas de resumen por piso y otro al volver a insertarlas. Medido por fórmula, el
recálculo completo (unos 15 s) se iba casi todo en dos cosas:

- unos 10 s en el evaluador de la hoja de Odoo: tras cada lista de _LISTAS que derrama
  (unas 3,300, tres por fila de PIEZAS y de BOM) copiaba y volvía a agregar todas las celdas
  pendientes. Se reemplazó ese paso por uno que agrega solo las nuevas
  (`ARQUITECTURA_COMUN.md`, sección 7);
- unos 3 s en «Nombre del módulo (calc.)» de PIEZAS y BOM: un `FILTER` de MODULOS por fila.
  La hoja de Odoo evalúa las dos ramas de `IF`, así que las filas vacías también lo pagaban.
  Ahora toma el nombre de la lista «código · nombre» de su tipología en _LISTAS (búsqueda en
  caché). Las hojas existentes lo reciben con «Actualizar a la plantilla vigente»; hasta
  entonces, las filas nuevas de una ampliación ya traen la fórmula nueva y dan el mismo
  resultado que las anteriores, salvo un módulo cuya tipología no está en TIPOLOGIAS, que
  queda sin nombre (tampoco aparece en la lista de Módulo).

Además, la importación escribe, quita y rehace los grupos por piso con la evaluación
aplazada, y evalúa una sola vez al final.

| Recorrido automático, 1,500 filas de ARBOL, 38 pisos | Antes | Después |
|---|---|---|
| Recálculo completo del libro (1,650 filas) | unos 15 s | unos 6 s |
| Importar en la hoja ya ampliada | unos 30 s | unos 18 s |
| Volver a importar (reemplazar) sobre la hoja agrupada por piso | dos recálculos completos | unos 20 s, uno solo |

De los 18 s, unos 6 s son el recálculo, unos 6 s insertar las 38 filas de resumen (la hoja
ajusta todos los rangos en cada inserción) y el resto leer el archivo, escribir y validar.

**Filas de resumen sin insertar filas (11-nov-2026, tercera medición).** De esos 18 s, unos
12 s eran las filas de resumen: insertar 38 filas (la hoja ajusta todos los rangos del libro
en cada una) y el recálculo completo que obliga una inserción. Ahora la fila de resumen es
una fila más de la plantilla: agrupar reacomoda las celdas escritas de ARBOL (no las
fórmulas), en orden y sin filas vacías, y deja libre la fila de encima de cada piso; quitar
los grupos solo borra el texto del resumen. Como no cambia la forma de la hoja, solo se
recalcula lo que depende de las celdas movidas. La importación cuenta esas filas al pedir
la ampliación. Si las filas de la plantilla no alcanzan (la última fila destino no tiene
las fórmulas), se insertan como antes; las hojas con resúmenes insertados se limpian
borrando esas filas, una vez.

| Recorrido automático, 1,500 filas de ARBOL, 38 pisos | Antes | Después |
|---|---|---|
| Importar en la hoja ya ampliada | unos 18 s | unos 7 s |
| Volver a importar (reemplazar) sobre la hoja agrupada | unos 16 a 20 s | unos 7.5 s |

Cambio visible: las filas vacías dentro de ARBOL desaparecen al agrupar (antes cortaban el
bloque del piso y quedaban fuera de los grupos).

**Sin medir: la obra grande de 8,000 líneas en BOM** (punto 1 del pedido). La corrida
anterior de 8,000 filas agotó la memoria de la máquina de desarrollo y no se repitió.
La meta de menos de 60 s (D3) sigue sin acordar: con 1,500 filas se cumple; con 8,000
hay que medirla en un equipo con más memoria antes de darla por cumplida.

«Actualizar a la plantilla vigente» no lleva el cuadro: la hace el servidor y no
escribe por lotes en el navegador.

### Decisiones y diferencias

- **M117-24, el dato guardado sigue siendo el código.** Como las etapas, reglas,
  actividades y tareas guardan el código del tipo y no una relación: agregar un tipo
  no obliga a migrar esos datos. El módulo sí guarda `type_id`.
- **M117-24, `FURNITURE_LAYOUT` 4.** La clase de MODULOS pasa a ser calculada y las
  fórmulas leen REFERENCIAS AB:AD. Una hoja anterior debe usar «Actualizar a la plantilla
  vigente» antes de ampliarse; hasta entonces sigue funcionando y lo avisa al ampliar.
- **M117-08, la ampliación no se cancela.** «Cancelar» se desactiva mientras se amplía
  y vale desde la primera fila de datos: una ampliación a medias dejaría filas sin
  fórmulas. Las filas de más quedan en la hoja y no molestan.
- **M117-13, con el motor de niveles** la regla se llama «Aprobación de requerimiento
  interno: grupo», sin documento ni área: la regla es una sola para todos los
  documentos. Con el motor `approvals` el nombre sí lleva documento y área.
- **M117-08, atajo en un método de la hoja.** `removeRangesFromRules` se parchea para
  toda hoja de la base y llama a `super()` si hay solape. Sin solape el resultado es
  el mismo.

## 4. Pruebas

Bases autorizadas para el paquete: `test_pe_construction_core` (núcleo y
requerimientos) y `test_pe_creval` (hojas, porque necesitan Documentos). La
configuración de dev1 no se toca: es parte de la prueba de Vicente.

Los criterios que mencionan hojas concretas de dev1 (por ejemplo, restaurar la
hoja vigente de la obra de prueba) los prueba Oficina Técnica en dev1 una vez
desplegada la entrega; aquí se prueban con datos propios de los tests.
