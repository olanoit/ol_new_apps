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
* Formato de la Directiva 176-MINSA/DIGEMID: hoja «Hoja1» con CodEstab
  (texto), CodProd, Precio 1 (empaque) y Precio 2 (unidad), con IGV y 2
  decimales; solo medicamentos y productos biológicos en oferta y con stock
  del local (clase DIGEMID del producto).
* Envíos por local y mes: la primera carga del mes es completa (reemplaza la
  lista), las siguientes solo con los cambios desde la última carga; plazo de
  rectificación de 7 días hábiles; recordatorio mensual al director técnico
  si el local no informó.
* Listado de genéricos esenciales del MINSA (importable) y cumplimiento del
  30 % por ítem en el local (Ley 32033); microempresas exceptuadas.
* Lista de precios por DCI de menor a mayor, con el aviso de empresas
  vinculadas.
* Cartel A4 de los productos de empresas vinculadas para exhibir en el local
  (DS 020-2024-SA, art. 32-B).
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
    'icon': '/al_l10n_pe_pharmacy_digemid/static/description/icon.png',
    'version': '6.20261027',
    'license': 'OPL-1',
    # resource: feriados del calendario laboral para el plazo de rectificación.
    'depends': ['al_pharmacy_stock', 'l10n_pe', 'account', 'resource', 'al_report_base'],
    'data': [
        'data/digemid_data.xml',
        'views/digemid_views.xml',
        'report/price_list_report.xml',
        'security/ir.access.csv',
    ],
    'demo': ['demo/digemid_demo.xml'],
    'installable': True,
    'application': False,
}
