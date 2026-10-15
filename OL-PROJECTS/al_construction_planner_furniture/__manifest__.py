# -*- coding: utf-8 -*-
{
    'name': 'Planificación de obra: rubro mobiliario (AL)',
    'summary': 'Tipologías de mueble con módulos, metros lineales y lista de materiales, generar plan desde la tipología e importación del maestro y del ETO.',
    'description': """
Planificación de obra: rubro mobiliario
=======================================
Puente del planificador de obra (paquete 1.7, M17-07): el núcleo
(al_construction_planner) solo depende de Proyectos, el Gantt de la suite y
las aprobaciones por niveles; cada función que opera en otra aplicación de
Odoo vive en su puente y se activa desde Ajustes.

Tipologías de mueble con módulos, metros lineales y lista de materiales, generar plan desde la tipología e importación del maestro y del ETO.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    'icon': '/al_construction_planner/static/description/icon.png',
    'version': '1.20261013',
    # LGPL-3 como el planificador del que depende (base_tier_validation es AGPL).
    'license': 'LGPL-3',
    'depends': ['al_construction_planner_mrp'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'wizards/plan_generate_wizard_views.xml',
        'wizards/master_import_wizard_views.xml',
        'views/construction_typology_views.xml',
        'views/plan_views.xml',
        'views/project_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
