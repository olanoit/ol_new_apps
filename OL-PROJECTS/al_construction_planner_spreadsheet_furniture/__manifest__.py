# -*- coding: utf-8 -*-
{
    'name': 'Hoja de trabajo del planificador: mobiliario (AL)',
    'summary': 'Maestro de mobiliario (tipologías, muebles, módulos, piezas, BOM) en la hoja de '
               'trabajo de la obra, con «Enviar al planificador» al importador del maestro y ETO.',
    'description': """
Hoja de trabajo del planificador: mobiliario
============================================
Puente entre la hoja de trabajo del planificador (al_construction_planner_spreadsheet)
y la vertical Mobiliario (v1.5, M15-15; plantilla del piloto en la v1.8, M18-22):
en las obras de mobiliario la hoja de trabajo es el maestro de planificación
(árbol, tipologías, muebles, módulos, piezas, BOM y tarifas) y «Enviar al
planificador» lo lleva al asistente «Importar maestro y ETO».

Se instala solo con la hoja de trabajo y el planificador de mobiliario. Desde
el requerimiento CREVAL v1.0 (6.7) la hoja genérica es la del presupuesto y
el plan de construcción.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    'icon': '/al_construction_planner_spreadsheet_furniture/static/description/icon.png',
    'version': '2.20261027',
    'license': 'LGPL-3',
    'countries': ['pe'],
    'depends': ['al_construction_planner_spreadsheet', 'al_construction_planner_furniture'],
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': True,
}
