# -*- coding: utf-8 -*-
{
    'name': 'Hoja de trabajo del planificador de obra (AL)',
    'summary': 'Presupuesto, APU y plan de la obra en una hoja de cálculo de Documentos, con '
               'las hojas del libro de carga, validación, «Enviar al planificador» y versiones.',
    'description': """
Hoja de trabajo del planificador de obra
========================================
Requerimiento CREVAL v1.0, 6.7. El presupuestador y la oficina técnica trabajan
el presupuesto, los APU y el plan en una hoja de cálculo de Odoo (Documentos)
con las mismas hojas y columnas del libro de carga (6.6):

* **Hoja de trabajo**: desde la cotización (carpeta Presupuestos › cotización)
  o desde la obra; la obra que viene de una cotización con hoja usa la misma.
  Nace con las pestañas OBRA, INSUMOS, APU, APU_DETALLE, PRESUPUESTO, PLAN,
  LISTAS, REFERENCIAS (listas vivas de Odoo) y ERRORES, y con lo que ya tiene
  la cotización.
* **Menú Planificación de obra**: Validar plantilla (los errores en ERRORES con
  su hoja, fila y columna), Enviar al planificador (destino presupuesto o
  presupuesto y plan, con la revisión del asistente del libro), Actualizar
  insumos (costo vigente del maestro), Traer de Odoo y Nueva versión (copia
  numerada en la misma carpeta, con el enlace en el historial).

Las obras de mobiliario llenan su maestro con el puente
al_construction_planner_spreadsheet_furniture. Requiere Documentos y Hoja de
cálculo (Odoo Enterprise); se instala solo con el puente de ventas del
planificador y Documentos.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    'icon': '/al_construction_planner/static/description/icon.png',
    'version': '5.20261016',
    # LGPL-3 como el planificador del que depende (base_tier_validation es AGPL).
    'license': 'LGPL-3',
    'countries': ['pe'],
    'depends': ['al_construction_planner_sale', 'documents_spreadsheet'],
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
