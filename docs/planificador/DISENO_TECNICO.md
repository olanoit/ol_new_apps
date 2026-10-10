# Planificación de obra — diseño técnico

Módulo `al_construction_planner` (área `OL-PROJECTS`). Fuente de verdad
funcional: [`ESPECIFICACION_v1.4.md`](ESPECIFICACION_v1.4.md). Este documento
traduce la especificación a Odoo 19 con lo que ya existe en la suite y en los
módulos oficiales, fija los nombres técnicos y ordena el trabajo por fases.

Fecha: 10/10/2026. Base de desarrollo y pruebas: `ol_pe_v19`.

## 1. Análisis de lo existente (con evidencia)

Rutas relativas a `~/odoo/ce19`. `OLP` = `myodoo/ol_new_apps/OL-PROJECTS`.

### 1.1 Gantt de la suite

| Hallazgo | Evidencia | Uso en el planificador |
|---|---|---|
| Capa de datos heredable: `al.gantt.data.get_data(project_ids, options)` devuelve tareas, vínculos y metadatos ya normalizados | `OLP/al_project_gantt_base/models/gantt_data.py:49`, `:184` | Fase 8: heredar `get_data` para añadir la columna de selección, las etapas y la carga de recursos |
| Entrada RPC del proyecto | `OLP/al_project_gantt_base/models/project_project.py:35` (`get_gantt_data`) | Abrir el cronograma desde el nodo elegido |
| Mapeo de campos configurable `al.gantt.field.map.get_map()` → `date_start`, `date_end`, `progress` | `OLP/al_project_gantt_base/models/gantt_field_map.py:46`, `:83` | **Fase 1**: la fecha de necesidad de la línea usa `get_map()['date_start']` de su tarea (`construction_resource_plan.py`, `_compute_date_needed`) |
| Línea base del Gantt | `gantt_baseline.py:19`, `:66` | Comparar el plan aprobado contra la ejecución (fase 8) |
| dhtmlxGantt **v10.0.0 MIT edition**; la vista de recursos es de la edición Pro | cabecera de `OLP/al_project_gantt_base/static/lib/dhtmlx/dhtmlxgantt.js` («A Pro version … resource management … is available») | La carga de recursos de P-15 será una **tabla OWL propia** bajo el diagrama, como prevé la especificación |

### 1.2 Requerimiento de materiales de obra (`al_construction_material_request`)

| Hallazgo | Evidencia | Uso |
|---|---|---|
| Documento con aprobación por niveles: `_inherit = [..., 'tier.validation']` | `OLP/al_construction_material_request/models/construction_material_request.py:25` | El plan de recursos usará el mismo patrón para su aprobación (fase 2) |
| Gancho de envío: `_check_ready_to_submit()` y `action_request_approval()`; aprobación final en `_write_approved()` | mismo archivo `:164`, `:177`, `:188` | Fase 3: control de exceso sobre el plan al enviar el requerimiento (`exceed_policy` del plan: avisar, pedir aprobación o bloquear) |
| Línea con `task_id`, `supply_mode` (central/directo), `qty_to_dispatch`, `qty_to_purchase`, `line_state` | `.../construction_material_request_line.py:47`, `:51`, `:64`, `:66`, `:74` | Fase 3: las columnas nuevas de P-07 (planificado, pedido, saldo) y el consumo de la línea del plan salen de estas cantidades |
| Proyecto marcado como obra: `is_construction_site` y su ubicación | `.../project_project.py:9`, `:12` | **Fase 1**: dominio de la obra en tipologías y planes; el menú «Obras» reutiliza `action_construction_sites` |
| Licencia LGPL-3 por depender de `base_tier_validation` (AGPL-3) | `scripts/areas.py` (`LICENSE_EXCEPTIONS`) | El planificador también es **LGPL-3** (excepción añadida en `scripts/areas.py`) |

### 1.3 Módulos OCA

| Módulo | Evidencia | Uso |
|---|---|---|
| `purchase_request` (copia local, no se modifica ni se commitea) | `OL-THIRD-PARTY/purchase_request/models/purchase_request.py:18` | Fase 3: lo que el requerimiento manda a compras ya viene del módulo de requerimientos |
| `base_tier_validation` (`tier.definition`) | `OL-THIRD-PARTY/base_tier_validation/models/tier_definition.py` | Fase 2: reglas de aprobación del plan y de las liquidaciones |

### 1.4 Módulos oficiales

| Módulo | Evidencia | Decisión |
|---|---|---|
| `account_budget`: `budget.line` hereda `analytic.plan.fields.mixin`; `budget_analytic_id`, `budget_amount` | `ee19/account_budget/models/budget_line.py:12`, `:18`, `:22` | El plan guarda `budget_analytic_id` (fase 1, campo); la fase 7 crea las líneas del presupuesto por etapa/tipo con la cuenta analítica de la obra |
| Columnas analíticas por plan: `account_id` para el plan de proyectos, `x_plan<N>_id` para los demás | `addons/analytic/models/analytic_plan.py:118` | Las líneas del plan heredan `analytic.mixin` (`analytic_distribution` JSON) y no crean columnas `x_plan` propias |
| `planning.slot`: `role_id`, `allocated_hours`; **sin tarea** | `ee19/planning/models/planning_slot.py:58`, `:89` | Personal propio (fase 5): el turno se crea por rol y horas; la tarea se enlaza desde la línea del plan, no desde el turno |
| `project_forecast` añade `project_id` al turno, no la tarea | `ee19/project_forecast/models/planning_slot.py:12` | Igual que arriba: la línea del plan guarda `role_id` y el turno |
| `mrp.production`: `action_confirm`, `_post_inventory`, `button_mark_done` | `addons/mrp/models/mrp_production.py:1625`, `:1907`, `:2219` | Fase 6: OF por ambiente desde la BOM de la tipología; consumos para el real del plan |
| `project_mrp`: `project_id` en la OF (calculado desde la BOM) | `addons/project_mrp/models/mrp_production.py:9`, `:12` | La OF queda en la obra sin campo propio |
| `hr_timesheet`: `progress` = horas registradas / asignadas | `addons/hr_timesheet/models/project_task.py:42`, `:95` | No sirve como avance por driver: el avance de contratas es un modelo propio (fase 4) |
| `sale_management` | instalado en `ol_pe_v19` | Fase 7: una línea de OV por partida (familia) con su precio; el ingreso devengado = precio × Δ avance |
| Planilla de construcción civil: `l10n_pe.hr.construction.site` | `myodoo/ol_new_apps/OL-PAYROLL/al_hr_pe_construction/models/hr_construction_cost.py:13` | Riesgo: dos nociones de «obra» (proyecto y obra de planilla). Fase 5: enlazar el proyecto con la obra de planilla en lugar de duplicarla |

## 2. Nombres técnicos

### 2.1 Convenciones

- Sin prefijo `x_` (es el de Studio). Campos nuevos en modelos de Odoo con
  prefijo `construction_`; modelos nuevos `construction.*`.
- Etiquetas en español, solo primera mayúscula; contadores con «Nº de …» para
  no repetir la etiqueta del one2many.
- Botones `action_<verbo>`; asistentes `construction.<objeto>.<verbo>.wizard`.
- Versión `N.AAAAMMDD` (`1.20261010`); categoría `OL-PROJECTS/Apps`.

### 2.2 Equivalencias especificación → módulo

| Especificación | Módulo | Modelo |
|---|---|---|
| `x_level` | `construction_level` | `project.task` |
| `x_floor_task_id` / `x_apartment_task_id` / `x_space_task_id` | `construction_floor_task_id` / `construction_apartment_task_id` / `construction_space_task_id` | `project.task` (calculados, almacenados, recursivos) |
| `x_typology_id` | `construction_typology_id` | `project.task` |
| `x_module_code` / `x_module_type` / `x_width_mm` / `x_ml_group` | `construction_module_code` / `construction_module_type` / `construction_width_mm` / `construction_ml_group` | `project.task` |
| `x_unit_state` | `construction_unit_state` | `project.task` (con seguimiento) |
| `x_plan_amount` | `construction_plan_amount` | `project.task` (no almacenado) |
| `x_consumption_stage` | `construction_consumption_stage` | `mrp.bom.line` |
| `x_resource_plan_id` / `x_plan_line_id` (en documentos de fases 3+) | `construction_plan_id` / `construction_plan_line_id` | requerimiento, OC, OF, turnos |
| `construction.resource.plan` · `construction.resource.plan.line` | igual | nuevos |
| `construction.typology` · `.module` · `.activity` | igual | nuevos |
| `construction.labor.activity` · `construction.labor.rate` | igual | nuevos |
| Líneas: `floor/apartment/space/module_task_id` | igual (en la línea, sin prefijo) | `construction.resource.plan.line` |

## 3. Estructura del módulo

```
al_construction_planner/
├── __manifest__.py           1.20261010 · LGPL-3 · OL-PROJECTS/Apps
├── data/ir_sequence_data.xml PLR/%(year)s/#####
├── i18n/es.po                campos heredados de mail/analytic en español
├── models/
│   ├── common.py             LEVELS, STAGES, RESOURCE_TYPES, MODULE_TYPES…
│   ├── construction_labor.py actividades y tarifas (_get_rate)
│   ├── construction_typology.py
│   ├── construction_resource_plan.py
│   ├── project_task.py · project_project.py · mrp_bom_line.py
├── wizards/plan_generate_wizard.py (+ vista)  W-01 / P-04
├── security/                 privilegio, grupos, ACL, reglas por compañía
├── views/                    P-12, P-14, plan, líneas, árbol, menús
├── static/description/       icon.png propio, index.html (ficha), diagramas
├── tests/                    22 tests
└── tools/planner_demo_data.py  DEMO PLAN · piso 05
```

Dependencias: `al_project_gantt_base`, `al_project_gantt_backend`,
`al_construction_material_request`, `purchase_request`, `base_tier_validation`,
`project_mrp`, `project_forecast`, `hr_timesheet`, `account_budget`,
`sale_management`. Se declaran todas desde la fase 1 para que el árbol de
dependencias no cambie entre fases (instalarlo en `ol_pe_v19` añadió `mrp`,
`project_mrp`, `project_forecast`, `hr_timesheet`, `account_budget`).

## 4. Grupos y menús

Privilegio **Planificación de obra** (`res.groups.privilege`, categoría Servicios):

| Grupo | Implica | Quién | Fase 1 |
|---|---|---|---|
| Reporte de avance | Usuario interno | Capataces y supervisores | Lectura del plan, tipologías y actividades |
| Usuario | Reporte de avance, Proyecto: usuario | Proyectos, Logística, Producción | + lectura de tarifas |
| Planificador | Usuario, Fabricación: usuario | Oficina Técnica | Tipologías, planes, líneas, asistente |
| Administrador | Planificador | Jefatura de Proyectos | + actividades y tarifas; root y admin |
| Planificación de obra: ingresos (fuera del privilegio) | Usuario | Administración y Finanzas | Sin permisos propios aún (fase 7) |

Menú raíz **Planificación de obra** (ícono propio: edificio de pisos con las
barras de su plan, carmesí `#BE123C`, trazo blanco; generado con
`icons/make_icons.py` del scratchpad):

- Obras ▸ Planes de recursos (P-01 básica) · Árbol de recursos (P-02) · Tareas de la obra · Recursos planificados · Obras
- Configuración ▸ Tipologías (P-12) · Actividades de obra (P-14) · Tarifas de contrata (P-14)

Multicompañía: `_check_company_auto` y `check_company=True` en todas las
relaciones; reglas `company_id in company_ids` (las actividades admiten
compañía vacía = compartidas); compañía de solo lectura en vistas. El plan y la
tipología toman la compañía de la obra o, si la obra es compartida entre
compañías (`project.company_id` vacío, posible en v19), la activa al crearlos.
Control `al_base_module_info` (TestMulticompany) en verde para este módulo.

## 5. Decisiones tomadas

1. **Costo de los materiales.** La especificación dice «el costo lo escribe el
   planificador, sin valor por defecto» pero muestra totales en P-04. Se
   resolvió así: las contratas llevan la tarifa vigente (la especificación la
   da como referencia) y los materiales salen en 0 con la advertencia «líneas
   sin costo». Al regenerar se conserva el costo ya escrito por producto o
   actividad. El demo aplica el costo después de generar (simula W-12, fase 2).
2. **Versiones.** «Una sola versión no reemplazada ni cancelada» chocaba con
   preparar la versión siguiente mientras la vigente se ejecuta. Se exige: una
   vigente (aprobada o en ejecución) y una en preparación (borrador o en
   aprobación) por obra.
3. **Edición.** Las líneas solo cambian en borrador, salvo la fecha de
   necesidad y el estado de la línea (los mueven otros documentos). El
   contexto `construction_plan_force` lo salta para procesos internos.
4. **Acumulación sin recursión.** Cada línea guarda sus cuatro ancestros
   (almacenados); el monto de un nodo es un `_read_group` por el ancestro de
   su nivel sobre el plan vigente (o el borrador si no hay vigente).
5. **ML en el módulo o en el ambiente.** Con anchos por módulo, las
   actividades por ML bajan a los módulos de su grupo (cantidad = ancho/1000);
   sin anchos quedan en el ambiente con la cantidad de la tipología y se avisa.
6. **Módulos existentes.** Si el ambiente ya tiene módulos (ETO), se emparejan
   por código; los de la plantilla que faltan se avisan y no se generan.
7. **Materiales sin etapa** se generan (para que se vean) y se avisan; la
   aprobación (fase 2) se bloqueará mientras existan.
8. **Compañía de la actividad**: la activa por defecto; vacía (compartida)
   solo por importación, porque la compañía es de solo lectura en las vistas.

## 6. Plan de fases

| Fase | Contenido | Pantallas |
|---|---|---|
| **1 (hecha)** | Jerarquía, catálogo, plan y generación | P-01 básica, P-04, P-12, P-14 |
| 2 (hecha) | Árbol del plan OWL con selección en cascada y carga por niveles | P-02 |
| Línea base (hecha; fase 3 de la especificación) | Aprobación con tier validation y bloqueo por líneas sin etapa/costo/actividad; presupuesto analítico por combinación de cuentas (ver §6.1); resumen por etapa; W-12 aplicar costo (manual, último precio, ponderado 3 y 6 meses); W-09 nueva versión (todo o solo saldos, `previous_line_id`); cierre | P-03, W-09, W-12 |
| Asignaciones y compras (hecha; fase 4 de la especificación) | Modelo de asignación; pedido/comprado/despachado/consumido/saldo y estado de la línea; W-02 compra masiva en dos modos; W-03 requerimiento de obra con saldo y control de exceso (W-10, revisión adicional); W-04 OF desde la BOM con control al confirmar (ver §6.2) | P-10, P-11 |
| 3 | ~~Requerimientos desde la selección~~: hecho en la fase 4 (el control va en `action_request_approval`, no en `_check_ready_to_submit`, que también corre al procesar) | P-07 |
| Contratas (hecha; fase 5 de la especificación) | W-05 asignar contrata con OC de servicio por contrata y obra; avance por driver con fotos (AVN), W-07 y avances por validar; ejecutado y avance de líneas y nodos; estado del módulo; semana de la obra (ver §6.3) | P-05, P-06, P-07, P-09 |
| Liquidación semanal (hecha; fase 6 de la especificación) | LIQ por contrata, obra y semana; acción programada; aprobación por niveles; recepción en la OC y factura con vencimiento el día de pago; «Pagada» (ver §6.3) | P-08 |
| Control y personal propio (hecha; fase 7 de la especificación) | OC con analítica contra el presupuesto de la combinación (W-10); estado y montos de control almacenados con eventos; análisis de control; W-06 cuadrillas con turnos y horas; W-08 cambiar fechas con aviso a Logística; reversión del estado del módulo (ver §6.4) | P-13, W-06, W-08 |
| 6 | Producción: estados del módulo (la OF por piso desde la BOM ya está en la fase 4) | P-10 |
| 7 | OV por partida, valorizaciones e ingreso devengado, factura de la valorización con control de saldo, flujo | P-20, P-21, P-22 |
| Cronograma con recursos (hecha; fase 8 de la especificación) | Etapas del ambiente; herencia de `al.gantt.data.get_data`; pantalla sobre el componente del Gantt con selección, panel, acciones y carga semanal OWL; arrastre con recálculo y aviso (ver §6.5) | P-15 |

### 6.1 Línea base: presupuesto y ganchos

- Presupuesto: `construction.resource.plan._get_budget_line_values()`. Cada
  clave de `analytic_distribution` («id1,id2») se reparte en sus cuentas y
  cada cuenta va a `account.analytic.plan._column_name()` de su plan raíz
  (`account_id` = plan de proyectos; `x_plan<N>_id` los demás). Una
  `budget.line` por combinación; distribución vacía = cuenta de la obra al
  100 %. En `ol_pe_v19`: `x_plan6_id` DEMO TC Centros, `x_plan31_id` DEMO RQO
  Disciplina, `x_plan32_id` DEMO RQO Partida, `x_plan141_id` DEMO Centros de
  costo.
- Versión anterior: su `budget.analytic` pasa a `revised` (padre del nuevo),
  porque `budget.analytic` no tiene `active`.
- Ganchos de las fases 4-6: `_transfer_to_new_version(new_plan)`,
  `line._get_line_execution()` (comprometido, real),
  `line._get_consumed_qty()` (solo saldos), `_mark_in_progress()` y
  `action_close()` (control de asignaciones abiertas y liquidaciones). La
  fase 4 los llena para las asignaciones (§6.2); las contratas (fase 5)
  agregan avances y liquidaciones.

### 6.2 Asignaciones y compras (fase 4)

- `construction.resource.plan.allocation`: `kind` + un solo documento
  (`CHECK num_nonnulls(...) = 1`); `qty_allocated` en la unidad de la línea.
  `qty_done`, comprado, despachado y consumido no se almacenan: se reparten
  por `date_needed` entre las asignaciones del mismo documento (la OF, por
  componente); el sobrante va a la última. `state` sigue al documento.
- Fuentes: compra masiva → comprado = lo asignado mientras el PR no se
  cancele (la especificación pide que suba al crearla, P-10), ejecutado = OC
  confirmadas; requerimiento → comprado = `qty_purchased` de su línea,
  despachado = `qty_received_on_site` (incluye la entrega directa); OF →
  despachado = consumido = componentes hechos; consumo en obra =
  movimientos hechos de la ubicación de la obra (y sus hijas) a una ubicación
  de uso `production` menos las devoluciones, por obra y producto. En
  `ol_pe_v19` no hay tipo de operación «CON»: se mide por ubicación.
- Línea: `qty_requested` excluye la compra masiva (comprar no es pedir a la
  obra); `line_state` deja de ser un campo almacenado y se calcula.
- Requerimiento de obra: sin cambios en `al_construction_material_request`.
  El control se hereda en `action_request_approval` (el estado `draft` se
  comprueba antes; `_check_ready_to_submit` también corre al procesar). Las
  asignaciones se reparten antes de pedir las revisiones; la regla de
  aprobación por exceso es un `tier.definition` de datos con dominio sobre
  `construction_exceed_state` y la política del plan.
- OF: `action_confirm` sincroniza y controla con `sudo` (la planta no ve el
  plan). Solo los componentes de producción y armado (por la etapa de la
  línea de BOM) se asignan; instalación y acabado van por requerimiento.
- Nombres: `x_resource_plan_id` → `construction_plan_id`; `x_exceed_state` /
  `x_exceed_reason` → `construction_exceed_state` / `construction_exceed_reason`;
  `x_allocation_ids` → `construction_allocation_ids`; `x_plan_remaining` /
  `x_out_of_plan` → `construction_plan_remaining` / `construction_out_of_plan`;
  `x_plan_mode` → `construction_plan_mode`; `x_space_task_ids` →
  `construction_space_task_ids`; `x_task_id` / `x_plan_line_id` (turno) →
  `construction_task_id` / `construction_plan_line_id`.

### 6.3 Contratas y liquidación semanal (fases 5 y 6)

- Modelos nuevos: `construction.task.progress` (AVN), `construction.contract.settlement`
  (LIQ, `tier.validation` con `_state_from = ['validated']`) y su línea;
  asistentes `construction.plan.contract.wizard` (W-05),
  `construction.plan.progress.wizard` (W-07) y `construction.reason.wizard`
  (motivo de rechazo y devolución).
- Nombres: `x_is_service_order` → `construction_is_service_order`; la obra de
  la OC, `construction_project_id` (sin depender de `project_purchase`);
  `x_settlement_ids` → `construction_settlement_ids`; `x_week_start_day` /
  `x_settlement_day` / `x_payment_day` → `construction_week_start_day` /
  `construction_settlement_day` / `construction_payment_day` (proyecto,
  calculados desde la compañía y editables); `x_progress_pct` /
  `x_progress_ids` → `construction_progress_pct` / `construction_progress_ids`.
  Línea de la OC: `construction_activity_id`, `construction_retention_pct`.
- La OC de servicio «abierta» es la no anulada ni bloqueada (`locked`). Si
  la compañía bloquea las OC confirmadas, cada asignación nueva abre otra OC.
- La línea de la liquidación se enlaza con la línea de la OC por la
  asignación `service_order` de la línea del plan del avance (no por la
  actividad): una actividad con dos tarifas da dos líneas.
- Avance de nodos: el avance guarda su valor (`amount` = unidades × costo
  unitario de la línea) y los ancestros de su línea; el nodo es un
  `_read_group` por ancestro sobre los validados entre el monto planificado de
  contrata y personal propio. Personal propio con unidad de horas: horas de
  la hoja de horas (empleados con el rol de la línea), sumadas en Python.
- Feriados: ausencias globales (sin recurso) de la compañía en cualquiera de
  sus calendarios (en `ol_pe_v19` los feriados están en un calendario aparte
  del de la compañía); los días sin horario no son feriado (el sábado de
  pago no se mueve por estar fuera del horario de lunes a viernes).
- Factura: `_prepare_invoice` de la OC y `_prepare_account_move_line` de cada
  línea con la cantidad de la semana; sin plazo de pago para que el
  vencimiento sea el día de pago. Retención en la factura solo con la cuenta
  de la compañía (decisión abierta de la especificación sobre el fondo de
  garantía).
- `sudo` justificado en: OC y producto de servicio al asignar, recepción y
  factura al aprobar (jefatura sin permisos de compras ni contabilidad), horas
  de otros empleados, feriados, estado del módulo, sincronización «Pagada».

### 6.4 Control y personal propio (fase 7)

- **Estado y montos almacenados por eventos.** `line_state`,
  `amount_committed`, `amount_actual`, `amount_remaining` y `executed_pct`
  de `construction.resource.plan.line` son almacenados y **sin** `compute`:
  dependen de campos no almacenados de las asignaciones (estado y cantidades
  repartidas, que siguen a compras, inventario y fabricación), de avances,
  turnos y hojas de horas; un `@api.depends` no los dispararía y un
  `store=True` con dependencias incompletas dejaría valores viejos sin aviso.
  `_refresh_control()` (sudo justificado) descarta de la caché esos campos no
  almacenados, recalcula con `_get_line_execution()` / `_get_line_state()` y
  escribe solo lo que cambió, agrupado por valores. Eventos: asignación
  (create/write/unlink, con las del mismo documento), línea (campos de
  `_CONTROL_TRIGGERS`), plan (`state`, `exceed_tolerance`), requerimiento de
  obra (`state`, `action_process`, línea: cancelada/cantidad/unidad), compra
  masiva (`state`, línea), OC (`state`) y su línea (`qty_received`,
  `qty_received_manual`, `product_qty`), OF (`state`),
  `stock.move._action_done` (asignaciones de requerimiento por producto y de
  OF), avance (create, `state`/`qty`/`plan_line_id`/`settlement_id`,
  unlink), turno (horas, fechas, recurso, unlink: la cascada de la base no
  pasa por el ORM y las líneas se leen antes) y hoja de horas (create, write,
  unlink; líneas de personal propio con `task_id parent_of`). Red de
  seguridad: `ir_cron_refresh_plan_control` cada hora (planes vigentes, en
  lotes de 1000) y «Actualizar control». Migración `6.20261010`: cálculo
  inicial. Lo que no cubren los eventos: un `qty_received_on_site` o un
  `line_state` del requerimiento que cambie por un cálculo sin `write` ni
  movimiento hecho (lo recoge la acción programada).
- **P-13.** `plan._get_control_data()` = `_read_group` por etapa y tipo de
  recurso de los montos guardados; `control_html` añade subtotales por etapa,
  total de la obra y % ejecutado (real ÷ planificado, que el pivote no puede
  calcular). Acción `action_construction_plan_control` con pivote y gráfico
  propios (prioridad 20).
- **OC con analítica.** `purchase.order.button_confirm` (no las de servicio):
  `_construction_budget_amounts()` reparte cada línea por su distribución;
  para cada cuenta busca el plan vigente de la obra con esa cuenta
  (`project.account_id`, misma compañía) y la línea de presupuesto que cubre
  la combinación (`plan._construction_match_budget_line`: todas sus columnas
  en la combinación, la más específica; como el informe de presupuesto de
  Odoo). Usado = `budget.line.committed_amount` de `account_budget_purchase`
  (nueva dependencia; `auto_install` con `account_budget` + `purchase`),
  invalidado antes de leer porque no tiene dependencias. Exceso = usado +
  esta OC − presupuesto × (1 + tolerancia). W-10 con `purchase_order_id`
  (concepto, saldo, pedido y exceso en moneda de la compañía). La aprobación
  la confirma la jefatura con `sudo` justificado (no es compradora).
- **Personal propio.** `_get_timesheet_by_employee()` (sudo) agrupa las horas
  por empleado; real = Σ horas × `hourly_cost`; comprometido = Σ por empleado
  de max(horas de turnos de la línea − horas registradas, 0) × costo hora.
  Limitación: dos líneas de personal propio del mismo rol en el mismo nivel
  cuentan las mismas horas.
- **W-06** (`construction.plan.crew.wizard`, hereda la selección del mixin):
  un `planning.slot` por recurso, semana (inicio de semana de la obra,
  08:00-17:00 hora local del usuario de la semana completa) y línea, con
  `allocated_hours` explícitas (repartidas por monto planificado),
  `construction_task_id`, `construction_plan_line_id`, rol y obra. Turnos y
  roles con `sudo` justificado. Asignación `planning_slot`: horas en la
  unidad de la línea si se mide en horas, 0 si se paga por driver;
  `planning.slot.write` la sincroniza con las horas del turno.
- **W-08** (`construction.plan.reschedule.wizard`): con todas las etapas
  desplaza `date_start`/`date_end` del mapa del Gantt de las tareas
  (selección y descendientes) y recalcula `date_needed` con
  `_get_default_date_needed()` para las líneas cuya tarea tiene inicio; con
  algunas etapas solo desplaza `date_needed`. Aviso: actividad «Por hacer»
  en requerimiento de obra, compra masiva u OC abiertos de las líneas cuya
  fecha (`date_required` / `date_planned`) queda antes de la nueva necesidad
  al postergar, o después al adelantar; responsable el comprador de la OC o
  el primer usuario de Logística de la compañía.
- **Estado del módulo.** `construction_unit_state_base` guarda el estado
  previo cuando el avance lo sube por primera vez; `revert=True` (desde
  `action_reset`) baja a max(lo que justifica el avance, ese estado previo).
- **Factura de la valorización (fase 10):** el control «monto confirmado
  menos facturado por partida» queda para el botón «Crear factura» de la
  valorización (modelo aún inexistente). Gancho previsto: un método
  `_construction_check_invoice_balance()` en la valorización, llamado antes de
  `_create_invoices`, con la misma política que los demás documentos.
- **Obra de planilla.** Sin enlace de modelo con
  `l10n_pe.hr.construction.site` (al_hr_pe_construction): exigiría depender
  de la planilla. Se encuentran por la cuenta analítica (la obra de planilla
  lleva `analytic_account_id`; el proyecto, `account_id`). Si se quiere un
  campo, va en un módulo puente.

### 6.5 Cronograma con recursos (fase 8)

- **Etapas.** `construction.space.stage` (ambiente + etapa, única) con
  fechas; pertenece al ambiente, no a la versión del plan, para que el
  cronograma sobreviva a las versiones nuevas. Contrata, cuadrilla, monto y
  avance se calculan en lote desde las líneas del plan vigente. Se crean al
  generar el plan; migración `7.20261010` y botón para los ya generados.
- **Fecha de necesidad.** No cambia su cálculo (inicio de la tarea o del
  plan menos la anticipación): mover una etapa la **desplaza** los mismos
  días en sus líneas, como W-08 con algunas etapas. Así los tests y planes
  anteriores conservan sus fechas.
- **Puntos de extensión del Gantt.** Lo que faltaba se añadió de forma
  genérica (sin referencias al planificador): en `al_project_gantt_backend`
  15.20261010, `transformGanttData`, `extraColumns`, `editorOptions`,
  `onGanttReady`, selección en cascada (`gantt_selection.js`, porque
  `multiselect` es PRO), botones de la barra de selección, `showProjectBar` y
  plantillas de barra, panel lateral y panel inferior; en
  `al_project_gantt_base` 17.20261010, la opción `canDragRow` del editor
  (antes solo se arrastraban tareas reales). Sin heredar, el Gantt queda
  igual (tests de la suite Gantt en verde).
- **Ids de fila.** En el modo «Etapas» las tareas pasan a `t<id>` y las
  etapas a `s<id>`: el editor del Gantt ignora las filas que no son tareas,
  así que no intenta guardar las barras resumen ni las etapas; la pantalla
  guarda el arrastre de las etapas con su propio `onAfterTaskUpdate`.
- **Carga semanal.** Tabla OWL (la vista de recursos de dhtmlxGantt es PRO):
  líneas de contrata y personal propio por contrata (o rol) y etapa,
  repartidas en partes iguales entre los días hábiles de la etapa del
  ambiente y sumadas por semana calendario.

## 7. Riesgos y pendientes

- **Volumen.** MOMEN: 1,589 tareas y ~7,800 líneas. Los ancestros almacenados
  e indexados evitan recursión; el árbol OWL carga por niveles. Medido con
  `tools/planner_tree_benchmark.py` (20 pisos, 153 departamentos, 1,257
  módulos, 7,800 líneas): cada nivel del árbol responde en 8-25 ms y el
  resumen de la selección en 31-65 ms (servidor, sin red).
  El recálculo de ancestros al mover un departamento recorre sus descendientes
  (recursivo almacenado): aceptable, pero conviene medirlo con el volumen real.
- **Precisión de cantidades.** `ol_pe_v19` tiene «Product Unit» = 2 decimales:
  la BOM guarda 1.9591 como 1.96. Si el maestro necesita 4 decimales, subir la
  precisión (decisión de configuración del cliente).
- **59 vs 64 líneas de instalación (P-05).** El demo genera 8 actividades en
  los 8 ambientes (64 líneas); el maestro tiene 59 porque algunas tipologías no
  tienen todas las actividades. Los montos cuadran (S/ 941.17).
- **Dos «obras»** (proyecto y `l10n_pe.hr.construction.site` de planilla):
  se encuentran por la cuenta analítica (§6.4); un campo de enlace iría en un
  módulo puente.
- **Siguiente**: entregas, valorizaciones e ingresos (con la factura de la
  valorización y su control de saldo) y cronograma valorizado (P-22), que
  reparte el plan con las fechas de `construction.space.stage`.
- **Cronograma**: los pisos y departamentos con fechas propias muestran en el
  modo «Etapas» el resumen de sus etapas, no sus fechas; para editar las
  tareas se usa el modo «Tareas» o el Gantt de proyectos. El arrastre de
  etapas exige permiso de escritura en las tareas del proyecto (activa la
  edición del Gantt).
- **Control por eventos**: un cambio que no pasa por los ganchos de §6.4
  espera a la acción programada horaria.
- **Retención y fondo de garantía**: sin cuenta configurada la factura va por
  el bruto; falta acordar con contabilidad el tratamiento.
- **Secuencia**: los tests consumen números de la secuencia `PLR` en bases de
  desarrollo (comportamiento normal de `ir.sequence` estándar).
- **Control multicompañía** de `al_base_module_info`: en verde (10/10/2026,
  con la fase 7).
