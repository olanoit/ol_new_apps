# -*- coding: utf-8 -*-
{
    'name': 'Farmacia: faltantes y sugerido de compra (AL)',
    'summary': 'Registro de la demanda perdida desde la caja (lo que se pide y no hay) y sugerido '
               'de compra por local según la venta diaria, los faltantes, el stock y lo que está '
               'por llegar, con solicitudes de presupuesto por proveedor o traslado desde el '
               'almacén central.',
    'description': """
Farmacia: faltantes y sugerido de compra
========================================
Entrega E6 de las mejoras (docs/farmacia/MEJORAS_PROCESOS.md).

Faltantes (demanda perdida):

* Botón «Faltante» en la caja: el producto de la línea seleccionada o un
  texto libre («no trabajamos X»), con cantidad y motivo (sin stock, no lo
  trabajamos, precio, otro).
* Queda por local, sesión y cajero; estados pendiente, pedido, atendido y
  descartado.
* Análisis por producto, local y motivo (tabla dinámica y gráfico).

Sugerido de compra por local:

* Venta diaria promedio del periodo: ventas del TPV del local más las
  entregas a clientes que no vienen del TPV (pedidos de venta), menos sus
  devoluciones.
* Sugerido = venta diaria × días de cobertura + faltantes pendientes − stock
  del local − lo que está por llegar (compras y traslados confirmados),
  redondeado hacia arriba al múltiplo de compra (unidad del proveedor o la
  presentación más grande).
* Líneas editables; crea las solicitudes de presupuesto agrupadas por
  proveedor principal o un traslado desde el almacén central, y marca los
  faltantes de esos productos como pedidos.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-HEALTH/Apps',
    'icon': '/al_pharmacy_replenishment/static/description/icon.png',
    'version': '2.20261027',
    'license': 'OPL-1',
    'depends': ['al_pharmacy_pos', 'purchase_stock'],
    'data': [
        'views/pharmacy_shortage_views.xml',
        'wizard/replenishment_wizard_views.xml',
        'views/menus.xml',
        'security/ir.access.csv',
    ],
    'demo': ['demo/pharmacy_replenishment_demo.xml'],
    'assets': {
        'point_of_sale._assets_pos': [
            'al_pharmacy_replenishment/static/src/app/**/*',
        ],
        'web.assets_tests': [
            'al_pharmacy_replenishment/static/tests/tours/**/*',
        ],
    },
    'installable': True,
    'application': False,
}
