# -*- coding: utf-8 -*-
{
    'name': 'Planificación de obra: cuadrillas propias (AL)',
    'summary': 'Asignar cuadrilla con turnos de Planificación, en horas o en días con costo '
               'diario por puesto, y horas de la hoja de horas como real.',
    'description': """
Planificación de obra: cuadrillas propias
=========================================
Puente del planificador de obra (paquete 1.7, M17-07): el núcleo
(al_construction_planner) solo depende de Proyectos, el Gantt de la suite y
las aprobaciones por niveles; cada función que opera en otra aplicación de
Odoo vive en su puente y se activa desde Ajustes.

Asignar cuadrilla con turnos de Planificación y horas de la hoja de horas como real.

Paquete 1.8 (M18-06 y M18-07): roles de cuadrilla con puesto y costo de
referencia por jornal, cuadrillas planificadas en jornales (hora, medio día o
día completo, con el redondeo de la nómina) y el análisis de jornales y soles
planificados contra ejecutados por obra, etapa y sub etapa.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    'icon': '/al_construction_planner/static/description/icon.png',
    'version': '4.20261016',
    # LGPL-3 como el planificador del que depende (base_tier_validation es AGPL).
    'license': 'LGPL-3',
    'depends': ['al_construction_planner', 'project_forecast', 'hr_timesheet'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'wizards/plan_crew_wizard_views.xml',
        'views/crew_views.xml',
        'views/crew_day_views.xml',
        'views/construction_board_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
