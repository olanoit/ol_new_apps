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
| 5 | Contratas: asignar contrata con OC de servicio por contrata y obra (W-05, P-05), avance por driver con fotos (W-07, P-06), avances por validar (P-07), avance de nodos y pestaña «Recursos y avance» (P-09), estado del módulo | hecha |
| 6 | Liquidación semanal (P-08): acción programada, aprobación por niveles, recepción en la OC y factura con vencimiento el día de pago | hecha |
| 7 | Control y personal propio: control de la OC con analítica contra el presupuesto, estado y montos de control guardados, análisis de control (P-13), cuadrillas (W-06), cambiar fechas (W-08), reversión del estado del módulo | hecha |
| 8 | Cronograma con recursos (P-15): etapas del ambiente, herencia de `al.gantt.data`, pantalla «Cronograma» sobre el Gantt de la suite con selección, panel de recursos, acciones W-02 a W-08, arrastre de etapas con recálculo de la necesidad y aviso a Logística, carga semanal | hecha |
| 9+ | Ingresos (entregas, valorizaciones, factura de la valorización), cronograma valorizado | pendiente |

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
- `construction.task.progress` (fase 5): avance reportado por driver
  (`AVN/año/#####`) con fotos, reportado / validado / rechazado.
- `construction.contract.settlement` / `.line` (fase 6): liquidación semanal
  (`LIQ/año/#####`) con aprobación por niveles (`tier.validation`).
- Herencias de las fases 5 y 6: `purchase.order` (`construction_is_service_order`,
  `construction_project_id`, liquidaciones) y su línea
  (`construction_activity_id`, `construction_retention_pct`); `account.move`
  (`construction_settlement_ids`, sincroniza «Pagada»); `project.project`
  (`construction_week_start_day`, `construction_settlement_day`,
  `construction_payment_day`); `res.company` (los mismos días por defecto y
  `construction_retention_account_id`); `project.task`
  (`construction_progress_ids`, `construction_current_line_ids`,
  `construction_progress_pct`).
- Fase 7: asistentes `construction.plan.crew.wizard` (W-06) y
  `construction.plan.reschedule.wizard` (W-08); en la línea del plan, estado
  y montos de control almacenados; `purchase.order`
  (`construction_exceed_state`, `construction_exceed_reason`); `project.task`
  (`construction_unit_state_base`).

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

## Contratas (fase 5, P-05 a P-07 y P-09)

- **W-05 «Asignar contrata»** (`construction.plan.contract.wizard`,
  `action_plan_contract_wizard`; base `construction.plan.supply.mixin`): etapa
  (una o todas), actividades (vacío = todas), contrata y fechas de ejecución.
  Toma las líneas de contrata de la selección con saldo por asignar
  (planificado − pedido) y sin otra contrata (se avisan), y propone una fila
  por actividad: driver total, tarifa vigente
  (`construction.labor.activity._get_rate(obra, contrata, inicio)`), monto y
  retención. Al confirmar: busca la OC de servicio abierta de la contrata en
  la obra (`construction_is_service_order`, `construction_project_id`, no
  anulada ni bloqueada) o la crea en borrador; suma la cantidad a la línea de
  la misma actividad y tarifa o agrega una (`construction_activity_id`,
  `construction_retention_pct`, analítica de las líneas o de la obra); pone
  `partner_id` en las líneas del plan con `construction_plan_force` y crea
  las asignaciones `service_order`. La OC y el producto se escriben con
  `sudo` (justificado en el código): quien asigna no necesita permisos de
  compras. Si la actividad no tiene producto de servicio se crea uno (servicio,
  recepción manual, unidad del driver, sin impuestos).
- **Avance reportado** (`construction.task.progress`): `task_id` + `activity_id`
  → `plan_line_id` (línea del plan vigente, calculada); contrata, etapa y
  ancestros relacionados y almacenados; fotos (`attachment_ids`, al menos
  una, también al crear); `amount` = unidades × costo unitario de la línea
  (pondera el avance de los nodos); `period_start` y
  `settlement_date_planned` (semana de liquidación por la fecha y la
  configuración de la obra). Restricción: lo reportado no rechazado de la
  línea ≤ planificado + tolerancia del plan. Validar, rechazar (asistente
  `construction.reason.wizard` con motivo) y volver a reportado (no si está
  liquidado ni en una liquidación presentada o validada; si estaba en una en
  borrador, sale de ella) son del grupo Planificador. Solo se corrige en
  reportado; se borra si no está validado.
- **W-07 «Registrar avance»** (`construction.plan.progress.wizard`,
  `action_plan_progress_wizard`, grupo Reporte de avance): actividad (solo las
  de la selección), contrata opcional, fecha y fotos; una fila por línea
  (módulo o ambiente) con presupuestado, acumulado, por validar, saldo y
  «Reportar hoy» (por defecto el saldo; no más que saldo + tolerancia). Copia
  las fotos a cada avance.
- **P-07 «Avances por validar»** (`action_construction_progress_to_validate`):
  reportados agrupados por obra › contrata › semana de liquidación, con validar
  y rechazar en lote.
- **Ejecución por driver** en la línea (no almacenados, `compute_sudo`):
  `qty_executed` (contrata: avances validados; personal propio con unidad de
  horas: horas de la hoja de horas del nivel y sus descendientes con
  empleados del rol; material: consumido), `qty_settled` (avances en
  liquidaciones aprobadas o pagadas) y `progress_pct` (≤ 100 %). `line_state`
  de contratas: Excedida si el ejecutado pasa lo planificado + tolerancia,
  Completa al llegar a lo planificado (o todo asignado y recibido).
- **Avance de nodos**: `construction.resource.plan._progress_amounts(dominio,
  campo)` = Σ valor de los avances validados (`_read_group` sobre los
  ancestros del avance) ÷ Σ monto planificado de contrata y personal propio.
  Lo usan el árbol (columna y medida «Avance», panel «Acum.») y la tarea
  (`construction_progress_pct`). Pestaña **«Recursos y avance»** (P-09) en la
  tarea: líneas del plan vigente del nivel y sus descendientes, avance
  valorizado, avances reportados y botón «Registrar avance».
- **Estado del módulo** (`project.task._construction_update_unit_state`, al
  validar o revertir): Producido con todo su armado (líneas del módulo),
  Instalado con toda la instalación (del módulo o de su ambiente). Solo sube.
- **Semana de la obra**: `project.project._construction_period(fecha)` y
  `_construction_settlement_dates(inicio)`: periodo desde el día de inicio
  (jueves) seis días; liquidación = primer día de liquidación tras el cierre;
  pago = primer día de pago desde la liquidación; feriado → día hábil
  anterior (`res.company._construction_previous_working_day`: ausencias
  globales de la compañía, de cualquiera de sus calendarios; los días sin
  horario no cuentan como feriado).

## Liquidación semanal (fase 6, P-08)

- `construction.contract.settlement`: contrata, obra, OC de servicio, plan,
  periodo (`period_start` restringido al día de inicio de la obra;
  `period_end`, `settlement_date` y `payment_date` calculados), estados
  Borrador › Presentada › Validada › Aprobada › Pagada (+ Anulada), una por
  contrata, obra y semana (`models.UniqueIndex` salvo anuladas). Líneas
  (`.line`) por línea de la OC: driver de la semana (avances agrupados por la
  línea de OC de su asignación), tarifa de la OC, monto, retención (%) de la
  OC; acumulado, presupuestado y avance informativos (líneas de la contrata
  con esa actividad en el plan vigente). Retención = Σ por porcentaje de
  round(monto × %), sobre el total para no acumular redondeos.
- `_prepare_settlements(hoy, obras)`: para cada obra y contrata con avances
  validados sin liquidar mira la semana anterior y la actual; si su fecha de
  liquidación ya llegó crea la liquidación en borrador (o refresca la que
  sigue en borrador) con los validados hasta el fin del periodo (incluidos los
  rezagados). Acción programada diaria `ir_cron_prepare_settlements` (también
  sincroniza «Pagada»). «Actualizar avances» refresca a mano.
- Flujo: «Presentar» y «Validar» (Planificador), «Devolver a la contrata»
  (motivo), «Anular» (libera los avances). Al validar se piden las revisiones
  (`tier_contract_settlement_manager`, jefatura; `_state_from = validated`);
  la última aprobación (`_action_approve`, con `sudo` justificado) exige la OC
  confirmada, suma la semana a `qty_received` sin pasar lo ordenado y crea la
  factura de proveedor con `_prepare_invoice` / `_prepare_account_move_line`
  (cantidad de la semana, sin plazo de pago y con `invoice_date_due` = día de
  pago); con cuenta de retención en la compañía agrega la línea negativa. El
  rechazo de la jefatura la vuelve a Presentada.
- «Pagada»: `account.move._compute_payment_state` sincroniza las liquidaciones
  de la factura (pagada ↔ aprobada).
- Ganchos del plan completados: `action_close` se niega con liquidaciones en
  borrador, presentadas o validadas, o con avances validados sin liquidar;
  `_transfer_to_new_version` pasa los avances no liquidados a la línea nueva.

## Control y personal propio (fase 7, P-13, W-06, W-08)

- **Estado y montos de control guardados.** En la línea del plan,
  `line_state`, `amount_committed`, `amount_actual`, `amount_remaining` y
  `executed_pct` son campos almacenados sin `compute`: dependen de documentos
  de otros modelos (compras, inventario, fabricación, turnos, horas) que no se
  pueden declarar en `@api.depends`. Los escribe
  `construction.resource.plan.line._refresh_control()` (con `sudo`
  justificado), llamado por los eventos: asignaciones (alta, cambio, baja),
  líneas del plan (cantidad, costo, unidad, tipo, rol, actividad, nivel),
  plan (estado, tolerancia), requerimiento de obra (estado, procesar, líneas),
  compra masiva (estado, líneas), OC (estado; recepción de la línea), OF
  (estado), `stock.move._action_done`, avances (alta, estado, cantidad,
  liquidación, baja), turnos (horas, fechas, recurso, baja) y hojas de horas
  (alta, cambio, baja). Red de seguridad: acción programada horaria
  `ir_cron_refresh_plan_control` (los turnos terminan con el paso del tiempo)
  y el botón «Actualizar control». La migración `6.20261010` los calcula para
  las líneas existentes.
- **Análisis de control (P-13).** Pestaña «Control» del plan
  (`control_html`: etapa › tipo de recurso con planificado, comprometido,
  real, saldo y % ejecutado, leídos con `_read_group` de los montos
  guardados) y acción `action_construction_plan_control` (pivote y gráfico
  propios; menú Obras ▸ Análisis de control y botón del plan). Filtros y
  agrupaciones por estado, contrata, producto y actividad.
- **Personal propio.** Real = horas de la hoja de horas de la tarea y sus
  descendientes con empleados del rol × `hourly_cost` de cada empleado;
  comprometido = horas de los turnos de la línea aún no registradas (por
  empleado) × su costo hora. El ejecutado en horas ya venía de la hoja de
  horas (fase 5).
- **Asignar cuadrilla (W-06, `construction.plan.crew.wizard`).** Selección,
  etapas, rol, recursos, primera semana (inicio de semana de la obra),
  semanas y horas por semana; un `planning.slot` por recurso, semana y línea
  de personal propio con `construction_task_id`, `construction_plan_line_id`,
  rol, obra y horas (repartidas por monto planificado), y su asignación
  `planning_slot` (horas en la unidad de la línea si se mide en horas; si
  se paga por driver, 0). Los recursos reciben el rol si no lo tienen. Al
  cambiar las horas del turno, la asignación lo sigue.
- **Cambiar fechas (W-08, `construction.plan.reschedule.wizard`).** Desplazar
  n días o fecha nueva (para el inicio más temprano de la selección). Con
  todas las etapas mueve las fechas de inicio y fin del Gantt de las tareas
  (`al.gantt.field.map`) y recalcula `date_needed` desde el nuevo inicio
  (`_get_default_date_needed`); con algunas, solo desplaza `date_needed` de
  esas líneas. Avisa a Logística (actividad «Fechas del plan cambiadas») en
  los requerimientos de obra, compras masivas y OC abiertos de las líneas
  cuya fecha queda antes de la nueva necesidad al postergar (o después, al
  adelantar). Responsable: el comprador de la OC o el primer usuario de
  Logística de la compañía.
- **OC con analítica de la obra.** `purchase.order.button_confirm` (salvo las
  OC de servicio, que se controlan al asignar y liquidar): por cada
  combinación analítica de sus líneas con la cuenta de una obra con plan
  vigente busca la línea del presupuesto analítico del plan que la cubre
  (`_construction_match_budget_line`, la más específica) y compara
  comprometido de esa línea (`account_budget_purchase`: OC confirmadas sin
  facturar más lo imputado) + esta OC con el presupuesto × (1 + tolerancia).
  Una combinación sin línea de presupuesto queda fuera del presupuesto.
  Política más estricta de las obras tocadas: bloquear (error), avisar (W-10
  y confirmar) o pedir aprobación (W-10 con justificación; confirma la
  jefatura del planificador con `sudo` justificado). Campos
  `construction_exceed_state` / `construction_exceed_reason` en la OC.
- **Factura de la valorización (fase 10).** Queda el gancho: el control
  «Monto confirmado menos facturado de cada partida» irá en el botón «Crear
  factura» de la valorización, que aún no existe.
- **Estado del módulo al revertir.** `_construction_update_unit_state(revert=True)`
  desde `action_reset`: un módulo en Producido o Instalado baja a lo que
  justifica el avance que queda o, si es mayor, al estado que tenía antes de
  que el avance lo subiera (`construction_unit_state_base`).
- **Obra de planilla.** No se enlaza `l10n_pe.hr.construction.site`
  (al_hr_pe_construction) con el proyecto para no crear una dependencia con
  la planilla: ambos se encuentran por la cuenta analítica (ponga en la obra
  de la planilla la cuenta analítica del proyecto).

## Cronograma con recursos (fase 8, P-15)

- **Etapa del ambiente (`construction.space.stage`).** Una por ambiente y
  etapa (restricción `UNIQUE(space_task_id, stage)`), con `date_start` y
  `date_end`. Pertenece al ambiente, no a la versión del plan. `_sync_from_plan`
  crea las que faltan al generar el plan (una semana por etapa desde el
  inicio del ambiente o del plan, de lunes a viernes); botón «Crear etapas
  del cronograma» y migración `7.20261010` para los planes ya generados.
  `partner_id`, `role_id`, `amount_planned` y `progress_pct` se calculan en
  lote desde las líneas del plan vigente (`_resources_by_stage`,
  `_progress_by_stage`); `predecessor_id`, por el orden de las etapas.
- **Mover fechas.** `write` de `date_start` desplaza `date_needed` de las
  líneas de esa etapa en el ambiente y sus módulos tantos días como el
  inicio y llama a `construction.resource.plan._notify_logistics` (el mismo
  aviso de W-08, ahora en el plan; un documento con el aviso pendiente suma
  la nota en vez de recibir otra actividad). `action_gantt_reschedule` es la
  entrada del arrastre: con `chain` empuja las etapas siguientes solapadas al
  lunes siguiente. W-08 mueve también las etapas de las etapas elegidas (con
  `construction_stage_keep_lines`, porque ya movió las líneas).
- **Capa de datos (`models/gantt_data.py`).** Hereda `al.gantt.data` sin
  tocar el Gantt. Solo con `options['construction_schedule']`: en el modo
  «Etapas» filtra pisos, departamentos y ambientes (`_get_task_domain`) e
  incluye los que no tienen fecha; añade a cada tarea `construction`
  (nivel, monto, avance, contratas, estado del módulo, alertas de líneas
  excedidas, con un `_read_group` por nivel), y al payload
  `construction_stages` y `construction_stage_links`. Opciones
  `construction_plan_id`, `construction_rows` y `construction_stage`.
- **Pantalla (`static/src/schedule/`).** `ConstructionScheduleAction` hereda
  `GanttAction` (`al_project_gantt_backend`) por sus puntos de extensión:
  filas `t<id>`/`s<id>` (de solo lectura las tareas, cuya barra resume sus
  etapas), columnas de monto, avance y contrata, casillas en cascada, panel
  con `get_selection_summary` (el del árbol, con el filtro de etapas), los
  botones de `get_tree_actions` con `construction_selection_stages` en el
  contexto (los asistentes activan solo esas etapas; W-05 toma la etapa si es
  una) y la carga semanal (`construction.resource.plan.get_schedule_load`:
  contratas y personal propio por contrata o rol y etapa, repartidos entre
  los días hábiles de la etapa).
- **Grupos.** El usuario de la planificación implica el usuario del Gantt;
  las etapas se leen con «Reporte de avance» y se mueven con «Planificador».

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

Fases 5 y 6 (después de los anteriores): Leandro con la instalación del
piso 05 (64 líneas, OC de servicio confirmada por S/ 941.17), Gonza con el
armado del Dpto 501, el avance del ejemplo de P-08 validado, la liquidación
del 29/10 al 04/11 presentada (bruto S/ 380.88, neto S/ 342.79) y avances por
validar.

```bash
.venv/bin/python odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http \
  < myodoo/ol_new_apps/OL-PROJECTS/al_construction_planner/tools/planner_demo_contracts.py
```

Fase 7 (después de los anteriores): personal propio en las cocinas de los
Dpto 501 y 502, la cuadrilla de dos obreros en la del 501 (4 turnos de 4 h)
y 6 h registradas.

```bash
.venv/bin/python odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http \
  < myodoo/ol_new_apps/OL-PROJECTS/al_construction_planner/tools/planner_demo_control.py
```

Tests: `--test-tags /al_construction_planner` (72 tests, con el tour
`al_construction_planner_plan_tree` del árbol; `test_supply.py` cubre la
fase 4: compra masiva en los dos modos, el requerimiento con las tres
políticas y la tolerancia, la OF con su BOM y el control al confirmar, el
estado de la línea, el traspaso al replanificar y la multicompañía;
`test_contracts.py` cubre las fases 5 y 6 sobre una copia del piso 05 del
demo: criterios de aceptación 4 a 8, saldo y tolerancia, fotos, rechazo y
reversión, estado del módulo, periodos y feriados, cierre y traspaso,
seguridad y multicompañía; `test_control.py` cubre la fase 7: OC con
analítica y las tres políticas, P-13 contra las líneas, estado filtrable,
cuadrilla con turnos y horas, cambiar fechas con aviso a Logística, reversión
del estado del módulo y multicompañía).

Rendimiento del árbol con volumen tipo MOMEN (deshace todo al terminar):

```bash
.venv/bin/python odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http \
  < myodoo/ol_new_apps/OL-PROJECTS/al_construction_planner/tools/planner_tree_benchmark.py
```

## Licencia

LGPL-3: depende de `base_tier_validation` (AGPL-3, OCA).
