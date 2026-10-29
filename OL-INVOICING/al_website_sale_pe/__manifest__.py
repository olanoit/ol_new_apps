# -*- coding: utf-8 -*-
{
    'name': 'PE - Tienda en línea peruana (AL)',
    'summary': 'Checkout de la tienda en línea para Perú: el cliente elige boleta o factura, '
               'su RUC o DNI se consulta en SUNAT/RENIEC y llena el nombre y la dirección.',
    'description': """
Tienda en línea peruana
=======================
Odoo 20 pide en el checkout el RUC (``vat``) y los identificadores adicionales
(DNI, pasaporte…) y la provincia y el distrito (``l10n_pe``); con RUC emite
factura y con otro documento, boleta. Este módulo lo hace explícito y rápido
para el cliente peruano:

* **Boleta o factura**: el cliente elige el comprobante y se
  muestra el documento que corresponde (factura → RUC; boleta → DNI).
* **Consulta del RUC o DNI**: con las conexiones de ``l10n_pe_vat_sunat``, el
  nombre o razón social, la dirección, el departamento, la provincia y el
  distrito se llenan solos.
* Las consultas desde la tienda tienen un límite por sesión: la ruta es
  pública y las API de consulta pueden ser de pago.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-INVOICING/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/al_website_sale_pe/static/description/icon.png',
    'version': '2.20261027',
    'license': 'OPL-1',
    'depends': [
        'website_sale',
        'l10n_pe',
        'l10n_pe_vat_sunat',
    ],
    'data': [
        'views/templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'al_website_sale_pe/static/src/interactions/address.js',
        ],
    },
    'installable': True,
    'application': False,
}
