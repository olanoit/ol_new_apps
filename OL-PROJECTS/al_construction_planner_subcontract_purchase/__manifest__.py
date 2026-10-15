# -*- coding: utf-8 -*-
{
    'name': 'Planificación de obra: contratas y compras (AL)',
    'summary': 'Descuento a la contrata del material extra en su liquidación semanal.',
    'description': """
Planificación de obra: contratas y compras
==========================================
Puente del planificador de obra (paquete 1.7, M17-07): el núcleo
(al_construction_planner) solo depende de Proyectos, el Gantt de la suite y
las aprobaciones por niveles; cada función que opera en otra aplicación de
Odoo vive en su puente y se activa desde Ajustes.

Descuento a la contrata del material extra en su liquidación semanal.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    'icon': '/al_construction_planner/static/description/icon.png',
    'version': '1.20261013',
    # LGPL-3 como el planificador del que depende (base_tier_validation es AGPL).
    'license': 'LGPL-3',
    'depends': ['al_construction_planner_subcontract', 'al_construction_planner_purchase'],
    'data': [
        'views/discount_views.xml',
        'views/portal_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
}
