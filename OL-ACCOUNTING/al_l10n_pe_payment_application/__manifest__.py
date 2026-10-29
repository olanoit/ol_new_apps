{
    'name': 'PE - Anticipos y aplicación de documentos (AL)',
    'summary': 'Anticipos de clientes (122) y a proveedores (422) como pagos, su aplicación '
               'a facturas, compensaciones entre cuentas por cobrar y por pagar y control '
               'de anticipos pendientes.',
    'description': """
Anticipos y aplicación de documentos
====================================
* **Anticipo** como pago normal de Odoo cuya cuenta destino es la de anticipos
  de la compañía (122 clientes, 422 proveedores; una por moneda opcional).
* **Aplicación de documentos**: aplicar anticipos a facturas, compensar cuentas
  por cobrar y por pagar del mismo socio y aplicar notas de crédito, también
  parcial, con un asiento en el diario de aplicaciones y conciliación estándar
  (la diferencia de cambio la genera Odoo). Reversión con asiento inverso.
* Botón **Aplicar anticipos** en la factura cuando el socio tiene anticipos.
* Lista de **anticipos pendientes** por socio.
""",
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    'icon': '/al_l10n_pe_payment_application/static/description/icon.png',
    'version': '3.20261027',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['al_account_base', 'al_l10n_pe_payment_receipt', 'l10n_pe'],
    'data': [
        'data/ir_sequence_data.xml',
        'views/payment_application_views.xml',
        'views/account_payment_views.xml',
        'views/account_move_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
        'security/ir.access.csv',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
}
