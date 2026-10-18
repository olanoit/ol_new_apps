# -*- coding: utf-8 -*-
{
    'name': 'Farmacia: maestro farmacéutico (AL)',
    'summary': 'Presentaciones de venta (caja, blíster, frasco) con precio propio; el stock se '
               'lleva en la unidad del producto.',
    'description': """
Farmacia: maestro farmacéutico
==============================
Núcleo de la suite de farmacias y boticas (docs/farmacia/PLAN_FARMACIA.md).

Prototipo E0: presentaciones de venta con precio propio. Cada presentación
agrupa un número fijo de unidades del producto, tiene su unidad de medida
(«Caja x 100», creada sola y agregada a los empaques del producto) y su
precio, que no tiene por qué ser proporcional al de la unidad.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-HEALTH/Apps',
    'version': '1.20261018',
    'license': 'OPL-1',
    'depends': ['product', 'uom'],
    'data': [
        'security/ir.model.access.csv',
        'security/pharmacy_security.xml',
        'views/product_template_views.xml',
    ],
    'installable': True,
    'application': False,
}
