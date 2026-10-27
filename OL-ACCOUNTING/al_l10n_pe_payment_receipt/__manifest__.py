{
    'name': 'PE - Comprobante de pago (AL)',
    'summary': 'Recibo de ingreso y comprobante de egreso numerados con serie propia por diario, '
               'con el detalle de lo pagado, el monto en letras y las firmas.',
    'description': """
Comprobante de pago
===================
* Serie propia por diario y sentido (recibo de ingreso RI, comprobante de egreso
  RE), asignada al confirmar el pago y sin reutilizar números.
* PDF con el formato común de la suite: socio y documento, medio de pago SUNAT,
  número de operación, banco y cuenta, monto en números y en letras, detalle de
  los comprobantes aplicados (también parciales), otros conceptos del asiento
  (retención, diferencias) y firmas.
* Envío por correo desde el pago.
""",
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    'icon': '/al_l10n_pe_payment_receipt/static/description/icon.png',
    'version': '3.20261027',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['al_account_payments', 'al_report_base'],
    'external_dependencies': {'python': ['num2words']},
    'data': [
        'reports/payment_receipt_reports.xml',
        'data/mail_template_data.xml',
        'views/account_journal_views.xml',
        'views/account_payment_views.xml',
    ],
    'installable': True,
    'application': False,
}
