# -*- coding: utf-8 -*-
{
    'name': 'Planificación de obra: contratas y ventas (AL)',
    'summary': 'Adicionales de la contrata desde el cambio de obra y margen de compra por partida.',
    'description': """
Planificación de obra: contratas y ventas
=========================================
Puente del planificador de obra (paquete 1.7, M17-07): el núcleo
(al_construction_planner) solo depende de Proyectos, el Gantt de la suite y
las aprobaciones por niveles; cada función que opera en otra aplicación de
Odoo vive en su puente y se activa desde Ajustes.

Requerimiento CREVAL v1.0 (3.9 y 3.13): «Agregar a la orden de contrata»
desde el cambio de obra aprobado y el margen de compra por partida.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    'icon': '/al_construction_planner/static/description/icon.png',
    'version': '1.20261023',
    # LGPL-3 como el planificador del que depende (base_tier_validation es AGPL).
    'license': 'LGPL-3',
    'depends': ['al_construction_planner_subcontract', 'al_construction_planner_sale'],
    'data': [
        'views/construction_change_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
}
