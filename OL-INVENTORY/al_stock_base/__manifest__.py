# -*- coding: utf-8 -*-
{
    'name': 'PE - Base Inventario (AL)',
    'summary': 'Página «Logística PE» en las transferencias: un solo lugar '
               'para los datos peruanos (guía de remisión, PLE, obra…).',
    'description': """
Base de inventario Perú
=======================
Módulo base y liviano del que cuelgan los datos peruanos de las
transferencias. Añade al formulario la página **Logística PE** con un
contenedor de grupos (``l10n_pe_stock_groups``): cada módulo de la suite pone
ahí su grupo (guía de remisión y transporte, libros electrónicos, requerimiento
de obra), como «Facturación PE» en la factura.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-INVENTORY/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/stock/static/description/icon.png',
    'version': '1.20261008',
    'license': 'OPL-1',
    # stock_account aporta stock.picking.country_code
    'depends': ['stock_account'],
    'data': [
        'views/stock_picking_views.xml',
    ],
    'installable': True,
    'application': False,
}
