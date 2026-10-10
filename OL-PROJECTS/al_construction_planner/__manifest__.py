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

Especificación: docs/planificador/ESPECIFICACION_v1.4.md. Diseño técnico y
plan por fases: docs/planificador/DISENO_TECNICO.md.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    # Ícono nativo de la app a la que pertenece; el menú raíz lleva el propio.
    'icon': '/al_construction_planner/static/description/icon.png',
    'version': '6.20261010',
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
        'wizards/plan_generate_wizard_views.xml',
        'wizards/plan_replan_wizard_views.xml',
        'wizards/plan_price_wizard_views.xml',
        'wizards/plan_supply_wizard_views.xml',
        'wizards/plan_contract_wizard_views.xml',
        'wizards/plan_crew_wizard_views.xml',
        'views/construction_labor_views.xml',
        'views/construction_typology_views.xml',
        'views/construction_progress_views.xml',
        'views/construction_resource_plan_views.xml',
        'views/construction_settlement_views.xml',
        'views/project_views.xml',
        'views/res_config_settings_views.xml',
        'views/mrp_bom_views.xml',
        'views/construction_plan_tree_views.xml',
        'views/construction_supply_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/planner_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'al_construction_planner/static/src/plan_tree/*',
        ],
        'web.assets_tests': [
            'al_construction_planner/static/tests/tours/*',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
