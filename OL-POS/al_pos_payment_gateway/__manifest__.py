# -*- coding: utf-8 -*-
{
    'name': 'Cobro con pasarelas en el TPV: un método por pasarela y devoluciones (AL)',
    'summary': 'Cada pasarela (Izipay, Niubiz, Culqi…) como método de pago propio del TPV: el '
               'cliente paga con el QR en su teléfono y las devoluciones vuelven a su tarjeta.',
    'description': """
Cobro con pasarelas en el punto de venta
========================================
El pago en línea nativo del TPV admite un solo método por caja: el cliente
escanea el QR y elige la pasarela en su teléfono. Este módulo lo completa:

* **Un método por pasarela**: la caja puede tener «Izipay», «Niubiz» y
  «Culqi» a la vez. El cajero elige con cuál cobra, el QR abre directamente
  esa pasarela y el cierre de caja muestra lo cobrado con cada una.
* **Botón «Cobrar en el TPV»** en la pasarela: crea su método de pago del
  TPV.
* **Devoluciones a la tarjeta**: al devolver una venta cobrada con una
  pasarela, el cajero elige ese método y el importe vuelve al medio de pago
  del cliente por la API de la pasarela (total o parcial).

Funciona con cualquier pasarela de Odoo que admita devoluciones; para Perú,
con al_payment_izipay, al_payment_niubiz y al_payment_culqi.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-POS/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/point_of_sale/static/description/icon.png',
    'version': '6.20261018',
    'license': 'OPL-1',
    'depends': ['al_pos_online_payment'],
    'data': [
        'views/payment_provider_views.xml',
    ],
    'assets': {
        # Después de pos_online_payment, que va en assets_prod: sus parches
        # deben quedar debajo de los de este módulo.
        'point_of_sale.assets_prod': [
            'al_pos_payment_gateway/static/src/app/**/*.js',
        ],
        'point_of_sale._assets_pos': [
            'al_pos_payment_gateway/static/src/app/**/*.xml',
            'al_pos_payment_gateway/static/src/app/**/*.scss',
        ],
        'web.assets_tests': [
            'al_pos_payment_gateway/static/tests/tours/**/*',
        ],
    },
    'installable': True,
    'application': False,
}
