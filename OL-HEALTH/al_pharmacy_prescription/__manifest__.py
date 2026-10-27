# -*- coding: utf-8 -*-
{
    'name': 'Farmacia: receta y dispensación (AL)',
    'summary': 'Receta médica con prescriptor y paciente, dispensación parcial y alternativas, '
               'retención con folio, alergias del paciente, libro de recetas y etiqueta de '
               'dispensación.',
    'description': """
Farmacia: receta y dispensación
===============================
Entrega E2 del plan (docs/farmacia/PLAN_FARMACIA.md), según el Manual BPOF
(RM 554-2022/MINSA, 7.5.2):

* Prescriptor (profesión, colegiatura, especialidad, estado) y paciente
  (fecha de nacimiento, alergias y condiciones crónicas, solo para el
  químico farmacéutico).
* Receta común o especial con vigencia, imagen, medicamentos por producto o
  por DCI con posología; estados vigente, dispensada en parte, dispensada,
  vencida y anulada.
* Dispensación contra la línea de la receta: equivalentes y DCI, entregas
  parciales, alternativa entregada, lote, químico farmacéutico y adquiriente.
* Libro de recetas en PDF y etiqueta de dispensación o fraccionado.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-HEALTH/Apps',
    'icon': '/al_pharmacy_prescription/static/description/icon.png',
    'version': '4.20261027',
    'license': 'OPL-1',
    'depends': ['al_pharmacy_base', 'contacts', 'al_report_base'],
    'data': [
        'security/ir.model.access.csv',
        'security/pharmacy_prescription_security.xml',
        'data/pharmacy_prescription_data.xml',
        'views/pharmacy_prescription_views.xml',
        'report/pharmacy_prescription_reports.xml',
    ],
    'demo': ['demo/pharmacy_prescription_demo.xml'],
    'installable': True,
    'application': False,
}
