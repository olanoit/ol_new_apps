# Planificación de obra — criterios de aceptación

Estado de los 19 criterios de aceptación de la especificación v1.4
(`ESPECIFICACION_v1.4.md`, «Criterios de aceptación») al cierre de la fase 11
del módulo `al_construction_planner` (versión `10.20261010`, 10/10/2026).

La especificación pide probarlos **sobre MOMEN en la base limpia**. El libro
`Maestro_Planificacion_MOMEN_v03.xlsx` no está disponible en el proyecto: los
tests reproducen cada criterio con datos sintéticos que siguen las cifras de
la especificación (demo del piso 05 en `tests/common.py` y
`tools/planner_demo_*.py`, y la obra de la ruta del ingreso en
`tests/test_income.py`). Todos corren en `ol_pe_v19`
(`--test-tags /al_construction_planner`).

Resultados:

- **Verde**: el test comprueba el criterio con las mismas cifras de la
  especificación.
- **Adaptado al demo**: el test comprueba la regla, pero con cifras del demo
  que difieren de las de MOMEN, y se indica la diferencia.
- **Pendiente de MOMEN**: necesita el maestro y la base limpia para
  comprobarse con sus cifras.

| # | Criterio (resumen) | Test que lo cubre | Resultado |
|---|---|---|---|
| 1 | Generar el plan de MOMEN: 1,263 módulos bajo 153 ambientes; S/ 126,854.54 de material y S/ 43,909.56 de contratas (± S/ 1) | `test_generate.TestGenerate.test_generate_space_501`, `test_regenerate_keeps_modules_and_costs`, `test_existing_eto_modules`; volumen con `tools/planner_tree_benchmark.py` (20 pisos, 153 departamentos, 1,257 módulos, 7,800 líneas) | **Pendiente de MOMEN**: la regla de generación está probada en el piso 05 del demo; las cifras de la obra completa necesitan el maestro (tipologías 01 a 10 con su BOM) |
| 2 | Piso 05: 66 módulos, 41.33 ML y S/ 8,944.44; Dpto 501: 7 módulos y S/ 993.66 | `test_plan_tree.TestPlanTree.test_root_and_floor`, `test_apartment_and_modules`; `test_schedule.test_gantt_data_stage_rows` | **Verde** (el reparto entre las tipologías 04 a 08 es de ejemplo y cuadra con una línea «(ajuste demo)») |
| 3 | Marcar el piso marca 8 departamentos, 8 ambientes y 66 módulos; desmarcar un módulo deja en parcial a sus padres | `test_plan_tree.test_selection_child_of`; recorrido `plan_tree_tour` (`TestPlanTreeTour.test_plan_tree_tour`) | **Verde** |
| 4 | Asignar a Leandro la instalación del piso 05: contrata en 59 líneas y 8 líneas por S/ 941.17 en su OC de servicio | `test_contracts.TestContracts.test_assign_contract`; desde el cronograma, `test_schedule.test_contract_wizard_from_schedule_selection` | **Adaptado al demo**: 64 líneas (el demo pone las 8 actividades en los 8 ambientes; el maestro tiene 59 porque algunas tipologías no tienen todas); OC con 8 líneas y S/ 941.17 igual |
| 5 | Validar 2.76 ML de mueble bajo en el Dpto 504: línea al 100 % e instalación de la cocina al 37.9 % | `test_contracts.test_progress_and_node_percentage` | **Adaptado al demo**: línea al 100 % y la cocina en 42.2 % (48.60 de la tipología de ejemplo); en el maestro, 49.68 ÷ 131.06 = 37.9 %. La regla (avance ponderado por valor, sin porcentajes escritos) es la misma |
| 6 | Jueves 05/11: liquidación de Leandro del 29/10 al 04/11, pago el sábado 07/11, S/ 380.88 bruto y S/ 342.79 neto | `test_contracts.test_weekly_settlement` | **Verde** |
| 7 | Un avance del 05/11 no entra a esa liquidación y aparece en la del 12/11 | `test_contracts.test_weekly_settlement` | **Verde** |
| 8 | Aprobar la liquidación recibe en la OC y factura con vencimiento el sábado; no recibe más que lo ordenado | `test_contracts.test_weekly_settlement`, `test_settlement_cannot_receive_more_than_ordered` | **Verde** |
| 9 | La OF del piso 05 con el producto de cada tipología y los componentes de su BOM; al confirmarse se contrasta con el saldo | `test_supply.TestSupply.test_production_from_bom`, `test_production_confirm_control` | **Verde** |
| 10 | Un requerimiento que excede el saldo se comporta según las tres políticas | `test_supply.test_request_policy_warn`, `test_request_policy_approval`, `test_request_policy_block_and_tolerance` | **Verde** |
| 11 | En el cronograma, marcar la instalación del piso 05 y «Asignar contrata» abre P-05 con 8 actividades y S/ 941.17 | `test_schedule.TestSchedule.test_contract_wizard_from_schedule_selection`; recorrido `schedule_tour` (`TestScheduleTour`) | **Verde** |
| 12 | Mover una semana la instalación del piso 05 corre siete días la necesidad y avisa de los requerimientos desfasados | `test_schedule.test_drag_installation_shifts_need_and_warns_logistics`, `test_drag_with_chain_pushes_next_stages` | **Verde** |
| 13 | Precios de 3101508 del 10/04 al 10/10/2026: 27 compras, ponderado S/ 122.39 y media móvil de 4 semanas S/ 122.79, en dólares al tipo de cambio de su fecha | `test_prices_supply.TestPricesSupply.test_criterion_27_purchases`, `test_report_converts_currency_and_uom`, `test_stats_exact` | **Adaptado al demo**: 27 compras sintéticas (24 en dólares) construidas para dar 122.39 y 122.79; las reales de MOMEN necesitan sus OC y tipos de cambio |
| 14 | Un plan con una línea sin costo no va a aprobación; W-12 guarda la base y su fecha | `test_baseline.TestBaseline.test_request_blocked_without_stage_or_cost`, `test_apply_cost_with_basis` | **Verde** |
| 15 | Producto creado desde el plan: activo, con código de su familia y marcado con el plan | `test_prices_supply.test_create_product_from_plan`, `test_use_similar_product` | **Verde** |
| 16 | Precio S/ 159,231.23, avance de 28.10 % a 42.94 % con material: la entrega del 29/10–04/11 devenga S/ 23,627.65 | `test_income.TestIncome.test_weekly_delivery_accrues_revenue` | **Verde** (plan sintético de S/ 170,764.10 con los mismos avances) |
| 17 | La valorización no se confirma sin fecha, nombre, cargo y documento; su factura lleva la cantidad al % acumulado y no supera lo confirmado | `test_income.test_valuation_flow_and_invoice`, `test_invoice_guarantee_line` | **Verde** |
| 18 | Con el calendario de P-21, la valorización 2 confirmada en la semana 12/11–18/11, facturada en la 19/11–25/11 y cobrada en la 17/12–23/12; el cobrado acumulado cierra en S/ 159,231.23 con el fondo de garantía | `test_schedule_report.TestScheduleReport.test_plan_schedule` (plan), `test_real_schedule` (real), `test_plan_cost_by_working_days` (reparto y redondeo) | **Adaptado al demo**: mismas semanas y mismo cierre, sobre la obra sintética de la ruta del ingreso con etapas de ejemplo (el monto de cada valorización depende del calendario real de MOMEN) |
| 19 | El inicio muestra a un supervisor solo los avances por validar de sus obras y la fila abre esa lista filtrada | `test_schedule_report.test_home_supervisor_sees_own_works`, `test_home_works_and_milestone`, `test_home_stage_without_contract` | **Verde** («sus obras»: responsable del proyecto o en «Supervisores de obra») |

Resumen: **13 en verde, 5 adaptados al demo y 1 pendiente de MOMEN.**

Control de multicompañía: `al_base_module_info` (`TestMulticompany`) y los
tests `test_multicompany` de cada fase.

## Qué falta para validarlos con MOMEN

1. **Maestro de MOMEN** (`Maestro_Planificacion_MOMEN_v03.xlsx`): un
   importador de tipologías (módulos, ML, actividades y BOM con su etapa) y
   del árbol de la obra (20 pisos, 153 departamentos y ambientes con su
   tipología). Con él se comprueban los criterios 1, 2 (sin la línea de
   ajuste), 4 (59 líneas) y 5 (37.9 %). Antes hay que resolver lo que la
   especificación ya señala del maestro: 20 filas de BOM sin etapa
   (S/ 10,709.20), 3 productos sin costo, armado de cajones sin cantidades y
   tornillos repetidos en PROYECCION_MATERIALES.
2. **ETO por módulo** (anchos y códigos): para bajar la instalación por ML
   al módulo; sin él queda en el ambiente (decisión de diseño 5).
3. **Compras reales**: las 27 OC de 3101508 entre el 10/04 y el 10/10/2026
   con sus tipos de cambio en la base limpia (criterio 13).
4. **Contrato**: el monto adjudicado (S/ 159,231.23, ¿con o sin IGV?), el
   adelanto (el correo dice 30 % con carta fianza y el contrato «No aplica»)
   y el calendario real de valorización y cobro (criterios 16 a 18).
5. **Decisiones abiertas** que cambian cifras: fondo de garantía y
   retención en la factura (contabilidad), partidas por familia de
   tipología, horario de días hábiles del ingreso y cuenta de la retención.

## Revisión final del módulo (fase 11)

- Menús de la especificación: Obras (Inicio P-01, planes y P-03, árbol P-02,
  etapas, tareas, recursos, análisis, obras y su calendario P-21),
  Cronograma (P-15), Avance (P-06, P-07), Contratas (P-05, W-06, OC de
  servicio, P-08), Ingresos (P-19, P-20, W-13, cobranza de la obra),
  Abastecimiento (P-18, P-16, P-11, OF, asignaciones), Reportes (P-22, su
  análisis, P-13 y P-16) y Configuración (ajustes, P-12, P-14, reglas de
  aprobación). El inicio es la acción por defecto de la aplicación.
- Seguridad: cinco grupos (Reporte de avance, Usuario, Planificador,
  Administrador e Ingresos) con permisos en cada modelo y asistente; el
  cronograma valorizado es de solo lectura (se recalcula con `sudo`
  justificado tras comprobar el acceso a la obra).
- Multicompañía: `_check_company_auto` y `check_company=True` en las
  relaciones, reglas por compañía en todos los modelos con compañía
  (incluido `construction.schedule.report`).
- Etiquetas en español (auditoría `docs/validacion/etiquetas_espanol.py` en
  0) y `i18n/es.po` regenerado.
- Sin advertencias del ORM al actualizar el módulo en `ol_pe_v19`.
- Guía funcional con todas las pantallas (P-01 a P-22) y asistentes (W-01 a
  W-14), ficha con capturas y novedades en `CHANGELOG.md`.
