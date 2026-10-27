# -*- coding: utf-8 -*-
{
    'name': 'Farmacia: tienda en línea (AL)',
    'summary': 'Tienda en línea de la botica: genéricos primero en la ficha del producto, receta '
               'subida antes de pagar y validada por el químico farmacéutico, controlados solo en '
               'el local, recojo en tienda y cadena de frío en la hoja de reparto.',
    'description': """
Farmacia: tienda en línea
=========================
Entrega E9 de las mejoras (docs/farmacia/MEJORAS_PROCESOS.md).

* Genéricos primero también en la web (DS 020-2024-SA, art. 49): la ficha de
  un producto con equivalentes muestra las alternativas, primero los
  genéricos en DCI y del más barato al más caro, con su precio y tipo.
* Leyenda de empresa vinculada en la ficha (art. 32-B).
* Venta con receta: antes de pagar, el cliente sube la foto o el PDF de la
  receta (JPG, PNG o PDF de hasta 5 MB). El pedido pagado queda «por
  validar» y no se confirma ni se entrega hasta que un químico farmacéutico
  aprueba la receta; si la rechaza, el cliente ve el motivo en el portal y
  puede subir otra. El químico farmacéutico que valida necesita ver todos
  los pedidos de venta (Ventas: todos los documentos).
* Los controlados no se venden en línea: la ficha no muestra el carrito y el
  carrito no los acepta (BPOF 7.5.5.1).
* Recojo en tienda con el «Click &amp; Collect» de Odoo.
* Cadena de frío: aviso en el pedido y en la entrega, filtro en las
  entregas y recuadro en la hoja de reparto.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-HEALTH/Apps',
    'icon': '/al_pharmacy_website/static/description/icon.png',
    'version': '3.20261027',
    'license': 'OPL-1',
    'depends': ['al_pharmacy_prescription', 'website_sale', 'website_sale_collect'],
    'data': [
        'views/website_templates.xml',
        'views/sale_order_views.xml',
        'report/delivery_slip.xml',
    ],
    'demo': ['demo/website_demo.xml'],
    'installable': True,
    'application': False,
}
