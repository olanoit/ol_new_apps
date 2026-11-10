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
