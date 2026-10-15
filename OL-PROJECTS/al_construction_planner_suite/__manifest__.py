# -*- coding: utf-8 -*-
{
    'name': 'Planificación de obra: todos los puentes (AL)',
    'summary': 'Instala el planificador con todos sus puentes (perfil mobiliario completo) y reúne las pruebas de integración.',
    'description': """
Planificación de obra: todos los puentes
========================================
Puente del planificador de obra (paquete 1.7, M17-07): el núcleo
(al_construction_planner) solo depende de Proyectos, el Gantt de la suite y
las aprobaciones por niveles; cada función que opera en otra aplicación de
Odoo vive en su puente y se activa desde Ajustes.

Instala el planificador con todos sus puentes (perfil mobiliario completo) y reúne las pruebas de integración.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    'icon': '/al_construction_planner/static/description/icon.png',
    'version': '1.20261013',
    # LGPL-3 como el planificador del que depende (base_tier_validation es AGPL).
    'license': 'LGPL-3',
    'depends': ['al_construction_planner_furniture', 'al_construction_planner_purchase', 'al_construction_planner_subcontract', 'al_construction_planner_subcontract_purchase', 'al_construction_planner_crew', 'al_construction_planner_budget', 'al_construction_planner_sale'],
    'data': [
    ],
    'demo': [
        'demo/planner_demo.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
