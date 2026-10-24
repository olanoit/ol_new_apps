# -*- coding: utf-8 -*-
{
    'name': 'Planificación de obra: compras y abastecimiento (AL)',
    'summary': 'Compra masiva, requerimiento de obra, abastecimiento de la obra, precios de compra, crear producto y material extra.',
    'description': """
Planificación de obra: compras y abastecimiento
===============================================
Puente del planificador de obra (paquete 1.7, M17-07): el núcleo
(al_construction_planner) solo depende de Proyectos, el Gantt de la suite y
las aprobaciones por niveles; cada función que opera en otra aplicación de
Odoo vive en su puente y se activa desde Ajustes.

Compra masiva, requerimiento de obra, abastecimiento de la obra, precios de compra, crear producto y material extra.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    'icon': '/al_construction_planner/static/description/icon.png',
    'version': '13.20261024',
    # LGPL-3 como el planificador del que depende (base_tier_validation es AGPL).
    'license': 'LGPL-3',
    'depends': ['al_construction_planner', 'al_construction_material_request', 'purchase_request'],
    'data': [
        'views/exceed_wizard_views.xml',
        'security/planner_groups.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'data/tier_definition_data.xml',
        'wizards/plan_price_wizard_views.xml',
        'wizards/plan_supply_wizard_views.xml',
        'views/construction_price_views.xml',
        'views/construction_supply_views.xml',
        'views/plan_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
        'views/material_request_scope_views.xml',
        'views/construction_board_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'al_construction_planner_purchase/static/src/supply_board/*',
            ('remove', 'al_construction_planner_purchase/static/src/**/*.dark.scss'),
        ],
        'web.assets_web_dark': [
            'al_construction_planner_purchase/static/src/**/*.dark.scss',
        ],
        'web.assets_tests': [
            'al_construction_planner_purchase/static/tests/tours/*',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
