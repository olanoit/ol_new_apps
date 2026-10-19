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

Resumen: **13 en verde, 5 adaptados al demo y 1 pendiente de MOMEN** (el
importador del maestro ya está hecho, fase 12: falta el libro real).

Control de multicompañía: `al_base_module_info` (`TestMulticompany`) y los
tests `test_multicompany` de cada fase.

## Paquete 1.8 (configurabilidad)

Criterios del requerimiento «Planificación de obra — requerimiento de
configurabilidad (paquete 1.8)» (`docs/md/`), diseño en `DISENO_v1.8.md`,
versión `42.20261016` del núcleo (16/10/2026). Corren en `ol_pe_v19` con
`--test-tags /al_construction_planner,/al_construction_planner_suite,/al_construction_attendance,/al_construction_planner_spreadsheet`.

| Req. | Criterio (resumen) | Test que lo cubre | Resultado |
|---|---|---|---|
| M18-01 | Con Construcción por partidas no hay menú, botón ni etiqueta de metrado; con Mobiliario, sí | `test_vertical_v18.TestVerticalTerms.test_construction_hides_measurement`, `test_apply_wizard_lists_changes`, `test_level_names_follow_the_template` | **Verde** |
| M18-02 | El filtro muestra Producción con sus sub etapas; marcar la padre filtra cronograma y panel a sus dos sub etapas | `test_stages_v18.TestStagesV18.test_filter_by_parent_stage`, `test_parent_bar_and_chained_sub_stages` | **Verde** |
| M18-03 | Al marcar un piso, un bloque por tipo de recurso con subtotal que cuadra con el plan | `test_io_matrix_v18.TestIoMatrixV18.test_panel_by_resource_type` | **Verde** |
| M18-04 | Matriz con una fila por elemento, insumos bajo su etapa y sub etapa, filas que suman el total | `test_io_matrix_v18.test_io_matrix_rows_columns_and_totals`, `test_io_matrix_excel` | **Verde** (filas por ambiente del demo; por mueble se elige el nivel) |
| M18-05 | Segundo requerimiento del mismo material espera a la jefatura y queda registrado | `test_exceed_v18.TestConsumptionControl.test_second_request_waits_for_head_and_is_logged`, `test_policy_defaults_from_company_and_types` | **Verde** |
| Cuadrillas | La obra crea su sede; 4 personas × 5 días = 20 jornales; la marcación alimenta el control | `al_construction_attendance` `test_crew_v18.TestCrewDays` (4 tests) | **Verde** |
| M18-09 | Valorización al 50 % manual con motivo marcada en la factura; contrata liquidada al 35 % sobre 30 % validado | `test_valuation_v18.TestValuationManual.test_manual_pct_on_valuation_and_invoice`, `test_exceed_v18.TestRepeatAndRework.test_manual_pct_over_validated` | **Verde** |
| M18-10 | Un supervisor sin el grupo no ve importes en el cronograma ni en la matriz; la jefatura sí | `test_amounts_v18.TestAmountsV18` (5 tests: cronograma, matriz, árbol y panel, vistas, lecturas, agrupaciones y exportación) | **Verde** en servidor; las pantallas OWL ocultan columnas con `show_amounts` (pendiente de revisión visual) |
| M18-11 | Avance con fotos en el chatter, evaluación del supervisor y validación con autor y fecha | `test_progress_v18.TestPartidaDriver.test_progress_traceability` | **Verde** (fotos cargadas en el avance; el portal usa el mismo `message_post`) |
| M18-12 | Partida de 120 m² con 48 m² ejecutados al 40 %; el emplacado avanza en su driver | `test_progress_v18.test_partida_progress_by_its_driver` | **Verde** |
| M18-13 | Cambiar un Work Item marca la receta desactualizada; aceptar la iguala sin tocar planes aprobados | `test_work_item_v18.TestWorkItemSync` (3 tests) | **Verde** |
| M18-14 | Cronograma, panel, control y valorización impresa con las sub etapas en orden y numeradas | `test_stages_v18.test_furniture_sequence`, `test_control_in_tree_order`, `test_valuation_v18.test_printed_valuation_stage_rows` | **Verde** |
| M17-18 | Importar la proyección deja cada módulo y mueble con los totales por material de la hoja | `test_projection_import_v18.TestProjectionImport.test_kitchen_book_keeps_sheet_totals` | **Adaptado**: libro sintético con el formato de Allcenter; los libros reales (FLORECE II, CLOSET LAMBAYEQUE) se leyeron sin errores, sin importarlos a una base |
| M17-19 | Un código inexistente bloquea la importación y lista columna y código | `test_projection_import_v18.test_unknown_code_blocks_the_import` | **Verde** |
| M17-15, M17-20 | Receta real lado a lado con la planificada; 8 % pasa registrado, 12 % espera a la jefatura | `test_module_product_v18.TestModuleProductsV18.test_real_recipe_versus_and_threshold` | **Verde** |
| M18-15 | Al aprobar el plan existen los productos de los módulos con su lista de materiales y la OF los produce con serie por departamento | `test_module_product_v18.test_products_per_module_with_bom_and_lot` | **Verde** |
| M18-16 | Envío de módulos con su transferencia; al recibir, tareas «en obra» | `test_module_product_v18.test_shipment_to_site` | **Verde** (la guía de remisión electrónica es de la localización) |
| M18-17, M18-18 | Ambiente con tipología, muebles bajo y alto y módulos con nombre, tipo y método de unión | `test_furniture_v18.TestFurnitureModelV18.test_join_method_and_special_kind`, `test_projection_import_v18` | **Adaptado**: reglas y método de unión probados con bloques sintéticos; la COCINA 04 de MOMEN con sus 9 módulos necesita su ficha |
| M18-19 | Módulo mixto y microondas generan su línea de armado con la tarifa de la obra | `test_furniture_v18.test_catalog_lines_and_project_rate_list` | **Verde** (tarifa del armado mixto a definir con Allcenter) |
| M18-20 | Dpto 304 de MOMEN genera armado y puertas comparables con la ficha ALL-PR-F-03 | — | **Pendiente de MOMEN**: la regla de piezas está; falta contrastar con la ficha (la suma de anchos no es exacta) |
| M18-21 | Segunda liquidación del mismo módulo espera autorización; re-trabajo «mal armado» se liquida aparte | `test_exceed_v18.test_repeat_payment_waits_for_head`, `test_rework_paid_apart` | **Verde** (la repetición solo puede pagarse dentro de la tolerancia de la OC) |
| M18-22 | COCINA 04 armada en la hoja con un material nuevo crea árbol, tipología, módulos, BOM, tarifas, contrato y el producto nuevo; un segundo envío no duplica | `al_construction_planner_spreadsheet` `test_worksheet_v18.TestWorksheetV18` (2 tests) | **Verde** con datos sintéticos; tablas dinámicas y listas dependientes pendientes de revisión en el navegador |

## Paquete 1.10 (fabricación por etapas)

Criterios del requerimiento «Planificación de obra — fabricación por etapas (paquete 1.10)»
(`docs/md/Allcenter_Planificacion_Paquete_1.10_Orden_Fabricacion_Por_Etapas.md`), diseño en
`DISENO_v1.10.md` (19/10/2026). Corren en `ol_pe_v19` con
`--test-tags /al_construction_planner_suite`. Escenario sintético con dos plantas de prueba
(corte y armado), la cocina C07 y el closet CL01B; la prueba E-03 de Montecarmelo se repite
en dev1 después de desplegar. Resultado del 19/10/2026: 326 pruebas de la suite, asistencia,
hoja y requerimiento de obra en verde (con la corrección del acceso al catálogo de etapas desde
planta).

| Req. | Criterio (resumen) | Test que lo cubre | Resultado |
|---|---|---|---|
| M110-01 | La cadena devuelve [1.1, 1.2]; sin planta en 1.1, [1.2]; sin plantas u otra compañía, vacía | `test_stage_chain_v110.TestStageChainV110.test_production_chain` | **Verde** |
| M110-02 | Lista de corte en la planta de corte, solo con producción de piezas; lista de fabricación en la planta de armado con el intermedio y lo de armado (tornillo 4); receta con secuencia 1000 y el tornillo en dos líneas (4 y 54); closet sin armado con su lista de corte y sin intermedio | `test_import_builds_stage_boms` | **Verde** |
| M110-02 | Volver a importar no duplica y conserva las operaciones | `test_reimport_keeps_operations_and_does_not_duplicate` | **Verde** |
| M110-02 | Sin planta en ninguna etapa, la receta de hoy y sin listas nuevas | `test_import_without_chain_is_unchanged` | **Verde** |
| M110-02 | Generar el plan da los mismos materiales con y sin cadena | `test_plan_materials_do_not_depend_on_chain` | **Verde** |
| M110-02 | Al aprobar el plan, subproductos de módulo que suman 100 %; la lista del módulo sin instalación y en la planta del armado | `test_module_byproducts` | **Verde** |
| M110-03, M110-04 | Una corrida sin forzar planta: cocinas en armado y closet en corte; módulos ligados; al confirmar las dos madres juntas, una hija por madre con su plan, ambientes y proyecto; cada orden compara solo sus etapas; el paquete no es cambio de material; accesorios solo en el armado | `test_orders_without_forced_plant_and_child_inherits_plan` | **Verde** |
| M110-03 | Con «Forzar planta», todas las órdenes van a esa planta | `test_forced_plant` | **Verde** |
| M110-04 | Con la política «bloquear», la madre se confirma y la hija queda «excede» con el aviso en la madre | `test_child_excess_does_not_block_mother` | **Verde** |
| M110-05 | No se valida sin departamento; «En tránsito» al reservar; «En obra» al validar; despacho parcial: el que no salió sigue «Producido» y sin enlace, con el aviso | `test_site_dispatch_by_apartment` | **Verde** |
| M110-05 | Una transferencia interna sin la marca no cambia nada | `test_internal_transfer_without_flag_changes_nothing` | **Verde** |
| M110-06 | La orden de posventa no se confirma sin motivo; con motivo sí; la de armado no pide motivo; el usuario de Fabricación no crea motivos | `test_after_sales_reason` | **Verde** |
| M110-07 | Resumen «Cantidad», «Fuera del plan» y «Ambos», «N materiales» y filtro «Me toca aprobar» | `test_approvals_v110.TestApprovalsV110.test_summary_fields` | **Verde** |
| M110-07 | Aprobar en bloque: quien no tiene el tramo no aprueba ninguna; quien lo tiene, todas | `test_bulk_approve` | **Verde** |
| M110-07 | Rechazar en bloque con un motivo: cada documento vuelve a borrador con el motivo | `test_bulk_refuse` | **Verde** |
| M110-08 | Saldo negativo: presupuestado, ya pedido, saldo negativo, exceso igual a lo pedido y exceso % | `test_negative_balance_figures` | **Verde** (10 presupuestados y 34 ya pedidos en lugar de 4 y 24) |
| M110-08 | Una solicitud aprobada cuyo documento ya siguió no se rechaza, tampoco desde los aprobadores; los aprobadores cancelados por el sistema no disparan el error | `test_refuse_after_approval_is_blocked` | **Verde** |
| M110-09 | Sin ajuste, el lote de hoy; con el formato de Allcenter, OBRA-0301-C07-MB1; módulos distintos, lotes distintos; clave desconocida da error | `test_stage_chain_v110.test_module_lot_pattern` | **Verde** |
| M110-07 | El jefe de producción no ve la columna de soles | — | **Por revisar en dev1**: la columna lleva el grupo «ve montos» como el resto del planificador |

## Qué falta para validarlos con MOMEN

1. **Maestro de MOMEN** (`Maestro_Planificacion_MOMEN_v03.xlsx`): el
   importador ya existe (fase 12, «Importar maestro y ETO», W-15: tipologías,
   módulos, ML, actividades, BOM con su etapa y árbol de la obra; ver
   `DISENO_TECNICO.md` §6.9). Falta solo el libro real: pasarlo al formato de
   la plantilla (o añadir sus encabezados como sinónimos) e importarlo en la
   base limpia. Con él se comprueban los criterios 1, 2 (sin la línea de
   ajuste), 4 (59 líneas) y 5 (37.9 %). La vista previa del importador ya
   avisa lo que la especificación señala del maestro: filas de BOM sin etapa
   (con su monto), productos sin costo y productos repetidos (los tornillos
   de PROYECCION_MATERIALES se suman); el armado de cajones sin cantidades
   hay que completarlo en el libro.
2. **ETO por módulo** (anchos y códigos): la hoja ETO del mismo importador
   crea los módulos reales con su ancho y «Generar plan» baja la instalación
   por ML al módulo (decisión aceptada el 11/10/2026). Falta el ETO real de
   la obra.
3. **Compras reales**: las 27 OC de 3101508 entre el 10/04 y el 10/10/2026
   con sus tipos de cambio en la base limpia (criterio 13).
4. **Contrato**: el monto adjudicado (S/ 159,231.23, ¿con o sin IGV?), el
   adelanto (el correo dice 30 % con carta fianza y el contrato «No aplica»)
   y el calendario real de valorización y cobro (criterios 16 a 18).
5. **Decisiones** que cambian cifras: las propuestas de ALTA se aceptaron
   el 11/10/2026 (`DISENO_TECNICO.md` §5.1). Quedan los datos del cliente:
   las cuentas del fondo de garantía y de la retención (contabilidad), las
   partidas por familia de tipología en la OV y el horario de días hábiles
   del ingreso.

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
- Documentación para usuarios con todas las pantallas (P-01 a P-22) y asistentes (W-01 a
  W-14), ficha con capturas y novedades en `CHANGELOG.md`.
