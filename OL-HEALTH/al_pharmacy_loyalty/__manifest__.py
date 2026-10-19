# -*- coding: utf-8 -*-
{
    'name': 'Farmacia: fidelización por DNI (AL)',
    'summary': 'Puntos y vales para los clientes de la botica sin premiar los medicamentos con '
               'receta ni los controlados: no suman puntos ni reciben descuentos o regalos.',
    'description': """
Farmacia: fidelización por DNI
==============================
Entrega E8 de las mejoras de la suite (docs/farmacia/MEJORAS_PROCESOS.md).

Las cadenas identifican al cliente por su DNI y le dan puntos y vales
(Inkaclub: 1 punto por S/ 4 y un vale de S/ 5 cada 1 000 puntos). En una
botica hay un límite: no se promueve el consumo de medicamentos con sorteos,
premios ni canjes, y menos el de los que necesitan receta.

* Opción «Excluir medicamentos con receta» en los programas de fidelización,
  promociones y cupones (activa por defecto).
* Con la opción, los productos con receta y los controlados no suman puntos
  ni entran en las condiciones del programa, en el TPV y en los pedidos de
  venta.
* Los descuentos no los alcanzan: un descuento sobre el pedido pasa a
  aplicarse solo a los demás productos.
* Un programa no puede regalar un medicamento con receta.
* Las tarjetas de regalo y los monederos no cambian: son medios de pago.
* Al instalar, los programas que ya existían se ajustan igual.
* Datos de ejemplo: programa «Club de Salud».
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-HEALTH/Apps',
    'icon': '/al_pharmacy_base/static/description/icon.png',
    'version': '1.20261019',
    'license': 'OPL-1',
    'depends': ['al_pharmacy_base', 'pos_loyalty', 'sale_loyalty'],
    'data': ['views/loyalty_program_views.xml'],
    'demo': ['demo/loyalty_demo.xml'],
    'assets': {
        'web.assets_tests': [
            'al_pharmacy_loyalty/static/tests/tours/**/*',
        ],
    },
    'post_init_hook': '_post_init_hook',
    'installable': True,
    'application': False,
}
