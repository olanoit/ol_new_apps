# -*- coding: utf-8 -*-
{
    'name': 'PE - Declaración mensual IGV y renta (621) (AL)',
    'summary': 'Régimen tributario, pago a cuenta del impuesto a la renta y resumen del '
               'Formulario Virtual 621 con saldo a favor, percepciones y retenciones.',
    'description': """
Declaración mensual (Formulario Virtual 621)
============================================
Un documento por compañía y periodo con todo lo que se declara en el 621:

* **IGV**: débito fiscal de las ventas y crédito fiscal de las compras del
  periodo, desde los asientos publicados; saldo a favor del periodo anterior
  y el que pasa al siguiente.
* **Percepciones y retenciones del IGV** sufridas en el periodo (si están
  instalados los módulos de percepciones y retenciones) más las no aplicadas
  de periodos anteriores, que se descuentan del IGV por pagar; lo no aplicado
  pasa al mes siguiente.
* **Pago a cuenta del impuesto a la renta** según el régimen vigente:
  Régimen General (mayor entre coeficiente y 1,5 %), MYPE Tributario (1 %
  hasta 300 UIT de ingresos netos del ejercicio; luego como el General) y
  Régimen Especial (1,5 %); suspensión aprobada por SUNAT.
* Estados borrador, calculado y declarado; asiento opcional del pago a cuenta.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-ACCOUNTING/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/al_l10n_pe_monthly_tax/static/description/icon.png',
    'version': '5.20261027',
    'license': 'OPL-1',
    'depends': [
        'al_account_base',
        'l10n_pe',
    ],
    'data': [
        'views/l10n_pe_monthly_tax_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
        'security/ir.access.csv',
    ],
    # Solo en bases con datos de demostración, en «PE Company» (l10n_pe).
    'demo': ['demo/al_l10n_pe_monthly_tax_demo.xml'],
    'installable': True,
    'application': False,
}
