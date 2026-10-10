# -*- coding: utf-8 -*-
{
    'name': 'PE - Traslados internos y bienes de terceros (AL)',
    'summary': 'Guía de remisión para todos los traslados de la empresa: entre '
               'establecimientos (04), compras que recoge (02, 07, 08), devoluciones (06) '
               'y exportación (09), y control de los bienes de terceros.',
    'description': """
Traslados internos y bienes de terceros
=======================================
* **Catálogo 20 completo para la empresa**: se suman 02 Compra, 06
  Devolución, 07 Recojo de bienes transformados, 08 Importación y 09
  Exportación; el motivo se propone según la operación o el tipo de operación;
  13 «Otros» con descripción; 08/09 con DAM o DS.
* **Guía en recepciones** que traslada la empresa (02, 07, 08): parte del
  proveedor y llega al almacén.
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
    'version': '2.20261010',
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
