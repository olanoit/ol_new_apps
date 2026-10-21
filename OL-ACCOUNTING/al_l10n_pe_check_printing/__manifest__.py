{
    'name': 'PE - Impresión de cheques (AL)',
    'summary': 'Imprime los cheques propios sobre la hoja de la chequera del banco, con un formato '
               'calibrable por diario: fecha, beneficiario e importe en números y en letras.',
    'description': """
Impresión de cheques
====================
* **Formato de cheque** por banco: tamaño de la hoja y posición en milímetros de la
  fecha, la fecha de pago (cheque diferido), el beneficiario, el importe en números (con
  asteriscos) y el importe en letras, y la leyenda «No negociable».
* **Imprimir prueba** con datos de ejemplo para calibrarlo contra la chequera.
* **Imprimir cheque** desde el cheque propio o el pago, una hoja por cheque y con el
  tamaño de papel del formato.

Los cheques propios son los de la gestión nativa de cheques (l10n_latam_check) que
adapta al_l10n_pe_check.
""",
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    'icon': '/account/static/description/icon.png',
    'version': '1.20261021',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['al_l10n_pe_check'],
    'external_dependencies': {'python': ['num2words']},
    'data': [
        'security/ir.model.access.csv',
        'security/check_printing_security.xml',
        'report/check_report.xml',
        'views/check_layout_views.xml',
        'views/account_journal_views.xml',
        'views/l10n_latam_check_views.xml',
    ],
    'installable': True,
    'application': False,
}
