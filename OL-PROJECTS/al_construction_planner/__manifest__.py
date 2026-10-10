# -*- coding: utf-8 -*-
{
    'name': 'Planificación de obra (AL)',
    'summary': 'Plan de recursos por obra, piso, departamento, ambiente y módulo: '
               'materiales, contratas a destajo, personal propio y producción, '
               'generado desde las tipologías de la obra.',
    'description': """
Planificación de obra
=====================
Aplicación «Planificación de obra», construida sobre el Gantt de proyectos de
la suite, para planificar módulo por módulo todo lo que la obra va a consumir.

Fase 1 (jerarquía y catálogo):

* Jerarquía de la obra en las tareas: piso › departamento › ambiente › módulo,
  con los ancestros de cada nivel calculados.
* Tipologías por obra con sus módulos, actividades por ambiente y lista de
  materiales con la etapa de consumo de cada componente.
* Actividades de contrata (driver de pago) y tarifas por obra y contrata con
  vigencia.
* Plan de recursos versionado y asistente «Generar plan» que crea las tareas de
  módulo y las líneas de armado, contrata y material desde las tipologías.

Fase 2 (árbol del plan, P-02):

* «Árbol de recursos»: obra › piso › departamento › ambiente › módulo cargado
  por niveles, con módulos, ML, material, contrata y total acumulados en el
  servidor.
* Selección en cascada con barra de resumen, panel de recursos acumulados de
  la selección y filtros por etapa, tipo de recurso, estado y contrata.

Fase 3 (línea base, P-03):

* Flujo del plan: borrador › en aprobación › aprobado › en ejecución ›
  cerrado, con reemplazado y cancelado. «Solicitar aprobación» se bloquea
  con líneas sin etapa, sin costo o contratas sin actividad (y las lista).
* Aprobación por niveles con base_tier_validation (reglas por monto).
* Al aprobar: presupuesto analítico con una línea por combinación de cuentas
  analíticas, montos congelados en las líneas y la versión anterior pasa a
  «Reemplazado» con su presupuesto revisado.
* «Nueva versión» (W-09): copia todo o solo saldos, con motivo obligatorio y
  la línea anterior enlazada.
* «Aplicar costo» (W-12): costo que escribe el planificador con su base
  (manual, último precio, ponderado de 3 o 6 meses) y la fecha de la base.
* Resumen por etapa (P-03), análisis en pivote y gráfico, cierre del plan.

Fase 4 (asignaciones y compras, P-10 y P-11):

* Asignaciones del plan: qué parte de cada documento (compra masiva,
  requerimiento de obra, OF, OC de servicio, turno) corresponde a cada línea;
  lo hecho se reparte por fecha de necesidad y su estado sigue al documento.
* Pedido, comprado, despachado, consumido, saldo, comprometido, real y estado
  de cada línea (excedida, completa, en compra, parcial, planificada).
* Compra masiva (W-02) en dos modos: con analítica de la obra o stock general
  (descuenta lo libre en el central y lo que ya viene en compras), redondeada
  a la unidad de compra.
* Requerimiento de obra (W-03) agrupado por ambiente, departamento o piso, con
  saldo del plan y control por línea; control de exceso al solicitar la
  aprobación según la política del plan (avisar, pedir aprobación, bloquear)
  y justificación con revisión adicional (W-10).
* Orden de fabricación (W-04) por piso o selección desde la BOM de la
  tipología, con control del saldo de producción y armado al confirmarla.
* Las asignaciones abiertas pasan a la versión nueva al aprobarla y el plan no
  se cierra con documentos abiertos.

Fase 5 (contratas, P-05 a P-07 y P-09):

* «Asignar contrata» (W-05): actividades de la selección con su driver total,
  la tarifa vigente (obra y contrata › obra › contrata › base), monto y
  retención; pone la contrata en las líneas y suma el alcance a la OC de
  servicio abierta de la contrata en la obra (una por contrata y obra).
* Avance reportado (AVN) por driver con fotos obligatorias: reportado,
  validado o rechazado con motivo; «Registrar avance» (W-07) propone el saldo
  por módulo o ambiente y no acepta más que el saldo más la tolerancia.
* «Avances por validar» (P-07) agrupado por obra, contrata y semana de
  liquidación.
* Ejecutado, liquidado y avance de cada línea; avance valorizado de cada nivel
  en el árbol y en la tarea (pestaña «Recursos y avance», P-09); el módulo
  pasa a Producido o Instalado con su avance.
* Semana de la obra configurable (inicio, día de liquidación y de pago), con
  valores por defecto en la compañía.

Fase 6 (liquidación semanal, P-08):

* Liquidación (LIQ) por contrata, obra y semana: avances validados del periodo
  más los rezagados; driver × tarifa de la OC, retención según la tarifa,
  acumulado y avance informativos.
* Acción programada diaria que prepara las liquidaciones en el día de
  liquidación de cada obra (feriados: el día hábil anterior).
* Presentar, devolver con motivo, validar y aprobación por niveles (jefatura);
  al aprobar recibe en la OC de servicio y crea la factura con vencimiento el
  día de pago; pasa a Pagada con la factura pagada.
* El plan no se cierra con liquidaciones pendientes y los avances no
  liquidados pasan a la versión nueva.

Fase 7 (control y personal propio, P-13, W-06, W-08):

* Estado y montos de control de cada línea (comprometido, real, saldo, %
  ejecutado) guardados, filtrables y agrupables; se actualizan con cada
  documento del plan y con una acción programada horaria.
* Pestaña «Control» del plan y «Análisis de control» en pivote y gráfico por
  etapa, tipo de recurso, contrata o producto.
* La OC con analítica de la obra se contrasta al confirmarla con el
  presupuesto analítico de su combinación según la política del plan (W-10).
* «Asignar cuadrilla» (W-06): turnos por obrero y semana con la tarea y la
  línea; las horas de la hoja de horas son el ejecutado y el real (costo
  hora), los turnos sin horas el comprometido.
* «Cambiar fechas» (W-08): desplaza o fija la fecha de la selección por
  etapas, recalcula la fecha de necesidad y avisa a Logística.
* Revertir un avance validado baja el estado del módulo.

Fase 8 (cronograma con recursos, P-15):

* Etapas de cada ambiente (producción, armado, instalación, acabado) con sus
  fechas, creadas al generar el plan; contrata, cuadrilla, monto y avance
  salen de las líneas.
* «Cronograma»: el Gantt de proyectos de la suite con las etapas como filas
  hijas de cada ambiente y sus vínculos, casillas de selección en cascada,
  panel con los recursos de la selección, botones de los asistentes W-02 a
  W-08 y carga semanal por contrata y etapa debajo del diagrama.
* Arrastrar una etapa desplaza la fecha de necesidad de sus líneas y avisa a
  Logística de los requerimientos y OC desfasados; «Cambiar fechas» (W-08)
  también mueve las etapas.

Fase 9 (productos, precios y abastecimiento, P-16 a P-18):

* «Precios de compra del producto» (P-16): las compras confirmadas de una
  ventana editable (6 meses) en soles, cada una al tipo de cambio de Odoo de
  su fecha de aprobación; ponderado, promedio simple, mediana, mínimo, máximo,
  desviación, último precio, medias móviles de 4 semanas y 3 meses, resumen
  por semana, mes y proveedor y gráfico semanal con las compras atípicas.
  Abre «Aplicar costo» con la base elegida.
* «Aplicar costo» (W-12) suma la media móvil de 4 semanas a sus bases.
* «Crear producto desde el plan» (W-11, P-17): código de la familia más
  correlativo asignado al guardar, productos de nombre parecido antes de
  crear, producto activo marcado con el plan y asignado a la línea, y
  actividad a Logística para completarlo.
* «Abastecimiento de la obra» (P-18): necesidad por semana de la etapa que
  consume el material, stock libre de la obra y del central, OC abiertas con
  la analítica de la obra, cantidad a comprar en la unidad de compra, costo
  del plan, último precio con alerta y compra masiva (W-02) con los
  productos marcados.
* Alertas de abastecimiento: precio sobre el plan (umbral en Ajustes),
  necesidad sin OC a menos de una semana y producto sin proveedor habitual.

Fase 10 (ruta del ingreso, P-19 a P-21):

* «Calendario e ingresos» de la obra (P-21): orden de venta del contrato,
  valorización cada n semanas o en fechas fijas, días para presentar, para
  la confirmación del cliente y para facturar, plazo de cobro, adelanto y
  fondo de garantía, con valores por defecto en Ajustes y tabla de
  valorizaciones previstas corridas al siguiente día hábil.
* Entrega semanal (P-19): una por obra y semana, preparada por la acción
  programada del día de liquidación y confirmada por la Jefatura; avance
  valorizado de cada partida con el material consumido, ingreso devengado,
  costo y margen.
* Valorización con el cliente (P-20): W-13 con las entregas confirmadas,
  envío con PDF, observaciones del cliente, conformidad obligatoria (W-14),
  lo no confirmado por valorizar y factura desde la OV al % acumulado
  confirmado, sin superar lo confirmado.

Fase 11 (cronograma valorizado e inicio, P-22 y P-01):

* «Cronograma valorizado» (P-22): por obra y semana, costo, ingreso
  devengado, margen, valorización confirmada, facturado y cobrado, en plan
  (líneas repartidas en los días hábiles de su etapa, ingreso por el avance
  previsto de cada partida y el calendario de P-21) y real (ejecutado
  valorizado, entregas y valorizaciones confirmadas, facturas publicadas y
  cobros conciliados). Curva S, fondo de garantía al cierre, exportación a
  Excel, pivote y gráfico; la última semana absorbe el redondeo.
* «Inicio» (P-01), acción por defecto de la aplicación: obras con plan,
  planificado, saldo, avance, próximo hito y estado, y «Pendientes de hoy»
  según los grupos del usuario, cada uno con su lista filtrada. El supervisor
  ve los avances y liquidaciones de sus obras (responsable o supervisor de
  obra).
* Menú «Reportes» (P-22, control de saldo y precios de compra) y «Cobranza de
  la obra» en Ingresos.

Fase 12 (importar maestro y ETO, W-15):

* «Importar maestro y ETO»: un libro Excel con las hojas del maestro de
  planificación (catálogo de actividades, tipologías, plantilla de módulos,
  actividades por ambiente, BOM con etapa de consumo y árbol de la obra) o
  solo con el ETO (código y ancho real de cada módulo). Todas las hojas son
  opcionales.
* Vista previa sin escribir nada, con conteos por hoja y advertencias: BOM
  sin etapa (con su monto en la obra), productos que no existen o sin costo,
  productos repetidos en una BOM (se suman), actividades o tipologías
  desconocidas, ambientes del ETO que no existen y cantidades con más
  decimales que la precisión de la unidad.
* Importación idempotente: volver a importar no duplica; lo que trae el libro
  de una tipología queda exactamente así. Opción para crear los productos que
  no existen; la hoja de actividades la aplica un administrador.
* «Generar plan» usa el ancho real del módulo del ETO: la instalación y la
  limpieza por ML bajan al módulo con su ancho.
* Plantilla vacía y libros de ejemplo (maestro de una obra genérica de 3
  pisos y su ETO) para descargar desde el asistente; se generan con
  tools/generar_ejemplos_importacion.py.

Especificación: docs/planificador/ESPECIFICACION_v1.4.md. Diseño técnico y
plan por fases: docs/planificador/DISENO_TECNICO.md.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    # Ícono nativo de la app a la que pertenece; el menú raíz lleva el propio.
    'icon': '/al_construction_planner/static/description/icon.png',
    'version': '11.20261011',
    # LGPL-3 y no OPL-1: depende de base_tier_validation (AGPL-3), como
    # al_construction_material_request.
    'license': 'LGPL-3',
    'depends': [
        'al_project_gantt_base',
        'al_project_gantt_backend',
        'al_construction_material_request',
        'purchase_request',
        'base_tier_validation',
        'project_mrp',
        'project_forecast',
        'hr_timesheet',
        'account_budget',
        # Comprometido de la línea de presupuesto (OC confirmadas sin facturar):
        # base del control de la OC con analítica de la obra (fase 7).
        'account_budget_purchase',
        'sale_management',
    ],
    'data': [
        'security/planner_groups.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'data/ir_sequence_data.xml',
        'data/tier_definition_data.xml',
        'data/ir_cron_data.xml',
        'data/mail_message_subtype_data.xml',
        'report/construction_valuation_report.xml',
        'wizards/plan_generate_wizard_views.xml',
        'wizards/plan_replan_wizard_views.xml',
        'wizards/plan_price_wizard_views.xml',
        'wizards/plan_supply_wizard_views.xml',
        'wizards/plan_contract_wizard_views.xml',
        'wizards/plan_crew_wizard_views.xml',
        'wizards/valuation_wizard_views.xml',
        'wizards/master_import_wizard_views.xml',
        'views/construction_labor_views.xml',
        'views/construction_typology_views.xml',
        'views/construction_progress_views.xml',
        'views/construction_resource_plan_views.xml',
        'views/construction_settlement_views.xml',
        'views/project_views.xml',
        'views/res_config_settings_views.xml',
        'views/mrp_bom_views.xml',
        'views/construction_plan_tree_views.xml',
        'views/construction_schedule_views.xml',
        'views/construction_supply_views.xml',
        'views/construction_price_views.xml',
        'views/construction_income_views.xml',
        'views/construction_schedule_report_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/planner_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'al_construction_planner/static/src/plan_tree/*',
            'al_construction_planner/static/src/schedule/*',
            'al_construction_planner/static/src/supply_board/*',
            'al_construction_planner/static/src/schedule_report/*',
            'al_construction_planner/static/src/home/*',
        ],
        'web.assets_tests': [
            'al_construction_planner/static/tests/tours/*',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
