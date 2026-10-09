# -*- coding: utf-8 -*-
{
    'name': 'Pagos con Niubiz (AL)',
    'summary': 'Niubiz Checkout All-In-One como proveedor de pago: tarjetas, Yape, Plin, '
               'Cuotéalo BCP y PagoEfectivo, con anulación y devoluciones.',
    'description': """
Proveedor de pago Niubiz (VisaNet Perú)
=======================================
Integra el **Checkout All-In-One de Niubiz** en Odoo 19: un solo modal para
tarjetas, Yape, Plin, Cuotéalo BCP y PagoEfectivo.

* **Tarjetas** Visa, Mastercard, American Express y Diners; los datos los
  procesa Niubiz (PCI DSS nivel 1).
* **Billeteras y cuotas**: Yape, Plin y Cuotéalo BCP en el mismo modal.
* **PagoEfectivo**: código CIP para pagar en efectivo; la transacción queda
  pendiente hasta el pago.
* **Anulación** el mismo día (reversa) y **devoluciones** parciales o totales.
* Soles y dólares, modo de prueba con el sandbox de Niubiz y huella del
  dispositivo para el antifraude.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    'version': '2.20261009',
    'license': 'OPL-1',
    'depends': ['payment'],
    'data': [
        'views/payment_niubiz_templates.xml',
        'views/payment_provider_views.xml',
        'data/payment_provider_data.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
