# -*- coding: utf-8 -*-
{
    'name': 'Planificación de obra: presupuesto y control (AL)',
    'summary': 'Presupuesto analítico al aprobar el plan y control de la OC contra el presupuesto.',
    'description': """
Planificación de obra: presupuesto y control
============================================
Puente del planificador de obra (paquete 1.7, M17-07): el núcleo
(al_construction_planner) solo depende de Proyectos, el Gantt de la suite y
las aprobaciones por niveles; cada función que opera en otra aplicación de
Odoo vive en su puente y se activa desde Ajustes.

Presupuesto analítico al aprobar el plan y control de la OC contra el presupuesto.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    'icon': '/al_construction_planner_budget/static/description/icon.png',
    'version': '5.20261027',
    # LGPL-3 como el planificador del que depende (base_tier_validation es AGPL).
    'license': 'LGPL-3',
    'depends': ['al_construction_planner', 'account_budget_purchase'],
    'data': [
        'views/exceed_wizard_views.xml',
        'views/budget_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
