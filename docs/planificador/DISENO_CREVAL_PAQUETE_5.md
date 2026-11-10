# Diseño del paquete 5 de CREVAL · hojas de venta y de planificación

Fuente: «Requerimiento de desarrollo · Paquete 5» v1.1 (10-nov-2026), CR-38 a
CR-47, que absorbe CR-28 y CR-32 del paquete 4. Los nombres de obra, montos y
usuarios de la prueba no se copian: el repositorio es público. Manda
`ARQUITECTURA_COMUN.md` en lo común.

## 1. Revisión de configuración

Cada requerimiento trae sus alternativas descartadas en las cuatro rutas.
Ninguna ruta configurable cumple: la hoja de Odoo no tiene tipos de hoja,
menús propios ni pasos guiados, y ningún módulo de `OL-THIRD-PARTY` trata hojas
de cálculo.

## 2. Entregas

| Entrega | Requerimientos | Qué resuelve |
|---|---|---|
| 1 | CR-38, CR-44, CR-47 | Dos hojas (venta y planificación) con su menú y su entrada, grupo «Presupuestador», «Pasar a la cotización» sin plan ni confirmación, contrato de obra en borrador al confirmar |
| 2 | CR-39, CR-40, CR-41 | INICIO con ruta, OBRA con listas y parámetros de la compañía, PRESUPUESTO para el presupuestador (títulos, APU por nombre, estado, TOTAL) |
| 3 | CR-42, CR-43, CR-44 (pie) | APU y APU_DETALLE por nombre con biblioteca, INSUMOS desde el maestro, PIE DE PRESUPUESTO |
| 4 | CR-45, CR-46 | «Traer la venta» con vista previa y huella, PLAN con lo vendido en gris, APU de obra como copia, CONTROL vendido frente a planificado |

## 3. Hecho · entrega 1 (10-nov)

- CR-38: `documents.document.construction_budget_role` (`sale`, `plan`; vacío =
  la hoja «Presupuesto y plan» de antes, que sigue igual con su menú). La hoja
  de venta se llama «Presupuesto de venta · cotización · cliente» y su menú es
  Validar, Pasar a la cotización, Actualizar insumos, Traer de Odoo y Nueva
  versión; la de planificación, «Planificación de obra · obra», con Traer la
  venta, Validar, Enviar al planificador: plan y Nueva versión. El servidor
  rechaza el envío que no corresponde a la hoja. Las dos usan las mismas
  claves de columna e importadores. Hasta la entrega 4, «Traer la venta» es
  «Traer de Odoo» (trae las partidas de la cotización de la obra).
- CR-44: «Pasar a la cotización» valida y pasa el presupuesto (destino
  Presupuesto: sin niveles, APU de obra ni plan) y no confirma la cotización
  (no se encontró ninguna confirmación en el envío, D1). Con la cotización
  confirmada, avisa que los cambios van por cambio de obra (D3). Al confirmar
  la cotización de una obra sin contrato nace el contrato de obra en borrador
  («Venta <cotización>», con cliente, obra, orden y la plantilla de hitos de
  la compañía) y la cotización lo dice (D2). El envío de mobiliario busca el
  contrato por ese nombre y no lo duplica.
- CR-47: grupo «Presupuestador» (Ventas y Documentos). La cotización tiene una
  sola entrada, «Hoja de presupuesto» (presupuestador o planificador); la obra
  por partidas, «Hoja de planificación» (planificador). Pulsar dos veces abre
  la misma hoja. El presupuestador revisa y pasa su presupuesto aunque no
  administre recetas ni productos: el destino Presupuesto corre como el
  sistema y no toca el plan. «Importar presupuesto» e «Importar libro» siguen
  solo para el planificador.

Pendiente de la entrega 1: «Actualizar a la plantilla vigente» para convertir
las hojas «Presupuesto y plan» en hoja de venta (decisión del 05-nov) va con
el nuevo diseño de las pestañas (entrega 2), porque convierte a ese diseño.

## 4. Hecho · entrega 2 (10-nov)

- CR-39: INICIO es la primera pestaña de la hoja de presupuesto: obra,
  cliente y última validación; ruta (OBRA, PRESUPUESTO, APU, INSUMOS,
  Validar) con el estado calculado por la hoja y «◀ Siguiente» en el primer
  paso pendiente; indicadores (partidas, por corregir, costo directo y total
  con IGV). Las pestañas van en el orden de trabajo y LISTAS, REFERENCIAS,
  _CLAVES e INSTRUCCIONES quedan ocultas.
- CR-40: parámetros de la compañía en Ajustes › Hoja de presupuesto (gastos
  generales, imprevistos, utilidad y margen por defecto; días de un precio
  antiguo; umbral de CONTROL). OBRA nace con el nombre de la obra (o el
  proyecto de la cotización), los porcentajes que la cotización no trae, el
  IGV de venta de la compañía, la fecha, la versión y «Margen por defecto %»;
  una partida sin margen escrito usa ese margen en la hoja y en el envío.
- CR-41: PRESUPUESTO tiene «Estado» (no se envía): «Título», «Falta APU o
  costo», «APU no existe», «APU sin costo», «Falta unidad» u «OK», en rojo si
  no está bien; las filas de título en negrita y gris; el ítem como texto; la
  partida ancha (360) y fija con el ítem, la especialidad y la
  sub-especialidad.

Pendiente de la entrega 2: el APU elegido por nombre en PRESUPUESTO y el
cálculo de Especialidad y Sub-especialidad desde el título de arriba (necesitan
la lista «nombre · código» de APU, que llega con CR-42 en la entrega 3), la
fila de TOTAL fija arriba (se lee hoy en INICIO; moverla corre todas las filas
del envío) y el grupo plegable de holguras.

## 5. Hecho · entrega 3 (10-nov)

- CR-42: APU calcula «Usado en» (partidas que lo usan), «Estado» («Sin
  código», «Sin detalle», «Sin uso» u «OK») y «Código propuesto» («R» y el
  siguiente número libre); el envío da ese mismo código al APU escrito solo
  con su nombre. APU_DETALLE muestra el total del APU en su primera fila (la
  franja de color por APU ya existía). La biblioteca de la compañía ya llega
  al crear la hoja de una cotización sin obra (D4).
- CR-43: INSUMOS calcula «Usado en» (APU que lo usan) y «Estado» («Producto
  nuevo sin precio», «Precio de más de N días» con N de Ajustes, u «OK»).
- CR-44, punto 1: pestaña PIE DE PRESUPUESTO: costo directo, gastos
  generales, imprevistos y utilidad, subtotal, descuento, valor de venta, IGV
  y total, con los porcentajes de OBRA y las mismas reglas que el pie de la
  cotización; debajo, el parcial y el peso de cada especialidad.

Pendiente: elegir el insumo de INSUMOS por nombre de un producto del maestro
con tipo, unidad, código y precio llenados solos (las columnas de dato de hoy
no pueden ser fórmulas; necesita una columna «Producto» con lista y las de
dato pasadas a calculadas, como BOM de mobiliario), y el aviso de cuántos APU
e insumos trajo «Traer de Odoo».

## 6. Hecho · entrega 4 (10-nov)

- CR-45: PLAN trae cada partida vendida (también sin partida en la obra
  todavía) y muestra en gris la unidad, el metrado vendido y el APU vendido
  (de PRESUPUESTO, por el ítem); el planificador escribe «Metrado de obra»,
  la modalidad final, el contratista, la etapa y las fechas; «Estado (calc.)»
  dice «Falta modalidad», «Metrado ±x %», «Fecha fuera de orden» u «OK». El
  envío del plan usa el metrado de obra (vacío, el vendido) y la cotización no
  cambia (D3).
- CR-46: pestaña CONTROL: por partida de PLAN, costo vendido sin margen (el
  «Costo real»), costo planificado (metrado de obra × costo unitario),
  diferencia, % y semáforo («Igual» bajo 0.5 %, «Más de lo vendido» hasta el
  umbral, «Supera el umbral» en rojo) con el umbral de Ajustes.

Pendiente: la vista previa y la huella de «Traer la venta» (hoy es «Traer de
Odoo», que reescribe PLAN con lo vendido), los APU de obra como copia de los
vendidos, la comparación con el plan de Odoo después del envío y el día de
fuera de la obra contra el inicio y el fin de la obra.

## 7. Hecho · pendientes de las entregas (10-nov)

- CR-38, punto 4 (pendiente de la entrega 1): «Actualizar a la plantilla
  vigente…» en la hoja «Presupuesto y plan» guarda una versión y la rehace
  como hoja de presupuesto de venta con la plantilla de hoy y lo escrito en
  ella: OBRA, INSUMOS, APU, APU_DETALLE, PRESUPUESTO y PLAN, leídos por su
  clave o encabezado como el envío. El APU y el insumo pasan a elegirse por
  nombre; la Especialidad y la Sub-especialidad escritas en las filas pasan a
  filas de título donde el ítem tiene ese nivel. La hoja queda ligada a la
  cotización con el nombre «Presupuesto de venta · …».
- CR-41 (pendiente de la entrega 2), plantilla 3 de PRESUPUESTO: Ítem,
  Partida, Und, Metrado, «APU (escriba el nombre)» con lista de APU por
  nombre, Costo sin APU, Costo unitario, Precio unitario, Parcial, Estado y
  Especialidad a la vista; Sub-especialidad, modalidad, holguras, margen,
  costos ofertados, reserva, catálogos y «Código del APU (calc.)» en el grupo
  plegado «Holguras y margen». Especialidad y Sub-especialidad se calculan del
  título de encima por el ítem, con la regla de `budget_code_levels`. Las
  claves no cambian: `apu` se lee de la columna calculada y el envío acepta
  también los encabezados cortos. Las hojas anteriores (plantillas 0 a 2)
  siguen con su orden al traer de Odoo.
- Formatos de la hoja de presupuesto: las zonas guardaban el formato como
  texto y la hoja lo ignoraba; ahora se registran en `formats` del libro, como
  mobiliario. El ítem «01» ya no se vuelve 1, y los importes de INICIO, PIE y
  CONTROL salen con dos decimales. El ítem de PLAN también es texto: antes
  «01.01» se guardaba como 1.01 y PLAN no encontraba la partida en
  PRESUPUESTO (unidad, metrado y APU vendidos vacíos).
- CR-43 (pendiente de la entrega 3): «Traer de Odoo» dice cuántos APU,
  insumos y partidas trajo.
- CR-45, punto 2 (pendiente de la entrega 4): «Traer la venta…» de la hoja de
  planificación abre la vista previa de mobiliario (M117-22), ahora común en
  `bring_preview.js` de la hoja base. PLAN compara por ítem solo ítem y
  partida; lo que escribe el planificador no se trae. Los APU de obra (INSUMOS,
  APU y APU_DETALLE) se comparan por su código: lo cambiado en la hoja desde
  la última vez va desmarcado (huella en `_HUELLA`). OBRA y PRESUPUESTO son la
  copia de lo vendido y se reescriben.
- CR-45, punto 3 (pendiente de la entrega 4): OBRA lleva «Inicio de la obra»
  y «Fin de la obra» (de la obra; el envío no los lee) y el estado de PLAN dice
  «Fecha fuera de la obra» si el inicio o el fin de la partida caen fuera.

Pruebas en `test_creval_package5.py`: plantilla 3, envío con los encabezados
cortos, conversión de la hoja anterior, «Traer la venta» del servidor, fecha
fuera de la obra, y un recorrido del navegador para la vista previa con
huella. El recorrido de fórmulas (`budget_formulas_tour.js`) calcula en el
navegador el código del APU elegido por nombre, la especialidad, la
sub-especialidad, el costo y el estado.

## 8. Diferencias frente al requerimiento

- Fila de TOTAL fija arriba (CR-41, punto 3): no se hace. Toda la hoja (envío,
  PLAN, CONTROL, PIE e INICIO) lee PRESUPUESTO desde la fila 2; una fila de
  total ahí se leería como partida o sumaría dos veces. El número de
  partidas, las que hay por corregir, el costo directo y el total con IGV
  están en INICIO.
- Modalidad por defecto la del APU (CR-41, punto 4): la columna queda en el
  grupo plegable; el envío ya toma la del APU si la partida no la escribe.
- Una hoja anterior con ítems de dos niveles y la Sub-especialidad escrita en
  las filas pierde esa sub-especialidad al actualizarse: la plantilla 3 la
  calcula de un título de segundo nivel que el ítem no tiene.
- Vista previa de «Traer la venta»: por pestaña (Nuevo, Cambia, Igual, Sobra)
  con las filas que cambian, como mobiliario, no una tabla por partida con
  metrado vendido y APU.

Siguen pendientes: elegir el insumo de INSUMOS por nombre de un producto del
maestro (CR-43; necesita pasar tipo, unidad, código y precio a columnas
calculadas), los APU de obra como recetas propias de la obra al enviar el plan
(CR-45, punto 4) y la comparación de CONTROL con el plan de Odoo después del
envío (CR-46, punto 3).
