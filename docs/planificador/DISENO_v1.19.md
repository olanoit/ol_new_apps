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

- **Núcleo** (`construction_labor_budget.py`):
  - `compute_budget`: persona-días necesarios, personas exactas, personas con
    la banda (⌈exactas ÷ (1 + banda)⌉), rendimiento exigido, desviación,
    persona-días presupuestados y soles (propio: persona-días × jornal;
    contrata: cantidad × tarifa). «Capacidad ociosa» bajo rendimiento − banda.
  - `construction.project.productivity`: tabla de rendimientos de la obra
    (origen Inicial, Ajustado o Medido; cambiar pide motivo). Nace con el
    rendimiento inicial del catálogo al enviar la hoja y al generar el plan.
  - `construction.labor.budget` por obra, sub etapa y modalidad, con sus
    actividades (`.line`, D3: costo = jornal ÷ rendimiento exigido de cada
    actividad) y sus semanas de lunes a domingo (`.week`). El jefe de
    proyecto ajusta el plazo en la obra con motivo; las metas se recalculan.
  - Etapa: «Lleva presupuesto de mano de obra» (`labor_budget`), por
    defecto las de campo que no consumen en taller (2.1, 2.2 y 2.3; no 1.2).
  - Línea del plan: «Persona-días».
- **Hoja** (`labor_budget_sheet.py`, plantilla 6):
  - PARAMETROS: «Banda del rendimiento» (10 %) y la sección «Rendimientos»
    (clave `rend:<código>`), con el valor de la obra o del catálogo como
    inicial y el motivo obligatorio si cambia. La columna «Rendimiento» de MO
    PROPIA queda en el libro de carga, pero no cuenta (el importador ya la
    descartaba); el rendimiento se escribe en «Rendimientos». Menú «Traer rendimientos de la obra».
  - `_MO` (oculta): días equivalentes por fecha (del horario de obra, se
    actualiza al abrir la hoja) y una fila por columna de la matriz de las
    sub etapas con presupuesto.
  - PROGRAMA, debajo de la grilla de pisos (aviso en C14 con la fila): un
    bloque por sub etapa y modalidad con plazo de los pisos o ajustado con
    motivo, días equivalentes, personas, rendimiento exigido, presupuesto y
    las metas por semana (meta, persona-días y soles con su acumulado).
    Las columnas de semanas de PROGRAMA son angostas para una tabla aparte.
  - INICIO: paso «Rendimientos» (aviso si una actividad no tiene).
- **Envío:** lee los valores calculados de PARAMETROS, `_MO` y PROGRAMA; al
  importar escribe la tabla de rendimientos y el presupuesto, que el servidor
  recalcula con la misma regla. Un ajuste hecho en la obra se conserva si la
  hoja no trae otro.
- **«Generar plan»:** personal propio a jornal ÷ rendimiento exigido con la
  base anotada; persona-días en toda línea de mano de obra; contrata con su
  tarifa.
- **«Asignar cuadrilla»:** muestra las personas del presupuesto y avisa la
  diferencia en persona-días y soles de las semanas elegidas; no bloquea.
- **Pendiente para la entrega 4:** «Usar como rendimiento medido» (el método
  `_construction_productivity_write(..., origin='measured')` ya existe).

## 7. Entrega 4 · M119-02 Control semanal

- `construction.labor.weekly.control` (`al_construction_attendance`): una fila
  por obra, presupuesto (sub etapa y modalidad), contrata y semana de lunes a
  domingo. Se rehace al abrirlo desde la obra («Control de MO»), con
  «Actualizar el control semanal» y con una acción programada diaria.
- Real: avance validado; persona-días del personal propio = jornales
  ejecutados; de la contrata = horas marcadas ÷ jornada completa del horario
  de obra, repartidas entre los presupuestos que avanzó la semana por lo que
  justifica su avance (D5). Soles reales: propio, persona-días × jornal;
  contrata, avance × tarifa. Semana en curso contra la meta de los días
  transcurridos.
- Avisos con la banda del presupuesto (D9): «Exceso de personal» (rendimiento
  real bajo el exigido − banda), «Atraso» (avance acumulado bajo la meta
  acumulada) y «Sobre el presupuesto» (reales acumulados sobre el
  presupuesto del avance + banda), con la primera semana marcada.
- Sin rendimiento, la fila lo dice y no calcula rendimiento real ni personal
  esperado. Con una sola actividad, «Usar como rendimiento medido» la lleva a
  la tabla de la obra con origen «Medido».
- Vistas: lista con avisos, pivote y gráfico acumulado (presupuesto del
  avance frente a persona-días reales); menú Ejecución › Asistencia.
- Los criterios se cumplen con la cuenta exacta; dos difieren por redondeo
  del requerimiento: la desviación de la segunda semana es −17.24 % (dice
  −17.3 %) y el presupuesto del avance acumulado es S/ 5,380.20 (dice 5,380).
- **Contratas con varias en una sub etapa:** la meta se reparte en partes
  iguales entre las contratas que avanzaron [I].

## 8. Entrega 5 · M119-05 Tablero de instalación

Programado desde el texto del requerimiento: el prototipo interactivo no
llegó (D2). Conviene revisarlo contra él antes de la aceptación.

- Acción de cliente OWL `al_construction_installation_board`
  (`al_construction_attendance`), con el método de servidor
  `construction.installation.board.get_data`. Entradas: botón «Control
  semanal» en la obra y menú Ejecución › «Control semanal de instalación»
  (con selector de obra).
- Período «Desde»/«Hasta» con atajos (una semana, últimas 4, desde el
  inicio) y flechas; por defecto la última semana cerrada; «Desde» mayor que
  «Hasta» mueve «Hasta». Interruptores «Producción» e «Instalación» (siempre
  uno prendido); instalación = sub etapas con presupuesto de mano de obra;
  producción = las demás que no son de control.
- **Semana programada:** el fin de la sub etapa en los ambientes del piso
  en el **Cronograma** (`construction.space.stage`), no un dato nuevo del
  envío de la hoja: el Cronograma ya tiene esas fechas (sección 3 de la
  arquitectura). Semana en que terminó: la del avance que llevó el piso al
  100 %.
- % por piso y sub etapa: cantidad validada ÷ planificada de sus líneas de
  contrata, personal propio o producción en el plan vigente. **Producción
  (D11) queda con esa misma regla**: las órdenes de fabricación por piso no se
  leen todavía.
- Indicadores: pisos del período, pisos atrasados (con la lista), pisos
  terminados (total y por sub etapa) y mano de obra (soles con «Ve montos»,
  persona-días sin él; solo instalación), desde el control semanal.
- Edificio: estados Terminado (con semana y retraso), Atrasado (% y semana
  debida), En curso (semana actual) y Pendiente (semana programada); barra de
  avance y borde en las celdas programadas del período.
- Radiografía a la derecha: por celda, semáforos de plazo, presupuesto
  (persona-días en contrata, soles en propio con «Ve montos») y alcance; quién
  ejecuta, semanas, sub etapa anterior, ambientes y qué falta, con enlace a los
  avances. Por piso: sus sub etapas con sus semáforos y qué falta.
- Curvas pequeñas por sub etapa: pisos que debían terminar y los que
  terminaron, con el período sombreado.
- Permisos: el menú y el botón dependen de la función «Control»; el servidor
  exige «Ejecuta» o «jefatura de proyectos» y el acceso a la obra.

## 9. Correcciones después de la entrega (09-nov)

Vicente aceptó las cinco entregas y ratificó las decisiones de programación
(D3 a D6, D8, columnas de la matriz, armado por módulo, `labor_budget`,
presupuesto por modalidad, meta repartida entre contratas, semana programada
desde el Cronograma). Las diferencias de redondeo de M119-02 son del
documento. Pidió cuatro correcciones antes del paquete 1.18 y envió el
prototipo del tablero.

| # | Corrección | Requerimiento | Estimación |
|---|---|---|---|
| C1 | Banda propia del aviso «Exceso de personal» (parámetro `banda_exceso_personal`, 10 %); reemplaza D9. La banda del rendimiento sigue para las personas, la capacidad ociosa y «Sobre el presupuesto» | M119-01 p. 3; M119-02 p. 2 | 0.5 a 1 día |
| C2 | Tabla de departamentos y muebles en la radiografía del piso, con una columna por sub etapa visible y su pie | M119-05 p. 6 | 0.5 a 1 día |
| C3 | Avance de producción por piso desde las órdenes de fabricación (lo producido repartido entre los ambientes de la orden en su orden; «Sin orden» en gris); reemplaza D11 | M119-05 p. 8 | 1.5 a 2 días |
| C4 | «Importar Excel a la hoja» con ACTIVIDADES llena la matriz, con aviso en ERRORES si no queda columna libre | M119-04 p. 8 | 1 a 1.5 días |
| R5 | Revisión de la entrega 5 contra el prototipo (textos de las celdas, chips de la radiografía, datos de la celda, rótulo del indicador de mano de obra, semanas futuras) | M119-05 | 1 día |

Total: 4.5 a 6.5 días.

Notas de diseño:

- C1: la banda del aviso viaja en el envío y se guarda en el presupuesto
  (`excess_band`); cambiarla en la obra rehace solo los avisos.
- C3: el tablero vive en `al_construction_attendance`, que no depende de
  Fabricación; la lectura de las órdenes se activa si el puente de
  Fabricación está instalado. La planta es el almacén del tipo de operación
  de la orden.
- C4: la importación ocurre en el navegador; el servidor devuelve las celdas
  de la matriz con la misma regla de «Actualizar a la plantilla vigente».

### Hecho (09-nov)

- C1: `construction.labor.budget.excess_band` y el parámetro
  `banda_exceso_personal` de PARAMETROS; el envío escribe las dos bandas (sin
  la fila, la de la obra o 10); cambiarla en la obra rehace el control semanal.
- C2: tabla «Departamentos y muebles del piso» en la radiografía del piso, con
  el pie de hechos por sub etapa; un clic en una marca abre esa sub etapa.
- C3: `_production_progress` lee las órdenes de fabricación de la obra (sus
  ambientes y las etapas de su lista); lo producido (movimientos terminados
  del producto hasta el cierre del período) se reparte entre los ambientes en
  el orden de «Producir»; «Sin orden» no cuenta en los indicadores ni en las
  curvas; la radiografía muestra la planta y enlaza las órdenes.
- C4: el asistente manda la pestaña de la matriz de cada actividad y la hoja
  escribe ACTIVIDADES en la matriz después de TIPOLOGIAS; lo que no ubica va a
  ERRORES como aviso.
- R5: celdas con texto y nota («Terminado · S6 · +1 sem.», «70 % · debía
  S8»), semáforos con valor y nota, datos de la celda y del piso, rótulos de
  los indicadores, estado del período, leyenda y semana en curso, como el
  prototipo. Quedan fuera del prototipo los montos de materiales de
  producción en la radiografía (el presupuesto de mano de obra no los cubre).
