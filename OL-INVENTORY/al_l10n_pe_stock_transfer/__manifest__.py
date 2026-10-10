# -*- coding: utf-8 -*-
{
    'name': 'PE - Traslados internos y bienes de terceros (AL)',
    'summary': 'Guía de remisión para traslados entre establecimientos (motivo 04) '
               'y control de los bienes de terceros en inventario y en la guía.',
    'description': """
Traslados internos y bienes de terceros
=======================================
* **Guía de remisión en traslados internos** entre establecimientos de la
  empresa: el botón de la guía aparece en las transferencias internas hechas
  cuando el origen y el destino son establecimientos distintos; el motivo es
  04, el destinatario es la propia empresa y los puntos de partida y llegada
  llevan su código de establecimiento anexo.
* **Bienes de terceros** (propietario nativo de Odoo, «consignación»): se ven
  en la transferencia (página Logística PE), se filtran en existencias,
  movimientos y transferencias, y el propietario va en las observaciones de la
  guía y en su representación impresa. No se valorizan ni entran al kardex
  valorizado (comportamiento nativo, sin cambios).
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-INVENTORY/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/stock/static/description/icon.png',
    'version': '1.20261010',
    'license': 'OPL-1',
    'depends': [
        'l10n_pe_edi_stock',
        'al_stock_base',
        'al_l10n_pe_delivery_guide_report',
    ],
    'data': [
        'data/edi_delivery_guide.xml',
        'views/stock_picking_views.xml',
        'views/stock_quant_views.xml',
        'reports/guia_remision_reports.xml',
    ],
    'installable': True,
    'application': False,
}
