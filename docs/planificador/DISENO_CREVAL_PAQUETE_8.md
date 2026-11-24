# Diseño del paquete 8 de CREVAL · correcciones de la carga de un presupuesto completo

Fuente: «Requerimiento · paquete CREVAL 8» versión 2 (24-nov-2026), CR-66 a
CR-72.
Las cifras y los nombres de la corrida no se copian: el repositorio es público.
Manda `ARQUITECTURA_COMUN.md` en lo común.

## 1. Revisión de configuración

El requerimiento trae su tabla «Revisión de configuración y alternativas
descartadas». Al programar se volvió a revisar cada punto y ninguno tiene una
ruta nativa ni configurable:

- CR-66: el servicio «Crea una obra» solo sirve si la obra nace al confirmar;
  aquí la obra existe antes.
- CR-67 y CR-68: las fechas las escribe el envío del libro; no hay opción.
- CR-69: «Traer la venta» no escribe títulos.
- CR-70: el modelo de las etapas, la selección de la tarea y el asistente no
  leían la plantilla.
- CR-71: un valor por defecto del usuario no cambia el dominio del campo.
- CR-72: es código.

## 2. Ubicación (ARQUITECTURA_COMUN, sección 4)

| Código | Capa | Módulo |
|---|---|---|
| CR-66 | Puente de Ventas, común | `al_construction_planner_sale` |
| CR-67 | Núcleo (ayudas del horario de obra y acumulación de fechas) y puente de Ventas (envío del libro), común | `al_construction_planner`, `al_construction_planner_sale`; lectura del portal en `al_construction_portal` |
| CR-68 | Núcleo (reparto de etapas) y puente de Ventas (envío), común | `al_construction_planner`, `al_construction_planner_sale` |
| CR-69 | Puente de hoja de cálculo, construcción por partidas | `al_construction_planner_spreadsheet` |
| CR-70 | Núcleo y puente de Compras, común | `al_construction_planner`, `al_construction_planner_purchase` |
| CR-71 | Núcleo (mixin de los asistentes del plan), común | `al_construction_planner` y las vistas de los asistentes en sus puentes |
| CR-72 | Puente de hoja de cálculo, común | `al_construction_planner_spreadsheet` |

No hay condiciones por vertical: los nombres salen de la plantilla de niveles,
las etapas del perfil de la obra y las horas del horario de obra de la compañía.

## 3. Entrega 1 · CR-71 y CR-66

### CR-71 · «Asignar contrata» desde el menú y casilla «Toda la obra»

| Qué | Dónde |
|---|---|
| La compañía del asistente es la del plan y, sin plan, la compañía activa (antes era un relacionado del plan: sin plan, el dominio de compañía del campo «Plan» no dejaba pasar ninguno) | `al_construction_planner/wizards/plan_supply_mixin.py` (`_compute_company_id`) |
| Al agregar partidas en «Selección», «Toda la obra» se desmarca; al vaciarla, se marca; al marcar «Toda la obra» con partidas, se quitan | mismo archivo (`_onchange_task_ids_whole_project`, `_onchange_whole_project_selection`) |
| «Selección» se ve siempre (antes solo con «Toda la obra» desmarcada) | vistas de los siete asistentes que heredan el mixin: núcleo, Compras, Contratas, Cuadrillas y Fabricación |

La apertura desde el plan y desde el cronograma no cambia: `default_get` sigue
leyendo la selección del contexto. `_get_selected_tasks` y los cálculos de
líneas, precio y retención no se tocaron.

### CR-66 · Orden de venta del contrato al confirmar

| Qué | Dónde |
|---|---|
| Al confirmar, la obra elegida en «Proyecto» toma la cotización como «Orden de venta del contrato» si no tiene una vigente (una cancelada no cuenta). El cambio queda en el historial de la obra con quien confirmó y «Al confirmar la cotización …» | `al_construction_planner_sale/models/sale_order.py` (`_construction_link_project_order`) |
| Si la obra ya tiene otra orden vigente, no se reemplaza: la orden confirmada deja un aviso con la orden de la obra y dónde cambiarla | mismo método |
| El vínculo va antes del contrato de obra en borrador (CR-44), que no cambia | `action_confirm` (llama a `super()` primero) |

Quien confirma es de Ventas y puede no escribir en la obra: el vínculo se
escribe con `sudo` y el historial conserva al usuario.

## 4. Entrega 2 · CR-67 y CR-68

Las dos comparten el punto de escritura: `_construction_apply_plan_dates` del
envío del libro (`al_construction_planner_sale/wizards/budget_book_wizard.py`).

### CR-67 · Fechas en el horario y la zona horaria de la obra

| Qué | Dónde |
|---|---|
| Día de obra → fecha y hora de la tarea: hora de entrada (o de salida) del horario de obra de la compañía; un día sin horario, 08:00 y 17:00. Zona horaria: la del contacto de la compañía; sin ella, la del usuario | `al_construction_planner/models/construction_site_schedule.py` (`_construction_site_tz`, `_construction_site_datetime`, `DEFAULT_SITE_HOURS`) |
| Fecha y hora de la tarea → día de obra, y límites de un día de obra para buscar tareas | mismo archivo (`_construction_site_date`, `_construction_site_day_bounds`) |
| La acumulación de fechas del cronograma hacia las tareas escribe y lee con esas ayudas | `construction_space_stage.py` (`_rollup_task_dates`) |
| Quien lee el inicio de una tarea como día usa la misma ayuda | `_default_dates`, `construction.resource.plan.line._get_default_date_needed`, `plan_reschedule_wizard._get_reference_date` |
| «Tareas del día» del portal busca en el día de la obra, no en el día UTC | `al_construction_portal/models/resident_service.py` (`_tasks_starting`) |

### CR-68 · Títulos y etapas del cronograma con las fechas de PLAN

| Qué | Dónde |
|---|---|
| Las etapas de cada partida se reparten dentro de su inicio y su fin: en el orden del catálogo, con los días hábiles de la obra en partes iguales. La primera empieza en el inicio y la última termina en el fin, aunque no sean hábiles | `construction.space.stage._fit_to_dates` (núcleo) |
| Las fechas de necesidad de las líneas se mueven con su etapa, sin aviso a Logística (como «Ritmo de programación») | mismo método (`_shift_lines(..., notify=False)`) |
| La partida y sus títulos toman el menor inicio y el mayor fin de lo que tienen debajo, en una sola acumulación | `_construction_apply_plan_dates` → `_rollup_task_dates` |
| Una partida sin receta (sin etapas en el cronograma) recibe las fechas en la tarea y cuenta para su título | `_construction_apply_plan_dates` |
| Con una sola fecha en PLAN, la otra es la que ya tenía la partida | mismo método |
| Línea en el historial del plan: «Fechas de la pestaña PLAN aplicadas: N partidas, M títulos» | mismo método |

Una partida sin fechas en PLAN no entra al reparto: conserva las propuestas.
Las fechas movidas a mano en el cronograma solo cambian si se vuelve a enviar
la hoja con fechas en PLAN para esa partida.

## 5. Entrega 3 · CR-69, CR-70 y CR-72

### CR-69 · Títulos de la venta en la hoja de planificación

| Qué | Dónde |
|---|---|
| Cada título va antes de la primera partida que cuelga de él. Sale de la ruta que cada línea de la cotización guarda desde el envío de la hoja de presupuesto (`construction_budget_path`, todos los niveles con ítem y nombre) | `al_construction_planner_spreadsheet/models/project_project.py` (`_construction_budget_rows`, `_construction_budget_title_rows`) |
| Sin esa ruta (cotización sin hoja de venta), las secciones y subsecciones de la cotización, con el código que da el ítem de la partida | mismo método |
| INICIO › Indicadores: «Títulos», debajo de «Total con IGV» | `_construction_budget_start_sheet` (celdas A21 y B21) |

La fila de título lleva ítem y nombre; unidad, metrado y APU quedan vacíos y el
formato es el condicional de siempre (`PRESUPUESTO_title`). Columnas, claves y
fórmulas no cambian. PLAN sigue con las partidas.

### CR-70 · Nombres de la plantilla de niveles

| Qué | Dónde |
|---|---|
| «Etapas del cronograma» hereda `construction.level.labels.mixin`: columnas, filtros y agrupadores con el nombre de la plantilla; la función que la plantilla no tiene no se muestra | `al_construction_planner/models/construction_space_stage.py` |
| «Nivel de obra» de la tarea: `construction_level_label`, el nombre de la línea de la plantilla sin la marca «(Nn)»; sin plantilla, la selección de siempre | `project_task.py`, `views/project_views.xml` |
| «Agrupar por» del asistente de requerimiento: solo las funciones de la plantilla, con su nombre (`fields_get`); al cambiar de plan, si la elegida no existe en su plantilla, pasa a otra | `al_construction_planner_purchase/wizards/plan_request_wizard.py` |
| La primera columna de las líneas lleva el nombre del nivel elegido: una columna por función sobre la misma tarea, visible según «Agrupar por» | mismo archivo y `plan_supply_wizard_views.xml` |

Las funciones guardadas (`space`, `apartment`, `floor`) y el agrupamiento de
las líneas no cambian.

### CR-72 · El 0 de la hoja se conserva

`documents.document._construction_book` escribía vacío todo valor igual a
`False`, y en Python `0 == False`. Ahora solo el texto vacío, `None` y el
booleano `False` van vacíos.

## 6. Diferencias frente al requerimiento

1. **CR-67, acumulación del cronograma.** El requerimiento pide la hora del
   horario de obra en las escrituras desde la hoja y desde el libro. También
   se aplicó a la acumulación de fechas del cronograma hacia las tareas
   (`_rollup_task_dates`), porque CR-68 hace que esa acumulación reescriba la
   partida y sus títulos: sin el cambio, volvían a las 00:00 UTC. Efecto: en
   cualquier obra (también de mobiliario), la próxima vez que el cronograma
   acumule fechas, las tareas pasan de las 00:00 UTC a la hora de entrada y de
   salida. Los días del cronograma no cambian; la tarea deja de verse un día
   antes.
2. **CR-67, horas por defecto.** Quedó la propuesta del requerimiento, 08:00 y
   17:00 (`DEFAULT_SITE_HOURS`), a falta de la decisión pendiente. También se
   usa en un día sin horario dentro de una compañía con horario de obra (un fin
   escrito en domingo).
3. **CR-67, portal.** La integración decía «sin ajuste». «Tareas del día»
   buscaba en el día UTC; se cambió al día de la obra para que el criterio 2
   se cumpla en cualquier zona horaria.
4. **CR-68, reparto.** «La misma regla de reparto del plan» se programó como
   partes iguales de los días hábiles de la partida entre sus etapas, en el
   orden del catálogo. La regla del plan (una semana por etapa) no cabe en un
   plazo fijo.
5. **CR-69, origen de los títulos.** No se lee el documento de la hoja de
   venta: el servidor no evalúa hojas. Los títulos salen de la ruta que el
   envío de la hoja de presupuesto guarda en cada línea de la cotización, que
   trae todos los niveles. Un título de la hoja de venta sin partidas debajo no
   llega (decisión del 13-nov: los títulos vacíos se excluyen).
6. **CR-69, «Traer de Odoo» en la hoja de venta.** Usa las mismas filas, así que
   también trae los títulos.
7. **CR-69, INICIO.** «Títulos» va en la fila 21, debajo de los cuatro
   indicadores, para no mover celdas que ya se leen. Las hojas ya creadas no lo
   reciben; sí las nuevas.
8. **CR-70, valor por defecto de «Agrupar por».** El requerimiento pide el nivel
   con etapas. Quedó el de hoy (el último agrupador: «Piso» o
   «Sub-especialidad») cuando la plantilla lo tiene, y el nivel con etapas si
   no, porque «Lo que no debe cambiar» incluye el agrupamiento y mobiliario
   «como hoy». Cambiarlo es una línea (`_default_group_by`). **Decisión
   pendiente.**
9. **CR-70, asistente abierto sin plan.** Los nombres de «Agrupar por» salen de
   la plantilla de la obra del plan con que se abre. Abierto desde el menú, sin
   plan, usa la plantilla de la compañía.
10. **CR-71, «Toda la obra».** Además de lo pedido, marcar «Toda la obra» con
    partidas elegidas las quita, para que no quede una selección que se ignora.

## 7. Pruebas

| Código | Prueba |
|---|---|
| CR-66 | `al_construction_planner_suite/tests/test_creval_package8.py`: `test_cr66_*` (comercial sin administrador ni planificador) |
| CR-67 | `test_cr67_*` |
| CR-68 | `test_cr68_*` |
| CR-70 | `test_cr70_*` |
| CR-71 | `test_cr71_*` (incluye «Requerimiento de materiales para obra») |
| CR-69, CR-72 | `al_construction_planner_spreadsheet/tests/test_creval_package8.py` |

Recorridos de pantalla (`TestCrevalPackage8Tours`, con un comercial y un
planificador sin administrador):

| Código | Recorrido | Archivo |
|---|---|---|
| CR-66 | `al_construction_package8_confirm` (confirmar) y `al_construction_package8_contract_order` (obra › «Calendario e ingresos» e historial) | `al_construction_planner_sale/static/tests/tours/package8_contract_order_tour.js` |
| CR-67, CR-68, CR-70 | `al_construction_package8_schedule`: la partida con «Nivel de obra» y sus fechas, y «Etapas del cronograma» | `al_construction_planner/static/tests/tours/package8_schedule_tour.js` |
| CR-70 | `al_construction_package8_request_wizard`: «Agrupar por» y la primera columna | `al_construction_planner_purchase/static/tests/tours/package8_request_wizard_tour.js` |
| CR-71 | `al_construction_package8_contract_wizard`: «Plan» sin pasar por el plan y «Toda la obra» | `al_construction_planner_subcontract/static/tests/tours/package8_contract_wizard_tour.js` |

CR-69 no tiene recorrido: la hoja se comprueba en el servidor (filas, celdas e
INICIO del documento creado y validación del libro con títulos).

## 8. Pendiente

- Capturas en creval-dev por criterio, junto a la maqueta.
- Recorrido de pantalla de CR-69 (abrir la hoja y validar).
- Verificación en creval-dev y en newallcenter-dev1.
- Decisiones: horas por defecto de CR-67 y valor por defecto de «Agrupar por»
  (diferencia 8).
