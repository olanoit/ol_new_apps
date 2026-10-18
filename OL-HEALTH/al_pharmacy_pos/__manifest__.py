# -*- coding: utf-8 -*-
{
    'name': 'Farmacia: punto de venta (AL)',
    'summary': 'Venta por caja, blíster o unidad en el TPV: cada presentación con su precio, el '
               'stock en unidades y el comprobante en la unidad de la presentación.',
    'description': """
Farmacia: punto de venta
========================
Prototipo E0 del plan (docs/farmacia/PLAN_FARMACIA.md, riesgo R1, opción A):

* Al elegir un producto con presentaciones, el TPV pregunta si se vende por
  unidad o por una presentación (caja, blíster…).
* La línea guarda la presentación; la cantidad va en unidades del producto
  (el stock se descuenta exacto) y el precio unitario es el de la
  presentación entre sus unidades, sin redondear.
* El código de barras del empaque vende directamente la presentación.
* La factura o boleta lleva la línea en la unidad de la presentación
  (1 Blíster x 7 a S/ 1,00), así cuadra con el ticket.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-HEALTH/Apps',
    'icon': '/point_of_sale/static/description/icon.png',
    'version': '1.20261018',
    'license': 'OPL-1',
    'depends': ['al_pharmacy_base', 'point_of_sale'],
    'assets': {
        'point_of_sale._assets_pos': [
            'al_pharmacy_pos/static/src/app/**/*',
        ],
        'web.assets_tests': [
            'al_pharmacy_pos/static/tests/tours/**/*',
        ],
    },
    'installable': True,
    'application': False,
}
