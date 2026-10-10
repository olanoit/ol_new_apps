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

- Obras ▸ Planes de recursos (P-01 básica) · Árbol de la obra · Recursos planificados · Obras
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
| 2 | Árbol del plan OWL con selección en cascada y carga por niveles; resumen por etapa; W-12 aplicar costo (última compra, promedio ponderado, maestro); aprobación con tier validation y bloqueo por líneas sin etapa/costo; replanificación (copia a versión nueva, `previous_line_id`) | P-02, P-03, W-12 |
| 3 | Requerimientos desde la selección: columnas planificado/pedido/saldo y control de exceso en `_check_ready_to_submit` del requerimiento | P-07 |
| 4 | Contratas: asignar contrata (OC de servicio por contrata y obra), avances por driver con foto, liquidación semanal con retención | P-05, P-06, P-08 |
| 5 | Personal propio: turnos de planificación por rol, horas; enlace con la obra de planilla | P-09 |
| 6 | Producción: OF por ambiente desde la BOM de la tipología, estados del módulo | P-10 |
| 7 | Presupuesto analítico, OV por partida, valorizaciones e ingreso devengado, flujo | P-11, P-13 |
| 8 | Cronograma con recursos: heredar `al.gantt.data.get_data`, panel y carga semanal OWL | P-15 |

## 7. Riesgos y pendientes

- **Volumen.** MOMEN: 1,589 tareas y ~7,800 líneas. Los ancestros almacenados
  e indexados evitan recursión; el árbol OWL (fase 2) debe cargar por niveles.
  El recálculo de ancestros al mover un departamento recorre sus descendientes
  (recursivo almacenado): aceptable, pero conviene medirlo con el volumen real.
- **Precisión de cantidades.** `ol_pe_v19` tiene «Product Unit» = 2 decimales:
  la BOM guarda 1.9591 como 1.96. Si el maestro necesita 4 decimales, subir la
  precisión (decisión de configuración del cliente).
- **59 vs 64 líneas de instalación (P-05).** El demo genera 8 actividades en
  los 8 ambientes (64 líneas); el maestro tiene 59 porque algunas tipologías no
  tienen todas las actividades. Los montos cuadran (S/ 941.17).
- **Dos «obras»** (proyecto y `l10n_pe.hr.construction.site` de planilla):
  decidir el enlace en la fase 5.
- **Secuencia**: los tests consumen números de la secuencia `PLR` en bases de
  desarrollo (comportamiento normal de `ir.sequence` estándar).
- **Control multicompañía** de `al_base_module_info`: falla hoy por
  `l10n_pe.hr.shift.cycle.assignment.template_id` (módulo de planillas, ajeno
  a este trabajo).
