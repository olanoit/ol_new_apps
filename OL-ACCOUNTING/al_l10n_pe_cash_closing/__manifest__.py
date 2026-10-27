{
    'name': 'PE - Cierre de caja y arqueo (AL)',
    'summary': 'Cierre diario de cada caja: saldo según libros, cobros y pagos por medio de pago, '
               'arqueo por denominación, asiento del faltante o sobrante y bloqueo del día cerrado.',
    'description': """
Cierre de caja y arqueo
=======================
* Un cierre por caja y día: saldo inicial según libros, cobros (contado y cobranza),
  pagos, depósitos y transferencias, y saldo final según libros.
* Resumen por medio de pago (catálogo SUNAT).
* Arqueo por denominación (billetes y monedas en soles y dólares, configurables) y
  otros valores.
* Al cerrar, el faltante o sobrante se registra contra las cuentas de diferencia del
  diario (o la cuenta y el responsable que se indiquen, p. ej. cuentas por cobrar al
  personal) y el día queda bloqueado para la caja.
* Reapertura solo por el administrador de contabilidad. PDF con firmas.
""",
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    'icon': '/al_l10n_pe_cash_closing/static/description/icon.png',
    'version': '3.20261027',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['al_account_base', 'al_account_payments', 'al_report_base'],
    'data': [
        'security/ir.model.access.csv',
        'security/cash_closing_security.xml',
        'data/ir_sequence_data.xml',
        'data/cash_denomination_data.xml',
        'report/cash_closing_report.xml',
        'views/cash_closing_views.xml',
        'views/cash_denomination_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
}
