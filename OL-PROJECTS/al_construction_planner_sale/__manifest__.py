# -*- coding: utf-8 -*-
{
    'name': 'Planificación de obra: valorización e ingresos (AL)',
    'summary': 'Calendario e ingresos, contratos de obra con hitos, entrega semanal, valorización, cobranza y cronograma valorizado.',
    'description': """
Planificación de obra: valorización e ingresos
==============================================
Puente del planificador de obra (paquete 1.7, M17-07): el núcleo
(al_construction_planner) solo depende de Proyectos, el Gantt de la suite y
las aprobaciones por niveles; cada función que opera en otra aplicación de
Odoo vive en su puente y se activa desde Ajustes.

Calendario e ingresos, contratos de obra con hitos, entrega semanal, valorización, cobranza y cronograma valorizado.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    'icon': '/al_construction_planner/static/description/icon.png',
    'version': '9.20261016',
    # LGPL-3 como el planificador del que depende (base_tier_validation es AGPL).
    'license': 'LGPL-3',
    'depends': ['al_construction_planner', 'sale_project', 'al_report_base'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'data/mail_message_subtype_data.xml',
        'data/construction_milestone_template_data.xml',
        'report/construction_valuation_report.xml',
        'wizards/valuation_wizard_views.xml',
        'views/construction_income_views.xml',
        'views/construction_schedule_report_views.xml',
        'views/construction_contract_views.xml',
        'views/construction_change_views.xml',
        'views/sale_order_views.xml',
        'views/project_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
        'views/construction_board_views.xml',
        'views/budget_import_views.xml',
        'wizards/budget_book_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'al_construction_planner_sale/static/src/schedule_report/*',
            ('remove', 'al_construction_planner_sale/static/src/**/*.dark.scss'),
        ],
        'web.assets_web_dark': [
            'al_construction_planner_sale/static/src/**/*.dark.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
