# -*- coding: utf-8 -*-
{
    'name': 'Planificación de obra: contratas (AL)',
    'summary': 'Asignar contrata con su OC de servicio, avance por driver, liquidación semanal y portal de la contrata.',
    'description': """
Planificación de obra: contratas
================================
Puente del planificador de obra (paquete 1.7, M17-07): el núcleo
(al_construction_planner) solo depende de Proyectos, el Gantt de la suite y
las aprobaciones por niveles; cada función que opera en otra aplicación de
Odoo vive en su puente y se activa desde Ajustes.

Asignar contrata con su OC de servicio, avance por driver, liquidación semanal y portal de la contrata.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    'icon': '/al_construction_planner/static/description/icon.png',
    'version': '13.20261016',
    # LGPL-3 como el planificador del que depende (base_tier_validation es AGPL).
    'license': 'LGPL-3',
    'depends': ['al_construction_planner', 'purchase', 'portal', 'al_report_base'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'data/tier_definition_data.xml',
        'data/construction_contract_data.xml',
        'report/construction_valuation_report.xml',
        'wizards/plan_contract_wizard_views.xml',
        'views/construction_settlement_views.xml',
        'views/construction_condition_views.xml',
        'views/construction_deduction_views.xml',
        'views/construction_valuation_views.xml',
        'views/purchase_order_terms_views.xml',
        'views/opening_import_wizard_views.xml',
        'views/construction_contract_report_views.xml',
        'views/progress_views.xml',
        'views/plan_views.xml',
        'views/project_views.xml',
        'views/res_config_settings_views.xml',
        'views/account_move_views.xml',
        'views/portal_templates.xml',
        'views/menus.xml',
        'views/construction_board_views.xml',
    ],
    'assets': {
        # Portal de obra: ubicación del celular al registrar el avance.
        'web.assets_frontend': [
            'al_construction_planner_subcontract/static/src/portal/construction_portal.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
