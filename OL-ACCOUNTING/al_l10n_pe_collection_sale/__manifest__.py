{
    'name': 'Cobranza: bloqueo de ventas por mora (AL)',
    'summary': 'No deja confirmar pedidos de venta de clientes con bloqueo de crédito por mora y lo '
               'advierte en el pedido.',
    'description': """
Cobranza: bloqueo de ventas por mora
====================================
Puente entre la app Cobranza y Ventas: un cliente bloqueado (por días de atraso,
por calificación D o a mano) no puede confirmar pedidos; el pedido lo advierte
desde que se elige el cliente. El administrador de cobranza lo libera por unos
días desde la ficha del cliente.

Se instala solo cuando están al_l10n_pe_collection y sale.
""",
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    'version': '2.20261027',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['al_l10n_pe_collection', 'sale'],
    'data': ['views/sale_order_views.xml'],
    'installable': True,
    'application': False,
    'auto_install': True,
}
