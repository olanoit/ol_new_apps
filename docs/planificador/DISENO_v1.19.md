# Diseño del paquete 1.19 · presupuesto de mano de obra, horario de obra y actividades en matriz

Fuente: «Requerimiento · paquete 1.19» (08-nov-2026, decisiones del 08 y del
09-nov), 5 requerimientos (M119-01 a M119-05). Este documento recoge cómo se
desarrolla, lo que se devuelve antes de programar y la estimación. Los nombres
de obra, montos de la prueba y usuarios no se copian aquí: el repositorio es
público. El ejemplo numérico de los criterios (400 ML, rendimiento 4, jornal
120) es ilustrativo y se usa en las pruebas.

Manda sobre este documento `ARQUITECTURA_COMUN.md`, en lo común.

## 1. Revisión de configuración (sección 3 de la arquitectura)

| Requerimiento | Ruta revisada | Resultado |
|---|---|---|
| M119-03 | Horario de trabajo nativo (`resource.calendar`) | Es la ruta que pide el requerimiento: el planificador solo lo lee. No hay un parámetro nativo que lleve un horario a las hojas, a la cuadrilla y a los jornales a la vez |
| M119-03 | Horas asignadas de Planificación según el calendario del recurso | Usa el calendario del empleado, que es el de la nómina (descartado el 09-nov) |
| M119-01 | APU de construcción (`construction_recipe_calc.py`) | Rendimiento por día dentro de una receta por partida; mobiliario no usa recetas por partida |
| M119-02 | Análisis de control y pestaña «Control» del plan | Comparan montos totales por línea, no semana ni personas |
| M119-04 | Tabla dinámica de la hoja de Odoo 19 | Solo lectura; no se escribe en ella |
| M119-05 | Tablero nativo (`spreadsheet.dashboard`) | Descartado por Vicente el 09-nov: vista propia con permisos |

No se encontró una ruta configurable que cumpla alguno de los cinco.

## 2. Entregas

Se desarrolla por entregas, en el orden que propone el requerimiento. Cada una
se prueba y se acepta antes de la siguiente (decidido el 09-nov).

| Entrega | Requerimiento | Módulos | Estimación |
|---|---|---|---|
| 1 | M119-03 Horario de obra | núcleo, `_crew`, `al_construction_attendance`, `_spreadsheet_furniture` | 3 a 4 días |
| 2 | M119-04 Actividades en matriz | `_spreadsheet_furniture` | 6 a 8 días |
| 3 | M119-01 Presupuesto de mano de obra | núcleo, `_furniture`, `_spreadsheet_furniture`, `_crew` | 10 a 13 días |
| 4 | M119-02 Control semanal | `al_construction_attendance` | 5 a 7 días |
| 5 | M119-05 Tablero de instalación | `al_construction_attendance` (acción de cliente OWL) | 8 a 10 días |

Total: 32 a 42 días de desarrollo, sin contar la espera de cada aceptación. La
entrega 3 es la menos segura: el presupuesto se calcula dos veces, en las
fórmulas de PROGRAMA y en el servidor al enviar (ver D10).

## 3. Lo que se devuelve antes de programar

| # | Punto | Propuesta | Se necesita para |
|---|---|---|---|
| D1 | El requerimiento cita M118-08, 10, 12 y 13 del paquete 1.18, que no está en el repositorio ni tiene documento aquí. M119-04, punto 9, se apoya en M118-12 (las celdas grises no reciben pegado) | **Decidido 09-nov:** M119-04 incluye el rechazo de pegado en sus celdas grises y el nombre de la actividad | Entrega 2 |
| D2 | El prototipo de M119-05 se comparte aparte y no lo tenemos | Recibir el enlace antes de la entrega 5 | Entrega 5 |
| D3 | M119-01, punto 8: «presupuesto de la sub etapa ÷ su cantidad» solo vale con una actividad. Una sub etapa tiene actividades en ML, por ambiente y por unidad | Costo unitario por actividad = jornal ÷ rendimiento exigido de esa actividad. Con una actividad da lo mismo (120 ÷ 4.08 = 29.40) y la suma de las líneas da el presupuesto de la sub etapa | Entrega 3 |
| D4 | M119-01, punto 5: «jornal del rol de la sub etapa». MO PROPIA admite varios roles en la misma sub etapa | Con varios roles, el promedio de sus jornales, y un aviso en ERRORES | Entrega 3 |
| D5 | M119-02: la marcación de la contrata es por obra y día, no por sub etapa | Si la contrata avanzó en varias sub etapas en la semana, sus persona-días se reparten en proporción a lo que justifica su avance (avance ÷ rendimiento exigido), la misma regla que M119-05 usa por piso | Entrega 4 |
| D6 | El Cronograma y la semana de carga usan los días hábiles del horario de la compañía (`res_company.py`, `_construction_site_weekdays`). El requerimiento no los pone en «Quién lo usa» | **Resuelto al programar:** «Generar plan» (en «Quién lo usa») calcula sus días con los días hábiles de la obra, así que con horario de obra los días hábiles salen de él (Cronograma, «Generar plan» y carga semanal cuentan el sábado). Vacío, el horario de la compañía como hoy (P4) | Entrega 1 |
| D7 | Feriados del horario de obra | Los de ese horario (`resource.calendar.leaves` del calendario) más los que ya cuenta el planificador: ausencias globales de la compañía y feriados nacionales de Perú | Entrega 1 |
| D8 | Decisión pendiente 2: redondeo del sábado | En un día con menos horas que la jornada completa, el jornal es horas ÷ jornada completa, sin redondeo y sin tope. **Aceptado 09-nov** | Entrega 1 |
| D9 | Decisión pendiente 1: aviso «Exceso de personal» | La misma banda del presupuesto (±10 %). **Aceptado 09-nov** | Entrega 4 |
| D10 | El servidor no evalúa fórmulas de las hojas. El presupuesto de la obra (punto 7) no se puede leer de PROGRAMA al enviar | El cálculo vive en el núcleo (Python) y se ejecuta con los datos del envío; PROGRAMA lo reproduce en fórmulas para verlo y probarlo. Las pruebas comparan los dos con el ejemplo de los criterios | Entrega 3 |
| D11 | M119-05, punto 8: el % de producción por piso sale de las órdenes de fabricación. Solo son por piso si «Producir» agrupa por piso (`plan_production_wizard.py`, `group_by`) | Con órdenes por piso, producido ÷ cantidad de la orden. Con órdenes que juntan pisos, se reparte lo producido entre sus ambientes en el orden de la orden | Entrega 5 |
| D12 | Los criterios de M119-04 usan la obra de la prueba en dev1 | Se programa contra pruebas propias; la revisión contra dev1 se hace con permiso de solo lectura, sin tocar la obra ni sus hojas | Entrega 2 |

## 4. Entrega 1 · M119-03 Horario de obra

- Núcleo (`construction_site_schedule.py`): `res.company.construction_site_calendar_id`
  en Ajustes › Obra, con las cifras derivadas de solo lectura (horas por semana,
  jornada completa = día más largo, jornales por persona y semana). Ayudas:
  `_construction_site_hours`, `_construction_day_factor`,
  `_construction_equivalent_days`, `_construction_is_short_day`,
  `_construction_day_window`. Con horario, los días hábiles de la obra y sus
  feriados salen de él (D6, D7).
- «Horas de la jornada» (núcleo) y «Horas por jornal» (`_crew`) son calculados
  y guardados: con horario, la jornada completa y de solo lectura; sin él, el
  valor escrito.
- `_crew`, «Asignar cuadrilla»: con horario, un turno por día con las horas de
  ese día; los días por semana y las horas por semana se proponen desde el
  horario (5.625 y 45). Sin horario, el turno semanal de antes. Los jornales
  se guardan con 4 decimales.
- `al_construction_attendance`: en un día corto el jornal es horas ÷ jornada
  completa, sin redondeo (D8).
- `_spreadsheet_furniture`: PARAMETROS agrega «Horas de la jornada completa» y
  «Jornales por persona y semana» (solo lectura); con horario, esos dos y «Días
  de trabajo por semana» se escriben al crear, abrir y validar la hoja.
- La pestaña oculta con los días equivalentes por fecha se agrega en la
  entrega 3, que es la que la usa.

## 5. Entrega 2 · M119-04 Matriz de actividades

- `activity_matrix.py` (`_spreadsheet_furniture`): una pestaña «ACT …» por
  etapa padre del perfil de la obra con actividades en sus sub etapas; el
  nombre es el de la sub etapa si es una sola («ACT ARMADO») o el de la etapa
  padre («ACT INSTALACIÓN»). Van donde estaba ACTIVIDADES, que queda oculta.
- Filas: encabezado «nombre · unidad», código (oculta), qué hace la columna
  (oculta: `data`, `ml`, `module`), sub etapa, tarifa (TARIFAS o la base del
  catálogo), cantidad en la obra y una fila por tipología de TIPOLOGIAS
  (150 filas). Al final, 5 columnas libres con lista para agregar otra
  actividad y «Ambientes», «Costo por ambiente» y «Costo total» (con total).
- **Columnas:** las actividades del catálogo de cada etapa, no las de
  TARIFAS. La plantilla la arma el servidor y no conoce TARIFAS, que vive en
  el navegador; una actividad nueva del catálogo llega con «Actualizar a la
  plantilla vigente» o se agrega en una columna libre.
- **Grises:** por módulo, los módulos de la tipología con esa actividad
  efectiva (columna nueva «Actividad efectiva (calc.)» en MODULOS: la escrita o
  la del catálogo por método de unión o tipo especial, con la clave
  `construction_sheet_key` de la actividad); por ML, los ML del grupo según
  los anchos de MODULOS, si no MUEBLES y si no TIPOLOGIAS.
- **Envío:** el servidor recibe los valores calculados de la matriz y arma
  ACTIVIDADES con las celdas escritas y las de ML (`merge_matrix`). Las de
  módulo **no van**: «Generar plan» ya saca el armado por módulo de MODULOS y
  se duplicaría. El importador y «Generar plan» no cambian.
- **Pegado (D1):** un complemento de la hoja rechaza el pegado sobre celdas
  grises, filas de cabecera y columnas calculadas de la matriz, con aviso.
- **Hojas existentes:** «Actualizar a la plantilla vigente» (plantilla 5)
  pasa las filas de ACTIVIDADES a las celdas escritas (las de otra columna, a
  una libre de su etapa) y, en una hoja que ya tiene la matriz, conserva lo
  escrito por el código de cada columna.
- **Pendiente:** «Importar Excel a la hoja» con una pestaña ACTIVIDADES la
  escribe en la pestaña oculta y no en la matriz; con la matriz, esas filas
  no llegan al envío. Se resuelve con el mismo paso de «Actualizar a la
  plantilla vigente» si Vicente lo pide.
- INICIO: el control «TARIFAS tiene cada actividad» y el indicador
  «Contratas» leen la matriz (incluye el armado por módulo, que antes no
  sumaba).

## 6. Entrega 3 · M119-01 Presupuesto de mano de obra

- Núcleo: «Rendimiento inicial (por persona-día)» en el catálogo; modelo
  `construction.project.productivity` (obra, actividad, sub etapa, unidad,
  rendimiento, origen, motivo, fecha, usuario); modelo
  `construction.labor.budget` por obra y sub etapa, con sus semanas; el cálculo
  (días equivalentes, personas con banda, rendimiento exigido, metas, soles).
- Hoja: sección «Rendimientos» y «Banda del rendimiento» en PARAMETROS;
  bloques «Presupuesto de mano de obra» y «Metas por semana» en PROGRAMA, con
  inicio y fin ajustados y su motivo.
- Envío: escribe la tabla de rendimientos y el presupuesto de la obra.
- «Generar plan»: líneas de personal propio con costo jornal ÷ rendimiento
  exigido (D3) y persona-días en toda línea de mano de obra.
- «Asignar cuadrilla»: propone las personas del presupuesto y avisa la
  diferencia sin bloquear.

## 7. Entrega 4 · M119-02 Control semanal

Informe `construction.labor.weekly.control` (vista SQL o modelo recalculado por
la acción programada de los jornales) por obra, sub etapa, modalidad, contrata
y semana, con avisos «Exceso de personal», «Atraso» y «Sobre el presupuesto», la
primera semana sobre el presupuesto y la acción «Usar como rendimiento medido».

## 8. Entrega 5 · M119-05 Tablero

Acción de cliente OWL en `al_construction_attendance`, con un método de servidor
que entrega por obra y período los pisos, sus sub etapas, los cuatro
indicadores y la radiografía. Acceso: «Ejecuta» o «jefatura de proyectos», solo
obras con acceso; soles con «Ve montos»; oculto con el control activo apagado.
