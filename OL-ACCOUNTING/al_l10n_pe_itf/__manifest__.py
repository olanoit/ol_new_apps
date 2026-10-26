{
    'name': 'PE - ITF automático (AL)',
    'summary': 'Impuesto a las Transacciones Financieras (0,005 %) registrado al confirmar los '
               'pagos y cobros de los diarios bancarios afectos.',
    'description': """
ITF automático
==============
* Al confirmar un pago o cobro en un diario bancario afecto, registra el ITF
  (Ley 28194: 0,005 %, redondeado según su artículo 13) con un asiento de gasto a
  la 6412 contra la cuenta de pagos pendientes del banco, que se concilia con la
  línea «ITF» del extracto.
* No afecta transferencias entre cuentas propias (art. 9 a) ni las cuentas
  exoneradas (detracciones, remuneraciones, CTS: desmarque el diario). Cada pago
  puede marcarse como exonerado.
* Regla de conciliación «ITF» para los diarios sin cuenta de pendientes.
* Análisis del ITF por mes y banco.
""",
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    'icon': '/account/static/description/icon.png',
    'version': '2.20261026',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['al_account_base', 'al_account_payments', 'l10n_pe'],
    'data': [
        'views/account_journal_views.xml',
        'views/account_payment_views.xml',
        'views/res_config_settings_views.xml',
        'views/itf_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
}
