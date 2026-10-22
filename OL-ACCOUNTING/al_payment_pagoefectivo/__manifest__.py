# -*- coding: utf-8 -*-
{
    'name': 'Pagos con PagoEfectivo (AL)',
    'summary': 'PagoEfectivo como proveedor de pago de Odoo: código de pago (CIP) para pagar en '
               'efectivo en agentes y bodegas o desde la banca, confirmado por notificación firmada.',
    'description': """
Proveedor de pago PagoEfectivo
==============================
Para clientes sin tarjeta: Odoo genera un código de pago (CIP) por el importe
exacto y el cliente lo paga en efectivo en agentes y bodegas, o desde la banca
por internet y las billeteras.

* **CIP generado en el servidor** con la API REST v1 de PagoEfectivo
  (autorización firmada con SHA-256 y token Bearer). El cliente va a la página
  del CIP en PagoEfectivo y además lo recibe por correo.
* **Confirmación por notificación** firmada con HMAC-SHA256 (cabecera
  PE-Signature): el pago se registra en Odoo cuando PagoEfectivo avisa.
* **Vencimiento**: vigencia configurable; vencido el CIP, la transacción se
  cancela sola.
* Soles y dólares. Funciona en la tienda en línea, el portal, los enlaces de
  pago y los avisos de cobranza.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    'version': '1.20261022',
    'license': 'OPL-1',
    'depends': ['payment'],
    'data': [
        'views/payment_provider_views.xml',
        'views/payment_pagoefectivo_templates.xml',
        'data/payment_method_data.xml',
        'data/payment_provider_data.xml',
        'data/ir_cron_data.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'application': False,
}
