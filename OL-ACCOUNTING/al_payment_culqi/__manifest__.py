# -*- coding: utf-8 -*-
{
    'name': 'Pagos con Culqi (AL)',
    'summary': 'Culqi como proveedor de pago de Odoo: tarjetas y Yape con Checkout Custom, '
               'autenticación 3DS y devoluciones totales o parciales.',
    'description': """
Proveedor de pago Culqi
=======================
Construido desde la documentación oficial de Culqi (API v2, Checkout Custom y
Culqi 3DS).

* **Tarjetas y Yape** con Culqi Checkout Custom: los datos de la tarjeta van
  del navegador a Culqi y nunca pasan por Odoo.
* **Cargo en el servidor** con la llave secreta, por el monto exacto en
  céntimos, con los datos antifraude del cliente y la huella del dispositivo.
* **Autenticación 3DS** cuando el banco la pide (respuesta REVIEW): el cliente
  se autentica y el cargo se repite con los parámetros 3DS.
* **Devoluciones** totales o parciales desde la transacción de Odoo.
* Soles y dólares. Funciona en la tienda en línea, el portal y los enlaces de
  pago de facturas y pedidos.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    'version': '1.20261006',
    'license': 'OPL-1',
    'depends': ['payment'],
    'data': [
        'views/payment_provider_views.xml',
        'views/payment_culqi_templates.xml',
        'data/payment_method_data.xml',
        'data/payment_provider_data.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'al_payment_culqi/static/src/interactions/payment_form.js',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'application': False,
}
