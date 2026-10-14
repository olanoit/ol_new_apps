# -*- coding: utf-8 -*-
{
    'name': 'PE - Cobro con QR de Yape y Plin en el TPV (AL)',
    'summary': 'El QR de cobro de Yape, Plin u otra billetera como método de pago QR del TPV: '
               'se muestra en la caja y en la pantalla del cliente, y el cajero confirma el pago.',
    'description': """
Cobro con el QR de Yape o Plin en el punto de venta
===================================================
El QR de cobro que entregan Yape, Plin o el banco (QR interoperable) es una
imagen fija: no lleva el importe ni avisa del pago a Odoo. Este módulo lo
convierte en un **formato de QR** de Odoo, así funciona con el cobro por QR
nativo del TPV:

* La imagen se sube en la **cuenta bancaria** donde llegan los abonos
  (pestaña «QR de billetera»).
* En el TPV se crea un método de pago con integración **QR** y formato
  «QR de billetera (Yape, Plin)», en un diario de banco con esa cuenta.
* Al cobrar, el TPV muestra el QR en la caja y en la pantalla del cliente; el
  cliente escanea, escribe el importe en su app y el cajero confirma al ver
  la notificación del pago.
* Sin conexión, el TPV usa la misma imagen (el QR no depende del importe).
* Si la compañía muestra QR en las facturas, también sirve para ellas.

Solo admite soles: Yape y Plin no cobran en dólares.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-POS/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/point_of_sale/static/description/icon.png',
    'version': '1.20261014',
    'license': 'OPL-1',
    'depends': [
        'point_of_sale',
        'l10n_pe',
    ],
    'data': [
        'views/res_partner_bank_views.xml',
    ],
    'installable': True,
    'application': False,
}
