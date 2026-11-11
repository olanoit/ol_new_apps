# Diseño del paquete 1.18 · hallazgos de la prueba como persona

Fuente: «Requerimiento · paquete 1.18» (07-nov-2026, revisado el 08 y el
09-nov, con su cruce con el 1.19), 15 requerimientos (M118-01 a M118-15).
Este documento recoge cómo se desarrolla, lo que se devuelve antes de
programar y la estimación. Los nombres de obra, montos y usuarios de la prueba
no se copian aquí: el repositorio es público.

Manda sobre este documento `ARQUITECTURA_COMUN.md`, en lo común. Va después
de las cuatro correcciones del 1.19 (`DISENO_v1.19.md`, sección 9).

## 1. Revisión de configuración (sección 3 de la arquitectura)

| Requerimiento | Ruta revisada | Resultado |
|---|---|---|
| M118-03 | Plantilla de hitos por defecto de la compañía | Necesaria (va en «Configuración y datos»), pero no asocia la orden ni crea los hitos |
| M118-04 | «Aplicar costo» y «Precios de compra del producto» de hoy | Funcionan por producto; el pedido es por grupo |
| M118-05 | Subir el tiempo límite del servidor | No da avance ni evita un segundo «Generar» |
| M118-06 | «Escribir fechas en OBRA» | Escribe las fechas de la obra, no las de cada piso y sub etapa |
| M118-12 | «Pegar solo valores» de la hoja | La hoja de Odoo rechaza igual el cruce del panel fijo |
| M118-15, punto 6 | Lista fija de tipos de pieza | Se resuelve con el catálogo de tipos de M117-24 (nivel Pieza): es desarrollo menor |

No se encontró una ruta configurable que cumpla alguno de los 15.

## 2. Entregas

En el orden que propone el requerimiento. Cada una se prueba y se acepta antes
de la siguiente.

| Entrega | Requerimientos | Qué resuelve | Estimación |
|---|---|---|---|
| 1 | M118-01, 02, 03, 04 | Lo que lleva a decidir mal: margen, ruta de INICIO, contrato e ingreso, costo de referencia y «Aplicar costo» por grupo | 10 a 13 días |
| 2 | M118-05, 12 | Lo que impide terminar: «Generar plan» por pisos y en segundo plano; pegado de bloques | 7 a 11 días |
| 3 | M118-08, 09, 13 | La memoria de la persona: «código · nombre», rótulo del ETO, copiar tipología | 5.5 a 8 días |
| 4 | M118-06, 10, 11 | Lo que se escribe dos veces: programa de la hoja en el plan, ML una vez, tableros y cantos desde PIEZAS | 7.5 a 10 días |
| 5 | M118-07, 14, 15 | Mismas cifras en hoja, plan y obra; resultados a la vista; ajustes menores | 5.5 a 8 días |

Total: 35.5 a 50 días de desarrollo, sin contar la espera de cada aceptación.
Las menos seguras son M118-05 (segundo plano y medición con la obra grande) y
M118-12 (el pegado es un comportamiento interno de la hoja de Odoo).

## 3. Estimación por requerimiento

| Requerimiento | Estimación | Dónde |
|---|---|---|
| M118-01 Venta neta y margen | 1.5 a 2 días | `planning_sheets.py` (INICIO, FICHA) |
| M118-02 Ruta de INICIO y envío con pendientes | 2 a 3 días | `planning_sheets.py`, `send_to_planner.js`, mensaje en la obra |
| M118-03 Contrato con la orden, hitos e ingreso | 2 a 3 días | `master_import_v18.py`, `al_construction_planner_sale` |
| M118-04 Costo de referencia y «Aplicar costo» por grupo | 4.5 a 5 días | línea del plan (núcleo), `plan_generate_wizard.py`, `al_construction_planner_purchase` (`plan_price_wizard.py`), Ajustes |
| M118-05 «Generar plan» por pisos y en segundo plano | 4 a 6 días | `plan_generate_wizard.py` y su vista; trabajo en segundo plano |
| M118-06 «Generar plan» con PROGRAMA | 3 a 4 días | envío (guarda PROGRAMA en la obra), `plan_generate_wizard.py`, presupuesto de mano de obra |
| M118-07 Las mismas cifras | 2 a 3 días | INICIO, vista previa, CONTROL, obra |
| M118-08 «código · nombre» en las listas | 2 a 3 días | `project_project.py` (listas, REFERENCIAS), envío e importación |
| M118-09 Rótulo del ETO | 1.5 a 2 días | MODULOS, ETO, módulo de plantilla, tarea, vale y etiqueta |
| M118-10 ML escritos una vez | 1.5 a 2 días | MUEBLES, matriz, FICHA, CONTROL |
| M118-11 Tableros y cantos desde PIEZAS | 3 a 4 días | PIEZAS, BOM, envío |
| M118-12 Pegado de bloques | 3 a 5 días | complemento de pegado (puente común), orden de MODULOS |
| M118-13 Copiar tipología | 2 a 3 días | menú de la hoja de planificación |
| M118-14 Resultados a la vista y fechas | 1.5 a 2 días | PRECIOS, RESUMEN VENTA, fechas, hora de «Validar» |
| M118-15 Ajustes menores (8) | 2 a 3 días | varios |

## 4. Lo que se devuelve antes de programar

| # | Punto | Propuesta | Se necesita para |
|---|---|---|---|
| D1 | M118-05: con qué mecanismo va el segundo plano | Acción programada con disparo inmediato (`ir.cron._trigger`) y el avance guardado en el plan: es nativo y no agrega dependencias al núcleo. `queue_job` está en los servidores, pero el planificador no depende de él | Entrega 2 |
| D2 | M118-06: el servidor no evalúa PROGRAMA | El envío guarda en la obra el inicio, el ritmo, el orden y los días por sub etapa de PROGRAMA; el asistente los propone y dice que salen del último envío. Si PROGRAMA cambió después, hay que volver a enviar | Entrega 4 |
| D3 | M118-11: la conversión de m² de piezas a la unidad del tablero | Un dato por producto, «m² útiles por unidad» (4.00, 4.29 en el ejemplo), que llena Oficina Técnica; sin él, la fila calculada se marca y no se envía | Entrega 4 (dato de Oficina Técnica) |
| D4 | M118-12: el pegado que cruza el panel fijo lo rechaza la hoja de Odoo por dentro | Un complemento que intercepta el pegado, lo divide en partes y las escribe en un solo paso que se deshace con Ctrl+Z. Si la hoja no deja deshacerlo en un paso, se devuelve con lo que sí se puede | Entrega 2 |
| D5 | M118-08 y la matriz del 1.19 | La lista de las columnas libres de la matriz pasa a «código · nombre»; la celda guarda el texto y la matriz extrae el código como BOM | Entrega 3 |
| D6 | M118-02, punto 5: mover «Rendimientos» antes de «Programa por piso» | Se mueve y se corrigen las referencias de INICIO que leen filas fijas (las pruebas que miran «Validar y enviar» en A18 se actualizan) | Entrega 1 |

## 5. Configuración y datos (Oficina Técnica y Compras)

Lo que el requerimiento resuelve con configuración: plantilla de hitos por
defecto, modalidad por defecto de Instalación, Acabado y Limpieza, tipos
Lavadero y Nicho de horno, contratas como proveedores, acabado y limpieza
juntos o separados, costos de tres productos, la actividad «crear la hoja de
planificación» y el nombre de un producto en el maestro. Más el dato de D3.

## 6. Hecho · entrega 1 (10-nov)

- M118-01: VENTA calcula el factor del contrato de cada fila, los ambientes y
  la venta neta; TIPOLOGIAS, el factor de su contrato. INICIO muestra venta
  antes de descuento, descuento comercial, venta neta (sin CONTRATOS, el
  «Subtotal de la cotización» de OBRA), margen estimado y su porcentaje, cada
  cifra con «De dónde sale»; el margen negativo va en rojo. FICHA muestra el
  precio neto y el margen por unidad sobre él. Los gráficos y el resumen por
  piso bajan dos filas (resumen desde la fila 46).
- M118-02: «Rendimientos» va antes de «Programa por piso» (A17) y «Validar y
  enviar» es el último paso (A19). «Qué falta» nombra hasta tres elementos y
  «y N más» (tipologías sin módulos, sin materiales o sin precio, actividades
  sin tarifa con su pestaña de la matriz, acabados sin tablero). «Lo que
  falta» (F28) junta los pasos pendientes y el aviso de margen negativo desde
  una columna oculta (K); FILTER sobre un texto concatenado daba error en la
  hoja de Odoo. El envío con pasos pendientes abre un diálogo («Volver a la
  hoja» por defecto, «Enviar igual») y deja la nota en la obra. Plantilla
  `FURNITURE_LAYOUT` 7: las hojas existentes necesitan «Actualizar a la
  plantilla vigente».
- M118-03: el contrato del envío lleva la orden de la obra y cada precio su
  línea de venta (también los que ya existían sin ella); con plantilla de
  hitos los genera al enviar (los facturados se conservan); sin plantilla, el
  análisis y la obra lo avisan y CONTRATOS marca la celda. El ingreso
  contratado de la obra cuenta solo los contratos con hitos; sin ninguno, la
  orden de venta.
- M118-04: `price_reference` y `price_reference_date` en la línea del plan
  (núcleo), que «Generar plan» llena con el costo del maestro en la unidad de
  la línea; la vista previa da el monto con costo decidido, el estimado con la
  referencia y los productos sin costo en el maestro. «Aplicar costo» por
  grupo (`construction.plan.price.group.wizard`, puente de compras): alcance
  (sin costo, selección, categoría, etapa), base y fecha, una fila por
  producto con referencia, base, variación, compras en 6 meses, costo editable,
  «Usar la referencia» y «Aplicar»; las filas que superan «Variación que pide
  revisión (%)» (Ajustes, 10 %) quedan en ámbar y sin marcar; un solo mensaje
  en el plan. Desde la lista de líneas, varios productos abren el de grupo.
  Si lo único que impide la aprobación es el costo, el aviso abre ese
  asistente.

Pendiente de la entrega 1: «De ellos, zócalos» y el desglose de mano de obra
por modalidad van en M118-07 (entrega 5).

## 7. Hecho · entrega 2 (10-nov)

- M118-05: «Generar plan» tiene «Pisos», que llenan los ambientes; los
  ambientes se ven y se buscan por su ruta («Piso / Departamento / Ambiente ·
  tipología») y «Buscar más…» usa una lista con piso, departamento y
  tipología. La vista previa se calcula al elegir el alcance o con «Ver vista
  previa» (al abrir, solo si la obra tiene hasta 30 ambientes). Con más de
  2,000 líneas (parámetro `al_construction_planner_furniture.generate_background_lines`)
  o sin vista previa en una obra grande, «Generar» encola el trabajo (D1:
  acción programada con `_trigger`) y cierra el asistente; el proceso genera
  por tandas de 10 ambientes, guarda el avance después de cada una, aplica el
  ritmo una vez al final y avisa con un mensaje en el plan a quien lo pidió
  (o dice en qué ambiente falló). Mientras genera, el plan muestra el avance
  y «Generar plan» queda deshabilitado. Escape con el calendario abierto ya no
  cierra el diálogo. Medición del 11-nov en dev1, con una copia temporal de
  la obra grande (153 ambientes; la copia se deshizo al terminar): el proceso
  de fondo generó 1,141 tareas de módulo y 27,860 líneas en 230 s (unos 248 s
  para 30,000; meta, 5 minutos). La medición no incluye los 16 commits de las
  tandas.
- M118-12: complemento común de la hoja (`paste_blocks.js`): el pegado desde
  el portapapeles en las pestañas de datos de las hojas del planificador se
  escribe en un solo paso (un Ctrl+Z), cruza las columnas fijas, salta las
  columnas calculadas (encabezado gris o «(calc.)») corriendo el resto de la
  fila y escribe solo el contenido, así que conserva el amarillo. La matriz
  conserva su rechazo. En MODULOS, «Clase (calc.)» va detrás de «Método de
  unión» (`FURNITURE_LAYOUT` 8). El pegado interno (copiar de la misma hoja)
  sigue la regla nativa. Sin prueba automática del navegador: se prueba a
  mano en dev1.

## 8. Hecho · entrega 3 (10-nov)

- M118-08: las listas de Actividad (MODULOS, TARIFAS, MO PROPIA, ACTIVIDADES y
  las columnas libres de la matriz) muestran «código · nombre» desde
  REFERENCIAS E; la de Módulo de BOM y PIEZAS, «código · nombre» desde la
  columna calculada «Para elegir (calc.)» de MODULOS. Queda el «0» al final
  de la lista de Módulo: quitarlo con un FILTER por fila multiplica las
  fórmulas de _LISTAS con las filas de la hoja (la prueba de rendimiento lo
  impide); se resuelve con otra forma de la lista auxiliar. La
  celda guarda el texto completo (D5) y las fórmulas toman el código: TARIFAS
  y BOM y PIEZAS tienen el código calculado («Código de la actividad (calc.)»,
  «Código del módulo (calc.)»), que usan la matriz, ACTIVIDADES y FICHA;
  «Actividad efectiva» y la fila de código de la matriz lo extraen. Nombre al
  lado: «Nombre del módulo (calc.)» en BOM y PIEZAS y «Nombre de la actividad
  (calc.)» en TARIFAS, MODULOS y MO PROPIA (al final de las calculadas). La
  importación y el envío aceptan el código solo o «código · nombre». Un
  código escrito solo (hojas anteriores, «Traer de Odoo») no está en la lista
  y la hoja lo marca como aviso; se envía igual. Falta el punto 5 (ancho del
  tablero en ACABADOS DE OBRA).
- M118-09: «Rótulo en el ETO» en MODULOS y ETO (después del código), en el
  módulo de plantilla (`eto_label`) y en la tarea del módulo
  (`construction_eto_label`); «Generar plan» y la importación del ETO lo
  pasan a la tarea, y el vale lo muestra en la ruta («Cocina / MB01 (MB-1)»).
  La validación avisa de rótulos repetidos en una tipología. No hay una
  etiqueta de fabricación aparte: la ruta del vale es la que se imprime.
- M118-13: «Copiar tipología…» en el menú de la hoja de planificación:
  origen y destino de TIPOLOGIAS, casillas por pestaña (MUEBLES, MODULOS,
  PIEZAS, BOM y las pestañas ACT), reemplazar o agregar si el destino ya
  tiene filas; guarda una versión antes y copia solo las celdas escritas
  (con el rótulo). Sin prueba automática del navegador.

## 9. Hecho · entrega 4 (10-nov)

- M118-06 (D2): el envío guarda en la obra el PROGRAMA de la hoja (inicio,
  pisos por semana, días por sub etapa, orden, hoja y fecha). «Generar plan»
  lo propone y dice de dónde sale; los días van por cada sub etapa del perfil
  (con 2.3 Limpieza) en lugar de cuatro campos fijos. Si la persona cambia el
  ritmo, el inicio, el orden o los días, el asistente marca «Cambiado
  respecto del PROGRAMA» y pide el motivo; al generar, el plazo de cada sub
  etapa del Cronograma pasa como plazo ajustado del presupuesto de mano de
  obra con ese motivo. Sin hoja enviada, los valores de siempre. PROGRAMA
  explica que «Escribir fechas en OBRA» no hace falta para el plan.
- M118-10: MUEBLES calcula «Metros lineales (calc.)» (suma de los anchos de
  sus módulos) y «ML usados (calc.)»; la columna de dato pasa a «ML escritos»
  y, escrita, se marca en ámbar. La matriz lee los ML usados de MUEBLES (sin
  muebles, los módulos y luego TIPOLOGIAS). FICHA muestra la diferencia entre
  los ML vendidos y los de los módulos y la marca en ámbar fuera de
  `tolerancia_ml_venta`.
- M118-11 (D3): «m² útiles por unidad» en el producto (`construction_board_m2`).
  La importación agrega a la BOM de cada módulo el tablero de sus piezas (m² ÷
  m² útiles); un tablero escrito en BOM manda y se avisa, y se avisa del
  tablero sin m² útiles y del escrito sin piezas. Los libros de ejemplo se
  regeneraron.
  Devolución: los cantos necesitan el producto de canto de cada tablero y el
  formato de la columna «Cantos» (por ejemplo «2L 1A»); hoy es texto libre y
  no se convierte a metros. Tampoco se muestran todavía en gris dentro de BOM
  los tableros calculados: se ven en el análisis y en la BOM del módulo.

## 10. Hecho · entrega 5 (10-nov)

- M118-07 (parcial): INICIO muestra «Módulos (todos)» y «de ellos, zócalos»
  (como cuenta «Generar plan»), las contratas de la matriz y el personal
  propio del presupuesto de mano de obra de PROGRAMA (D21:E25). Devolución: el
  total de mano de obra igual al de la vista previa necesita separar en la
  hoja qué actividades de la matriz hace el personal propio (la modalidad de
  cada actividad la decide el plan, M112-04); la propuesta es una fila de
  modalidad en la matriz que lea el catálogo de etapas. El vínculo de «No
  coincide» de la obra a la fila de CONTROL queda para entonces.
- M118-14: RESUMEN VENTA lleva los totales arriba (filas 11-15) y las
  partidas desde la fila 18 (el resumen de «Pasar a la cotización» lee las dos
  formas); las fechas de OBRA (venta y planificación) y el inicio de PROGRAMA
  escritas como texto se marcan en rojo claro; la hora de la validación sale
  en la zona horaria del usuario (o la de la compañía, o la de Lima).
  Pendiente: el precio final de PRECIOS dentro de las columnas fijas cambia las
  letras de las fórmulas de la pestaña; va con la siguiente versión de la
  hoja de venta.
- M118-15: 1) el proyecto de OBRA vuelve a la «Referencia del cliente» de la
  cotización al pasar el resumen; 2) desde la hoja, el asistente se llama
  «Enviar la hoja al planificador» y no habla de Excel; 3) al terminar vuelve
  a la hoja con el resumen; 4) el mensaje de la obra nombra la hoja y su
  versión; 5) el aviso de productos repetidos lleva el módulo; 6) los tipos de
  pieza están en el catálogo (nivel Pieza, con zona frente o estructura) y la
  lista de PIEZAS los lee de REFERENCIAS (AK); 7) «Completar operaciones» se
  ve solo si la obra tiene listas por etapa sin operaciones; 8) el aviso
  «código provisional → producto» de los productos nuevos que ya existían.
