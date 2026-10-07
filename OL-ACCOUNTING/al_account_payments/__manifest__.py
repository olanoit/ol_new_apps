# -*- coding: utf-8 -*-
{
    'name': 'PE - Medios de Pago (AL)',
    'summary': 'Medio de pago SUNAT (catálogo 1) y número de operación '
               'bancaria en pagos y en el asistente de registro de pagos.',
    'description': """
Medios de pago — SUNAT Perú
===========================
Personalizaciones al circuito de pagos para la localización peruana:

* Catálogo ``pe.catalog.payment`` con los medios de pago de SUNAT
  (depósito en cuenta, transferencia, cheque, efectivo, etc.), su código
  de facturador (PSE) y la marca "para detracción".
* Campos **Medio pago** y **Número de operación banco** en el pago
  (``account.payment``) y en el asistente de registro de pagos
  (``account.payment.register``), que los traslada a los pagos creados.
* Menú de mantenimiento del catálogo en Contabilidad ▸ Configuración y
  en Perú ▸ Configuración.

Refactor v19 (desde v18): el catálogo ya no hereda del modelo
``pe.catalog`` (eliminado del ``al_account_base`` v19) y se quitó la
dependencia muerta de ``al_account_dua``.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-ACCOUNTING/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/account/static/description/icon.png',
    'version': '6.20261008',
    'license': 'OPL-1',
    'depends': [
        'account',
        # Catálogos peruanos (tipos de identificación y códigos de tributo
        # SUNAT) que usan los pagos y sus pruebas.
        'l10n_pe',
        'al_account_base',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/account_payment_views.xml',
        'views/pe_catalog_payment_views.xml',
        'views/menus.xml',
        'wizards/account_payment_register_views.xml',
        'data/pe_catalog_payment.xml',
    ],
    'installable': True,
    'application': False,
}
