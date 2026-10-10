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

Especificación: docs/planificador/ESPECIFICACION_v1.4.md. Diseño técnico y
plan por fases: docs/planificador/DISENO_TECNICO.md.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    # Ícono nativo de la app a la que pertenece; el menú raíz lleva el propio.
    'icon': '/al_construction_planner/static/description/icon.png',
    'version': '1.20261010',
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
        'sale_management',
    ],
    'data': [
        'security/planner_groups.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'data/ir_sequence_data.xml',
        'wizards/plan_generate_wizard_views.xml',
        'views/construction_labor_views.xml',
        'views/construction_typology_views.xml',
        'views/construction_resource_plan_views.xml',
        'views/project_views.xml',
        'views/mrp_bom_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
