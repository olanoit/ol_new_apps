# -*- coding: utf-8 -*-
{
    'name': 'Planificación de obra: cuadrillas propias (AL)',
    'summary': 'Asignar cuadrilla con turnos de Planificación y horas de la hoja de horas como real.',
    'description': """
Planificación de obra: cuadrillas propias
=========================================
Puente del planificador de obra (paquete 1.7, M17-07): el núcleo
(al_construction_planner) solo depende de Proyectos, el Gantt de la suite y
las aprobaciones por niveles; cada función que opera en otra aplicación de
Odoo vive en su puente y se activa desde Ajustes.

Asignar cuadrilla con turnos de Planificación y horas de la hoja de horas como real.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    'icon': '/al_construction_planner/static/description/icon.png',
    'version': '1.20261013',
    # LGPL-3 como el planificador del que depende (base_tier_validation es AGPL).
    'license': 'LGPL-3',
    'depends': ['al_construction_planner', 'project_forecast', 'hr_timesheet'],
    'data': [
        'security/ir.model.access.csv',
        'wizards/plan_crew_wizard_views.xml',
        'views/crew_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
