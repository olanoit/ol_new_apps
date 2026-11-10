# Diseño del paquete 7 de CREVAL · cartera de obras e indicadores

Fuente: «Requerimiento · paquete 7» v2.0 (10-nov-2026), CR-59 a CR-65. Las
cifras y nombres de la prueba no se copian: el repositorio es público. Manda
`ARQUITECTURA_COMUN.md` en lo común.

## 1. Revisión de configuración

La tabla del requerimiento revisa Odoo nativo (tablero de proyectos, panel de
rentabilidad, presupuesto analítico, actividades), OCA y lo hecho en AL.
Ninguna ruta cumple sola; se combinan el favorito nativo del proyecto, la
validación por niveles de OCA y los cálculos de AL.

## 2. Entregas

| Entrega | Requerimientos | Qué resuelve |
|---|---|---|
| 1 | CR-62, CR-61 | Las fuentes: costo ejecutado e ingreso contables; avance físico y valor ganado por partida |
| 2 | CR-64, CR-63 | Cambios cobrables en la venta; meta de valorización del mes con aprobación |
| 3 | CR-60 | Ficha de indicadores de la obra |
| 4 | CR-59, CR-65 | Cartera de obras en el Inicio; pendientes por área |

## 3. Hecho · entrega 1 (10-nov)

- CR-62: `project.project._construction_accounting_amounts(date_from,
  date_to)` suma los apuntes analíticos de la cuenta de la obra: costo
  ejecutado = cuentas de gasto (`expense`, `expense_direct_cost`,
  `expense_depreciation`), en positivo; ingreso contable = cuentas de ingreso
  (`income`, `income_other`). Las cuentas de balance quedan fuera por su
  tipo; los prefijos de «Cuentas fuera del costo de obra» (Ajustes; «9,79»
  por defecto en una compañía peruana) no suman. Campos de la obra
  «Costo ejecutado» e «Ingreso contable» y la acción que abre los apuntes de
  costo agrupados por cuenta. En el Cronograma valorizado, «Real» pasa a
  «Avance valorizado al costo del plan» (botón, serie y ayuda); las cantidades
  «Ejecutado» no cambian.
- CR-61: `project.project._construction_physical_values(date)` usa la regla
  de la valorización (`_construction_partida_progress`) a la fecha (hoy) por
  partida: avance físico = Σ avance × precio ÷ Σ precio (solo partidas) y
  valor ganado = Σ avance × costo meta (presupuesto aprobado de sus líneas o,
  sin él, lo planificado). Campos «Avance físico» y «Valor ganado» de la obra.
  «Avance de la partida» de las obras nuevas sale del parámetro de la
  compañía («Avance valorizado» por defecto); las existentes conservan el
  suyo. El avance del árbol del plan no cambia.

## 4. Hecho · entrega 2 (10-nov)

- CR-64: el cambio de obra tiene «Cobro» (cobrable, no cobrable, en trámite) y
  «Efecto en el margen» (precio al cliente − costo), en la lista (agrupada por
  «Cobro») y en el formulario. Al aprobar un cambio cobrable se agrega a la
  orden de venta del contrato una línea con el producto «Adicional de obra» de
  Ajustes y el precio al cliente (negativo si es deductivo), ligada al cambio
  (`sale_line_id`). Con la orden bloqueada o sin orden, el cambio lo dice en
  su historial y no agrega la línea. La venta vigente es la orden con esas
  líneas.
- CR-63: `construction.valuation.target` (obra y mes; monto calculado,
  propuesto y aprobado; estado; quién propuso y aprobó, cuándo). El monto
  calculado es la suma de las valorizaciones previstas con corte en el mes ×
  (venta ÷ partidas), así que las metas de la obra cierran en la venta. «Metas
  de valorización» en la pestaña «Calendario e ingresos» de la obra crea una
  meta por mes y abre la lista; «Proponer meta del mes» (planificador) pide la
  aprobación por niveles (OCA); la regla por defecto es un nivel, la jefatura
  de proyectos. Una meta aprobada que se vuelve a proponer queda «Propuesta» y
  vale la anterior hasta la nueva aprobación; el historial queda en el
  chatter. «Vencimiento de la meta» es un campo de la obra (días después del
  fin de mes); la acción programada diaria marca la meta vencida sin aprobar y
  manda una actividad a la jefatura.

## 5. Hecho · entrega 3 (10-nov)

- CR-60: `project.project._construction_indicators(mes, hoy, plan)` (puente
  de ventas) devuelve presupuestado y ejecutado de los cuatro bloques, valor
  ganado, CPI, SPI, costo final estimado, fin estimado (inicio + duración ÷
  SPI, días enteros hacia arriba) y el semáforo de la compañía (índices desde
  0.95 / 0.90 y margen previsto al cierre desde 10 % / 5 %, en Ajustes).
- La ficha es una acción cliente (`al_construction_planner_sale.indicator_sheet`,
  modelo `construction.project.indicators`): encabezado con la estrella, el
  cliente, las fechas, la etapa y los accesos (Cronograma valorizado,
  Valorizaciones, Análisis de control, Cambios de obra); los bloques
  presupuestado contra ejecutado (componente común del núcleo,
  `core/indicator_blocks`), con «Costo meta / costo final estimado» en «Al
  cierre»; seguimiento (facturado, cobrado, por cobrar, comprometido, por
  gastar, índices); línea de plazo; gráfico «Avance físico contra valorizado»
  (línea semanal, escalones por corte, valorización presupuestada punteada y
  el «por valorizar» de hoy marcado); curva S de costo; tablas de
  valorizaciones, especialidades y cambios, que abren su documento. Se abre
  desde «Calendario e ingresos» de la obra y desde la cartera.
- Sin «Ve montos» la ficha llega sin soles: avance, valorizado %, índices y
  plazo.

## 6. Hecho · entrega 4 (10-nov)

- CR-59: el Inicio muestra la cartera. Cada obra trae su etapa
  (`_construction_portfolio_stage`: en planificación, en ejecución, postventa
  con el plan cerrado), favorita, cliente, fechas, «mis obras» y los
  indicadores del puente de ventas. Pestañas con su cantidad, filtros
  «★ Favoritas», «Mis obras» y «En rojo», selector de mes, «⇅ Ordenar» (más
  atrasadas, mayor facturación, mayor venta, mayor por valorizar, menor
  margen, fecha de inicio, fin más próximo), favoritas siempre primero; el
  orden se recuerda por usuario en el navegador. Total de la cartera en
  tarjetas sobre la tabla (respeta pestaña y filtros), tabla con dos filas por
  obra y pie con la unidad y la regla del color; la ayuda de cada columna dice
  su cálculo. Tocar la obra abre su ficha.
- Rendimiento: los indicadores del mes en curso se guardan en la obra
  (`construction_indicators_cache`). La acción programada diaria los
  recalcula; confirmar una valorización, publicar un asiento con la analítica
  de la obra o aprobar una meta los marcan para recalcular al abrir el Inicio.
  Otro mes se calcula al pedirlo.
- CR-65: cada pendiente tiene área (`_pending_areas`; los puentes agregan las
  suyas) y el rol que lo atiende. El panel muestra el total del día en el
  título, cada área con su total y su franja de color, y pliega en una línea
  gris los pendientes en 0. Un pendiente sin área cae en «Otros».

## 7. Diferencias frente al requerimiento

- CR-59: «Postventa» es el plan cerrado; la aplicación no tiene tickets de
  postventa y el fondo de garantía de contratas es una deuda con el
  subcontratista, no un cobro al cliente. Queda el gancho
  `_construction_in_postsale` para el puente que los agregue.
- CR-59: el orden elegido se guarda en el navegador del usuario, no en el
  servidor.
- CR-60: el índice de costo por especialidad compara el valor ganado con lo
  ejecutado valorizado al costo del plan: la contabilidad no separa el costo
  por especialidad.
- CR-60: el semáforo del margen usa el margen previsto al cierre.

- CR-62 va en el puente de ventas (`al_construction_planner_sale`) y no en el
  núcleo: el núcleo depende solo de `analytic`, y el costo se separa por el
  tipo de la cuenta contable, que es de Contabilidad. Todas las bases con obras
  tienen el puente de ventas.
- Los indicadores de la entrega 1 se calculan al leerlos; guardarlos por obra
  y recalcularlos con la acción programada va con la cartera (entrega 4), que
  es quien los necesita en lote.
- CR-63: la meta vive en su propia lista (desde la obra y el menú Ingresos)
  y no en una pestaña del Cronograma valorizado: el Cronograma es una pantalla
  de solo lectura en OWL y la meta necesita su formulario, su aprobación y su
  historial.
- CR-64: anular un cambio aprobado sigue sin permitirse (ya entró al plan); el
  cambio cobrable se corrige con otro cambio, que agrega su línea en negativo.
  La línea de venta del cambio no se reparte entre partidas del plan.
- CR-62: el «Ingreso contable» y el «Costo contable» de la pestaña
  «Planificación» de la obra usan la misma regla (tipo de cuenta, sin las
  excluidas); antes eran los apuntes positivos y negativos de la analítica,
  con las cuentas de balance mezcladas.
- CR-59 y CR-60: con una obra sin orden del contrato (sin partidas) o con el
  plan sin aprobar, el CPI y el SPI quedan vacíos y no cuentan para el
  semáforo: no hay valor ganado que medir.
- CR-60: el avance físico del gráfico es semanal (un punto por semana, como
  mucho 40), no diario. Los puntos pasados se guardan en la obra y los
  recalcula la acción programada diaria; un avance validado con fecha
  atrasada aparece en el gráfico al día siguiente.

## 8. Verificación en las bases de desarrollo (10-nov)

Con las obras existentes, sin guardar cambios (consola con `rollback`):

- creval-dev: 7 obras con plan. La cartera abre en 0.8 s con los
  indicadores guardados (5.7 s la primera vez del día, que hace la acción
  programada). Pendientes: 19 en el título y 9 en Compras, como el criterio
  de aceptación de CR-65. La ficha de cada obra revisada da las mismas cifras
  que su fila de la cartera.
- newallcenter-dev: 6 obras con plan y 120 sin plan; la cartera abre en 2.5 s.
  La ficha de la obra más grande (5 393 líneas de plan) tardaba 20 s por el
  gráfico de avance (17 s): con los puntos guardados queda en el cálculo de
  los indicadores (unos 2 s).
- Hallazgo corregido: las obras sin orden del contrato salían en rojo con
  CPI y SPI en 0.

## 9. Tabla final

| Código | Commit | Versión | Pruebas (`test_creval_package7.py` y otras) | Diferencias |
|---|---|---|---|---|
| CR-59 | 27da7cc2 y el de esta corrección | planner 78, sale 26 | `test_portfolio_*`, `test_indicators_are_marked_stale`, recorrido `al_construction_planner_portfolio` | Postventa = plan cerrado; orden en el navegador |
| CR-60 | ídem | sale 26 | `test_indicators_budget_and_executed`, `test_estimated_end_from_the_schedule_index`, `test_indicator_sheet_*`, `test_progress_points_are_stored`, `test_indices_need_partidas`, recorrido `al_construction_planner_indicator_sheet` | Índice por especialidad contra el costo del plan; avance semanal |
| CR-61 | 27da7cc2 | sale 25 | `test_physical_progress_uses_the_valuation_rule`, `test_new_sites_default_to_valued_progress` | — |
| CR-62 | 27da7cc2 | sale 25 | `test_cost_and_income_from_accounting`, `TestPlanningTabV15` | En el puente de ventas; la pestaña «Planificación» usa la misma regla |
| CR-63 | 27da7cc2 | sale 25 | `test_month_targets_close_on_the_sale`, `test_target_approval_by_the_project_head` | Lista propia, no pestaña del Cronograma |
| CR-64 | 27da7cc2 | sale 25 | `test_billable_change_goes_to_the_sale`, `test_rework_is_not_billable` | Un cambio aprobado no se anula: se corrige con otro |
| CR-65 | 27da7cc2 | planner 78 | `test_pending_by_area` | — |

