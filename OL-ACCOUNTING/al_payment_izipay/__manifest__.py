# -*- coding: utf-8 -*-
{
    'name': 'Pagos con Izipay (AL)',
    'summary': 'Izipay como proveedor de pago de Odoo: formulario emergente de Izipay con tarjetas '
               'y cuotas, confirmación por IPN firmada, anulaciones y devoluciones.',
    'description': """
Proveedor de pago Izipay
========================
Construido desde la documentación oficial de Izipay (API REST V4 de
micuentaweb.pe y formulario incrustado) y validado contra su tienda de prueba.

* **Formulario emergente de Izipay** (modo pop-in): los datos de la tarjeta
  van del navegador a Izipay y nunca pasan por Odoo; Izipay se encarga de 3DS
  y de las cuotas.
* **formToken creado en el servidor** con el importe exacto de la
  transacción y los datos del cliente para el antifraude.
* **Confirmación en el servidor**: al terminar, Odoo consulta el pedido a
  Izipay (Order/Get); además procesa la **IPN** firmada con la contraseña,
  aunque el cliente cierre la ventana.
* **Anulación y devoluciones**: el mismo día se anula o se reduce el importe
  por capturar; después de la captura, se reembolsa (total o parcial).
* Soles y dólares. Funciona en la tienda en línea, el portal y los enlaces de
  pago de facturas y pedidos.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    'version': '1.20261014',
    'license': 'OPL-1',
    'depends': ['payment'],
    'data': [
        'views/payment_provider_views.xml',
        'views/payment_izipay_templates.xml',
        'data/payment_provider_data.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'al_payment_izipay/static/src/interactions/payment_form.js',
            'al_payment_izipay/static/src/scss/payment_form.scss',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'application': False,
}
