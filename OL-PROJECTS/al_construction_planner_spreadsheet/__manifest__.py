# -*- coding: utf-8 -*-
{
    'name': 'Hoja de trabajo del planificador de obra (AL)',
    'summary': 'Maestro de planificación de la obra como hoja de cálculo de Documentos, con '
               'listas de Odoo de referencia y el menú «Enviar al planificador».',
    'description': """
Hoja de trabajo del planificador de obra
========================================
v1.5, fase 21 (M15-15). El maestro de planificación (árbol, tipologías,
muebles, módulos, actividades, BOM, ETO y variantes) se llena en una hoja de
cálculo de Odoo en lugar de un Excel suelto:

* **Hoja de trabajo de la obra**: el botón de la pestaña «Planificación» crea
  (o abre) la hoja de la obra en Documentos, con una pestaña por hoja del
  maestro y sus encabezados, y una pestaña REFERENCIAS con listas de Odoo
  vivas de las actividades y de las tipologías de la obra.
* **Enviar al planificador**: menú Archivo de la hoja; lleva las pestañas del
  maestro al asistente «Importar maestro y ETO», que muestra lo que se creará,
  las advertencias y los errores con su hoja y su fila, antes de escribir.

Requiere Documentos y Hoja de cálculo (Odoo Enterprise); se instala solo
cuando están el planificador y Documentos.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    'icon': '/al_construction_planner/static/description/icon.png',
    'version': '1.20261013',
    # LGPL-3 como el planificador del que depende (base_tier_validation es AGPL).
    'license': 'LGPL-3',
    'countries': ['pe'],
    'depends': ['al_construction_planner_furniture', 'documents_spreadsheet'],
    'data': [
        'views/project_views.xml',
    ],
    'assets': {
        'spreadsheet.o_spreadsheet': [
            'al_construction_planner_spreadsheet/static/src/**/*.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': True,
}
