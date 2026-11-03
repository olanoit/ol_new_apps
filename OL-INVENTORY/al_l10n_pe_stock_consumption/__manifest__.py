# -*- coding: utf-8 -*-
{
    'name': 'PE - Asiento de consumo a costo',
    'summary': 'Las salidas de almacén a consumo se contabilizan al costo, en la cuenta de la '
               'familia del producto (61) y con su centro de costo; de ahí sale el destino 9/79.',
    'description': """
Asiento de consumo a costo (Perú)
=================================
Una ubicación virtual marcada «de consumo» convierte cada salida en un cargo a
gasto o variación de existencias, por el valor del movimiento:

    61x (cuenta de la categoría o de la ubicación, con centro de costo)
        a 2x (cuenta de existencias del producto)

* Valorización permanente: un asiento por movimiento, como el nativo.
* Valorización periódica: una línea por cuenta y centro en el cierre de
  valorización de Odoo.
* Las devoluciones de consumo revierten el asiento.
* Con ``al_account_destinations``, el asiento genera su destino 9/79 según el
  centro de costo.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-INVENTORY/Apps',
    'icon': '/al_l10n_pe_stock_consumption/static/description/icon.png',
    'version': '1.20261103',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['stock_account'],
    'data': [
        'views/stock_location_views.xml',
        'views/product_category_views.xml',
        'views/stock_picking_views.xml',
        'views/stock_move_views.xml',
    ],
    'installable': True,
    'application': False,
}
