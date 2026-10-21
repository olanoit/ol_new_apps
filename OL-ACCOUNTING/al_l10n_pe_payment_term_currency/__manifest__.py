{
    'name': 'PE - Cuota fija en soles (AL)',
    'summary': 'Plazos de pago con cuotas de importe fijo en soles que se convierten al tipo de '
               'cambio de la factura cuando esta es en dólares u otra moneda.',
    'description': """
Cuota fija en soles
===================
* Casilla **Importe en soles** en las cuotas de importe fijo de los plazos de pago.
* En una factura en moneda extranjera, esa cuota vale el importe en soles convertido al
  tipo de cambio de la propia factura; la cuota de saldo absorbe la diferencia.
* En una factura en soles no cambia nada.

En Odoo 19 una cuota fija está en la moneda de la factura (S/ 1 000 en un plazo se leen
US$ 1 000 en una factura en dólares). La cuota de detracción en soles la separa
al_l10n_pe_detraction; este módulo cubre el resto (inicial o arras pactadas en soles).
""",
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    'icon': '/account/static/description/icon.png',
    'version': '1.20261021',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['al_account_base'],
    'data': [
        'views/account_payment_term_views.xml',
    ],
    'installable': True,
    'application': False,
}
