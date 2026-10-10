# Planificación de obra (AL)

Guía funcional: [GUIA_FUNCIONAL.md](GUIA_FUNCIONAL.md)

Planificador de recursos de obra según la especificación v1.4
([`docs/planificador/ESPECIFICACION_v1.4.md`](../../docs/planificador/ESPECIFICACION_v1.4.md)).
Diseño técnico, equivalencias de nombres y plan de fases:
[`docs/planificador/DISENO_TECNICO.md`](../../docs/planificador/DISENO_TECNICO.md).

## Estado

| Fase | Contenido | Estado |
|---|---|---|
| 1 | Jerarquía de la obra, tipologías, actividades y tarifas, etapa de consumo, plan de recursos y «Generar plan» (P-01 básica, P-04, P-12, P-14) | hecha |
| 2 | Árbol del plan OWL (P-02) | hecha |
| 3 | Línea base: aprobación por niveles, presupuesto analítico, resumen por etapa (P-03), aplicar costo (W-12), nueva versión (W-09), cierre | hecha |
| 4 | Asignaciones y compras: asignaciones del plan, ejecución por línea, compra masiva (W-02, P-10), requerimiento de obra con control de plan (W-03, W-10, P-11), OF desde la BOM (W-04) | hecha |
| 5-8 | Contratas, avances y liquidaciones, personal propio, ingresos, cronograma con recursos | pendiente |

## Modelos

- `construction.labor.activity` / `construction.labor.rate`: actividades con su
  driver (und, ML, módulo) y tarifas por obra y contrata. Prioridad: obra y
  contrata › obra › contrata › base › precio de la actividad.
- `construction.typology` (+ `.module`, `.activity`): plantilla de un ambiente.
- `construction.resource.plan` / `.line`: plan por obra con versiones; las
  líneas guardan sus ancestros (piso, departamento, ambiente, módulo) para
  acumular con `_read_group` sin recursión.
- `project.task`: `construction_level` y ancestros `construction_*_task_id`
  (calculados y almacenados), datos del módulo y `construction_unit_state`.
- `mrp.bom.line`: `construction_consumption_stage`.
- `construction.resource.plan.allocation`: qué parte de un documento corresponde
  a cada línea del plan (fase 4).
- Herencias de la fase 4: `construction.material.request` (`construction_plan_id`,
  `construction_exceed_state`, `construction_exceed_reason`) y su línea
  (`construction_allocation_ids`, saldo, fuera de plan, control);
  `purchase.request` (`construction_plan_id`) y su línea
  (`construction_allocation_ids`, `construction_plan_mode`); `mrp.production`
  (`construction_plan_id`, `construction_space_task_ids`, asignaciones, control
  de exceso); `purchase.order` (`construction_plan_id`) y su línea
  (asignaciones); `planning.slot` (`construction_task_id`,
  `construction_plan_line_id`, asignaciones).

## Árbol de recursos (P-02)

Acción de cliente OWL `al_construction_planner.plan_tree`
(`static/src/plan_tree/`), en **Obras ▸ Árbol de recursos** y en el botón
«Árbol de recursos» del plan.

- Carga por niveles: `construction.resource.plan.get_tree_nodes(parent_key,
  filters)` con `'root'` (la obra), `'p'` (pisos) o el id de una tarea. Cada
  nodo trae módulos, ML, material, contrata, total, cantidades de driver y
  estado del módulo; lo acumulado sale de un `_read_group` por el ancestro
  almacenado de la línea (`floor/apartment/space/module_task_id`).
- Selección en cascada (`selection.js`): se guardan solo los nodos marcados
  de más arriba; el servidor los expande con `child_of`
  (`get_selection_summary`). Desmarcar un hijo deja a los padres en parcial.
- Barra de selección: módulos, ambientes, ML y montos, más los botones de los
  asistentes W-02 a W-08 que estén instalados (`get_tree_actions`; reciben
  `construction_selection_keys` y `construction_selection_task_ids` en el
  contexto).
- Panel lateral: recursos de la selección por actividad, producto o rol, con
  driver, acumulado (fase 5), monto y contrata.
- Filtros: etapa, tipo de recurso, estado del módulo y contrata (o «sin
  asignar»); medida en soles, cantidad de driver o avance.
- Permisos: lectura del plan (`check_access`) y reglas de compañía del plan y
  de las tareas.

Rendimiento (`tools/planner_tree_benchmark.py`, 20 pisos, 153 departamentos,
1,257 módulos, 7,800 líneas; mejor de 5, en el servidor):

| RPC | ms |
|---|---|
| `get_tree_nodes('root')` – obra | 19.3 |
| `get_tree_nodes('p')` – 20 pisos | 24.8 |
| `get_tree_nodes(piso)` – departamentos | 15.1 |
| `get_tree_nodes(ambiente)` – módulos | 7.7 |
| `get_tree_nodes('p')` con filtro de material | 22.7 |
| `get_selection_summary` de un piso | 37.2 |
| `get_selection_summary` de 10 pisos | 64.6 |
| `get_selection_summary` de la obra | 39.5 |

## Línea base (fase 3, P-03)

Estados del plan: `draft` › `to_approve` › `approved` › `in_progress` ›
`closed`, más `replaced` y `cancel`.

- **Solicitar aprobación** (`action_request_approval`): bloquea si hay
  líneas sin etapa, sin costo, contratas sin actividad o, con la obra sin
  cuenta analítica, líneas sin distribución (`_get_approval_issues`, mensaje
  con hasta 10 líneas por motivo). Pide las revisiones de
  `base_tier_validation` (`_state_from = draft, to_approve`, `_state_to =
  approved`); sin reglas que apliquen, aprueba directamente. El rechazo
  devuelve a borrador; «Volver a borrador» desde «En aprobación» reinicia las
  revisiones. Reglas en **Configuración ▸ Reglas de aprobación**; ejemplo en
  `demo/planner_demo.xml` (jefatura, y gerencia de operaciones sobre
  S/ 100 000).
- **Última aprobación** (`_write_approved`): crea el `budget.analytic`
  (gasto, fechas del plan, `parent_id` = presupuesto de la versión anterior) y
  lo confirma; congela `amount_budgeted` en las líneas; la versión vigente
  anterior pasa a «Reemplazado» y su presupuesto a «Revisado» (archivado, el
  mecanismo de revisiones de `account_budget`, que no tiene `active`). El
  presupuesto se crea con `sudo()`: quien aprueba no suele tener permisos de
  contabilidad.
- **Mapeo analítico** (`_get_budget_line_values`): cada clave de la
  distribución de la línea («id1,id2,…»; vacía = cuenta de la obra al 100 %)
  se reparte en sus cuentas y cada cuenta va a la columna de su plan raíz
  (`account.analytic.plan._column_name()`): `account_id` para el plan de
  proyectos y `x_plan<N>_id` para los demás. Una línea de presupuesto por
  combinación; el redondeo se ajusta en la combinación mayor para que el
  total cuadre con el plan. En `ol_pe_v19`: `account_id` = Proyecto,
  `x_plan6_id` DEMO TC Centros, `x_plan31_id` DEMO RQO Disciplina,
  `x_plan32_id` DEMO RQO Partida, `x_plan141_id` DEMO Centros de costo.
- **Ganchos** para las fases 4 a 6: `_transfer_to_new_version(new_plan)`
  (asignaciones abiertas y avances no liquidados a las líneas nuevas por
  `previous_line_id`), `line._get_line_execution()` (comprometido y real por
  línea), `line._get_consumed_qty()` (base de «solo saldos») y
  `_mark_in_progress()` (primer documento generado).
- **Nueva versión** (`construction.plan.replan.wizard`, W-09): motivo
  obligatorio, «Copiar todo» o «Solo saldos»; líneas con `source = replan` y
  `previous_line_id`. La vigente sigue en uso hasta aprobar la nueva.
- **Aplicar costo** (`construction.plan.price.wizard`, W-12): desde el plan o
  desde la lista de líneas (un producto). Sugiere el último precio y el
  ponderado de 3 y 6 meses de las compras confirmadas (unidad del producto,
  moneda de la compañía al tipo de cambio de cada compra); escribe
  `price_unit_planned`, `price_basis` y `price_basis_date` en las líneas en
  borrador.
- **Resumen por etapa** (pestaña del plan): material, contrata (incluye
  personal propio), planificado, presupuesto (en una versión en preparación,
  el de la vigente), diferencia, comprometido, real y saldo. «Sin etapa» en
  rojo. **Análisis del plan**: pivote y gráfico de las líneas.
- **Cerrar** (administrador): solo lectura y presupuesto «Hecho». Un plan
  aprobado no se elimina.

## Asignaciones y compras (fase 4, P-10 y P-11)

- **Asignación** (`construction.resource.plan.allocation`): `kind` y
  exactamente un documento (`purchase_request_line_id`,
  `material_request_line_id`, `production_id`, `purchase_line_id`, `slot_id`;
  `CHECK num_nonnulls(...) = 1` y control de tipo). Lo hecho del documento se
  reparte entre sus asignaciones por `date_needed` (cada una hasta lo
  asignado; el sobrante a la última): comprado (compra masiva: lo asignado
  mientras no se cancele; faltante del requerimiento: `qty_purchased` de su
  línea), despachado (`qty_received_on_site` del requerimiento; consumo de la
  OF), consumido (movimientos hechos de la ubicación de la obra a una ubicación
  de consumo, por obra y producto; componentes consumidos de la OF). `state`
  sigue al documento (abierta / hecha / cancelada). No almacenados, con
  `compute_sudo`: el usuario del plan no necesita permisos de compras,
  inventario ni fabricación para verlos.
- **Línea del plan**: `qty_requested` (requerimientos de obra y OF; OC de
  servicio y turnos para contratas y personal; un documento cancelado cuenta
  solo lo hecho), `qty_purchased`, `qty_dispatched`, `qty_consumed`,
  `qty_remaining` (planificado − pedido) y `line_state` calculado: Excedida
  (pedido > planificado + tolerancia), Completa (despachado ≥ planificado; en
  contratas, todo asignado y cerrado), En compra, Parcial, Planificada; Cancelada
  si el plan se canceló. `_get_line_execution`: comprometido = (máx(pedido,
  comprado) − consumido) × costo del plan; real = consumido × costo (contratas:
  tarifa de la OC de servicio).
- **Ganchos de la fase 3 completados**: `_transfer_to_new_version` mueve las
  asignaciones abiertas a la línea nueva (`previous_line_id`) y deja nota de
  las que no continúan; `_get_consumed_qty` = pedido con documentos cerrados
  (base de «solo saldos»); `_mark_in_progress` al crear el primer documento;
  `action_close` se niega con asignaciones abiertas.
- **Saldo** (`models/construction_plan_supply.py`): `_supply_balance`,
  `_supply_split` y `_supply_check` sobre un grupo de líneas, en la unidad del
  producto y sin contar las asignaciones del propio documento.
- **Asistentes** (base `construction.plan.supply.mixin`: lee del contexto la
  selección del árbol `construction_selection_task_ids` /
  `construction_selection_project`, la expande con `child_of`, filtra por
  etapa; exige el plan vigente):
  - `construction.plan.purchase.wizard` (W-02, `action_plan_purchase_wizard`):
    modo con analítica (necesidad completa, distribución de las líneas o la
    cuenta de la obra al 100 %) o stock general (necesidad − libre en el
    destino − entrante); destino, rango de necesidad, agrupar por producto o
    producto y fecha; unidad de compra del proveedor y redondeo hacia arriba
    salvo unidades de medida (m, kg, l, m², m³, h). Crea el `purchase.request`
    en borrador con `construction_plan_mode` y las asignaciones.
  - `construction.plan.request.wizard` (W-03, `action_plan_request_wizard`):
    agrupa por ambiente, departamento o piso (la línea por encima de ese nivel,
    en su propio nivel); planificado, pedido, saldo, disponible en el origen y a
    pedir. Crea el `construction.material.request` en borrador con la tarea del
    grupo en cada línea y asignaciones a las líneas de cada nivel.
  - `construction.plan.production.wizard` (W-04, `action_plan_production_wizard`):
    una OF por piso (o por la selección) y tipología: producto de la tipología ×
    ambientes, BOM de la tipología, planta y fecha; omite los ambientes que ya
    están en una OF del plan. Asigna los componentes de producción y armado
    (por la etapa de la línea de BOM) a las líneas de esas etapas de sus
    ambientes.
  - `construction.plan.exceed.wizard` (W-10): documento, política,
    justificación y tabla saldo / pedido / exceso.
- **Control del requerimiento de obra**: sin tocar
  `al_construction_material_request`, se hereda `action_request_approval`:
  refresca el plan vigente, calcula el exceso por línea (saldo bajo la tarea de
  la línea, tolerancia del plan; sin líneas = fuera de plan), y según
  `exceed_policy` bloquea, abre W-10 (avisar: confirmar; pedir aprobación:
  justificación obligatoria) o sigue; antes de las revisiones reparte cada
  línea entre las líneas del plan (asignaciones). La regla
  `tier_material_request_exceed` (datos, `noupdate`) agrega la revisión del
  grupo administrador del planificador cuando `construction_exceed_state =
  exceeded` y la política es «pedir aprobación»; `_write_approved` lo pasa a
  «Exceso aprobado».
- **Control de la OF**: `mrp.production.action_confirm` sincroniza las
  asignaciones y controla el saldo de producción y armado con la misma
  política; con «pedir aprobación» la confirma el administrador del
  planificador desde W-10.
- Vistas: botones de la cabecera del plan y del árbol (los xmlid de
  `TREE_ACTIONS`), «Asignaciones» en el plan y en la línea, columnas de
  ejecución, menú **Abastecimiento** (requerimientos de obra, requerimientos de
  compra, órdenes de fabricación, asignaciones), columnas «Saldo del plan» y
  «Control» y cabecera de control en el requerimiento de obra, modo de compra
  masiva en el requerimiento de compra y pestaña «Plan de obra» en la OF.

## Generar plan (`construction.plan.generate.wizard`)

1. Ambientes elegidos (vacío = todos los de la obra).
2. Crea las tareas de módulo faltantes desde la plantilla (no duplica: si el
   ambiente ya tiene módulos, empareja por código y avisa los que faltan).
3. Armado: una línea por módulo a la tarifa vigente de la obra.
4. Actividades por ambiente: en el ambiente; las de ML bajan al módulo cuando
   la tipología tiene anchos (cantidad = ancho / 1000).
5. Materiales: de la BOM de los módulos si la tienen; si no, de la BOM de la
   tipología. Etapa = etapa de consumo de la línea; costo vacío (lo escribe el
   planificador), salvo el ya escrito en el plan.
6. «Reemplazar» borra antes solo las líneas generadas de esos ambientes.

## Datos demo y pruebas

```bash
.venv/bin/python odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http \
  < myodoo/ol_new_apps/OL-PROJECTS/al_construction_planner/tools/planner_demo_data.py
```

Piso 05 (Dptos 501 a 508): 66 módulos, 41.33 ML, S/ 6,642.91 de material,
S/ 2,301.53 de contrata, S/ 8,944.44 en total; el script lo comprueba.

Fase 3 (después del anterior): reglas de aprobación, tres compras de la
melamina blanca, la versión 1 aprobada con su presupuesto y la versión 2 en
borrador con el costo ponderado aplicado y una línea sin etapa ni costo.

```bash
.venv/bin/python odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http \
  < myodoo/ol_new_apps/OL-PROJECTS/al_construction_planner/tools/planner_demo_baseline.py
```

Fase 4 (después de los anteriores): compra masiva con analítica de la
producción del piso 05, requerimiento de obra del piso (instalación y
acabado), un requerimiento del Dpto 501 que excede el plan con su
justificación y una OF del Dpto 502 en borrador.

```bash
.venv/bin/python odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http \
  < myodoo/ol_new_apps/OL-PROJECTS/al_construction_planner/tools/planner_demo_supply.py
```

Tests: `--test-tags /al_construction_planner` (49 tests, con el tour
`al_construction_planner_plan_tree` del árbol; `test_supply.py` cubre la
fase 4: compra masiva en los dos modos, el requerimiento con las tres
políticas y la tolerancia, la OF con su BOM y el control al confirmar, el
estado de la línea, el traspaso al replanificar y la multicompañía).

Rendimiento del árbol con volumen tipo MOMEN (deshace todo al terminar):

```bash
.venv/bin/python odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http \
  < myodoo/ol_new_apps/OL-PROJECTS/al_construction_planner/tools/planner_tree_benchmark.py
```

## Licencia

LGPL-3: depende de `base_tier_validation` (AGPL-3, OCA).
