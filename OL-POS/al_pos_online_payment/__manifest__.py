# -*- coding: utf-8 -*-
{
    'name': 'Pago en línea del TPV: ticket sin pagos duplicados (AL)',
    'summary': 'Corrige el TPV de Odoo 19 que, tras un cobro en línea, muestra el pago dos veces '
               'y un cambio igual al importe pagado.',
    'description': """
Pago en línea del TPV sin líneas duplicadas
===========================================
Con el pago en línea nativo (QR que el cliente paga con Izipay, Culqi, Niubiz u
otra pasarela), el TPV de Odoo 19 deja la línea que pidió el cobro y le suma el
pago que registró la pasarela al sincronizar la orden. El ticket muestra el
pago dos veces y un cambio igual al importe, aunque en la base hay un solo
pago.

Cuando la orden ya está pagada en el servidor, este módulo quita del TPV la
línea local de pago en línea: quedan solo los pagos registrados por la
pasarela. Se instala solo con el pago en línea del TPV.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-POS/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/point_of_sale/static/description/icon.png',
    'version': '1.20261016',
    'license': 'OPL-1',
    'depends': ['pos_online_payment'],
    'assets': {
        'point_of_sale._assets_pos': [
            'al_pos_online_payment/static/src/app/**/*',
        ],
    },
    'installable': True,
    'auto_install': True,
    'application': False,
}
