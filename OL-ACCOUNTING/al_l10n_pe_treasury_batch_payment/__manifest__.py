# -*- coding: utf-8 -*-
{
    'name': 'PE - Programación de pagos con lote bancario (AL)',
    'summary': 'Al pagar una programación de Tesorería con el método «archivo TXT del banco», sus '
               'pagos quedan agrupados en un lote listo para generar el archivo.',
    'description': """
Programación de pagos con lote bancario
=======================================
Puente entre la programación de pagos de Tesorería y los pagos masivos a
proveedores (TXT de BCP, BBVA, Interbank, Scotiabank y Banco de la Nación):
la programación aprobada se paga y sus pagos se agrupan en un lote; el lote
queda enlazado a la programación.
""",
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    'icon': '/al_l10n_pe_treasury/static/description/icon.png',
    'version': '1.20261026',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['al_l10n_pe_treasury', 'al_l10n_pe_batch_payment'],
    'data': [
        'views/treasury_payment_plan_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
}
