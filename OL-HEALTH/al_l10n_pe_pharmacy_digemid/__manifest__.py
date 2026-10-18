# -*- coding: utf-8 -*-
{
    'name': 'PE - Farmacia: DIGEMID, genéricos e IGV (AL)',
    'summary': 'Precios para el Observatorio de DIGEMID, cumplimiento del 30 % de genéricos (Ley '
               '32033), lista de precios por DCI, reacciones adversas para NotiMED e IGV exonerado '
               'de medicamentos oncológicos, para VIH y para diabetes.',
    'description': """
PE - Farmacia: DIGEMID, genéricos e IGV
=======================================
Entrega E3 del plan (docs/farmacia/PLAN_FARMACIA.md):

* Código DIGEMID del producto y precios para el Observatorio Peruano de
  Productos Farmacéuticos: cada cambio de precio queda pendiente de informar
  hasta que se exporta el archivo (columnas ajustables a la plantilla
  vigente).
* Listado de genéricos esenciales del MINSA (importable) y cumplimiento del
  30 % por ítem en el local (Ley 32033); microempresas exceptuadas.
* Lista de precios por DCI de menor a mayor, con el aviso de empresas
  vinculadas.
* Sospechas de reacciones adversas con su plazo (graves 24 h) para notificar
  en NotiMED; quedan en el libro de ocurrencias.
* Régimen del IGV: exonerado para las listas de las leyes 27450 y 28553.
* Datos del establecimiento: tipo (farmacia o botica) y autorización
  sanitaria.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-HEALTH/Apps',
    'icon': '/al_pharmacy_base/static/description/icon.png',
    'version': '2.20261018',
    'license': 'OPL-1',
    'depends': ['al_pharmacy_stock', 'l10n_pe', 'account', 'al_report_base'],
    'data': [
        'security/ir.model.access.csv',
        'security/digemid_security.xml',
        'data/digemid_data.xml',
        'views/digemid_views.xml',
        'report/price_list_report.xml',
    ],
    'demo': ['demo/digemid_demo.xml'],
    'installable': True,
    'application': False,
}
