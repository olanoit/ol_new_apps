# -*- coding: utf-8 -*-
{
    'name': 'Farmacia: punto de venta (AL)',
    'summary': 'Caja de farmacia: venta por caja, blíster o unidad con su precio, alternativas '
               'genéricas primero, receta en la caja, control del químico farmacéutico, lotes '
               'disponibles por vencimiento y receta y dispensación registradas al vender.',
    'description': """
Farmacia: punto de venta
========================
Entregas E0 y E2 del plan (docs/farmacia/PLAN_FARMACIA.md).

Venta por presentación (riesgo R1, opción A):

* Al elegir un producto con presentaciones, el TPV pregunta si se vende por
  unidad o por una presentación (caja, blíster…).
* La línea guarda la presentación; la cantidad va en unidades del producto
  (el stock se descuenta exacto) y el precio unitario es el de la
  presentación entre sus unidades, sin redondear.
* La lista de precios del pedido (porcentaje o fórmula) se aplica al precio
  de la presentación; se recalcula al cambiar la lista o la cantidad.
* El código de barras del empaque vende directamente la presentación.
* La factura o boleta lleva la línea en la unidad de la presentación
  (1 Blíster x 7 a S/ 1,00), así cuadra con el ticket.

Dispensación en la caja:

* Al elegir un producto de marca con equivalentes, ofrece las alternativas:
  genéricos en DCI primero y del más barato al más caro (Ley 32033).
* Productos con receta: pide la receta (número, fecha, prescriptor y
  colegiatura, paciente) según el ajuste de la compañía; el químico
  farmacéutico puede autorizar la excepción (nunca en controlados).
* Si quien atiende no es químico farmacéutico: aviso o bloqueo, según el
  ajuste; cada caso queda en el libro de ocurrencias.
* Lotes: solo los disponibles, el que vence primero arriba (FEFO).
* Al guardar la venta pagada se registran la receta y la dispensación.

Precio por vencer (mejora E11):

* Al vender un lote que vence dentro de una escala de descuento por vencer
  (al_pharmacy_stock), la línea recibe el descuento y la nota «Por vencer:
  vence dd/mm/aaaa». Si se cambia a un lote sin descuento, vuelve al precio
  normal.
* Un lote vencido nunca se ofrece, aunque el cron diario aún no lo marque.

Cumplimiento (DS 020-2024-SA):

* Empresa vinculada (art. 32-B): aviso al agregar el producto y leyenda en
  la línea y en el ticket.
* Venta fraccionada (art. 48): rótulo del envase con el establecimiento, el
  producto, el laboratorio, la concentración, la vía, el lote y el
  vencimiento, desde el recibo del TPV o la orden.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-HEALTH/Apps',
    'icon': '/al_pharmacy_pos/static/description/icon.png',
    'version': '10.20261027',
    'license': 'OPL-1',
    'depends': ['al_pharmacy_base', 'al_pharmacy_stock', 'al_pharmacy_prescription',
                'point_of_sale', 'pos_hr'],
    'data': ['report/pos_fraction_label.xml', 'views/res_config_settings_views.xml'],
    'assets': {
        'point_of_sale._assets_pos': [
            'al_pharmacy_pos/static/src/app/**/*',
        ],
        'web.assets_tests': [
            'al_pharmacy_pos/static/tests/tours/**/*',
        ],
    },
    'demo': ['demo/pharmacy_pos_demo.xml'],
    'installable': True,
    'application': False,
}
