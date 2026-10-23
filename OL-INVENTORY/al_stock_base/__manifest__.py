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

También deja compacto el resumen de inventario: tarjetas sin gráfico y con
las etiquetas en español, y guarda la regla de las planchas enteras
(unidad «Plancha entera», producto indivisible, necesidad y redondeo del
movimiento) que usan el requerimiento de obra y la fabricación del
planificador.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-INVENTORY/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/stock/static/description/icon.png',
    'version': '3.20261023',
    'license': 'OPL-1',
    # stock_account aporta stock.picking.country_code
    'depends': ['stock_account'],
    'data': [
        'views/stock_picking_views.xml',
        'views/whole_sheet_views.xml',
    ],
    'assets': {
        # Resumen de inventario compacto (paquete 1.11, M111-09).
        'web.assets_backend': [
            'al_stock_base/static/src/stock_overview/*',
        ],
    },
    'installable': True,
    'application': False,
}
