# -*- coding: utf-8 -*-
{
    'name': 'Planificación de obra: producción (AL)',
    'summary': 'Órdenes de fabricación desde el plan, etapa de consumo en la lista de materiales y espera del metrado.',
    'description': """
Planificación de obra: producción
=================================
Puente del planificador de obra (paquete 1.7, M17-07): el núcleo
(al_construction_planner) solo depende de Proyectos, el Gantt de la suite y
las aprobaciones por niveles; cada función que opera en otra aplicación de
Odoo vive en su puente y se activa desde Ajustes.

Órdenes de fabricación desde el plan, etapa de consumo en la lista de materiales y espera del metrado.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    'icon': '/al_construction_planner/static/description/icon.png',
    'version': '9.20261023',
    # LGPL-3 como el planificador del que depende (base_tier_validation es AGPL).
    'license': 'LGPL-3',
    # al_stock_base: regla de las planchas enteras (paquete 1.11, M111-12).
    'depends': ['al_construction_planner', 'project_mrp', 'al_stock_base'],
    'data': [
        'views/exceed_wizard_views.xml',
        'security/planner_groups.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'wizards/plan_production_wizard_views.xml',
        'views/construction_stage_views.xml',
        'views/construction_production_reason_views.xml',
        'views/mrp_bom_views.xml',
        'views/mrp_production_views.xml',
        'views/whole_sheet_views.xml',
        'data/remnant_data.xml',
        'views/remnant_views.xml',
        'views/plan_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}
