# -*- coding: utf-8 -*-
{
    'name': 'Costeo de piezas por medida (AL)',
    'summary': 'La orden de corte reparte su costo entre las piezas por área, material de '
               'origen y metros de tapacanto, e importa el despiece como productos-pieza.',
    'description': """
Costeo de piezas por medida
===========================
Orden de fabricación de corte (CNC o corte manual): cada pieza producida
(subproducto con su propio producto) recibe el costo que le corresponde por
su área en m², el tablero del que se corta y sus metros de tapacanto, en lugar
del reparto en partes iguales del estándar.

* Se apoya en el ``cost_share`` nativo de los subproductos (gancho
  ``_cal_price``) y fija el costo unitario de cada salida: asientos, kárdex y
  reportes quedan coherentes.
* Bolsas: tapacanto (por la marca del producto), una por tablero (solo entre
  sus piezas) y la general (mano de obra, costo extra e insumos sueltos).
* Controles: sin entregas parciales, sin desarme, sin kits, piezas con área y
  con su tablero entre los componentes; cuadre de la orden cerrada y ajustes
  manuales de valor.
* Importador del despiece (XLSX plano) que crea o actualiza los
  productos-pieza.

Refactorización del costeador de Allcenter (especificación de costeo de
piezas CNC v1.4, 20-set-2026) con la misma lógica.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-INVENTORY/Apps',
    'icon': '/al_mrp_piece_costing/static/description/icon.png',
    'version': '3.20261027',
    'license': 'OPL-1',
    # al_stock_base: costo fijo de los retazos (paquete 1.11, M111-12).
    'depends': ['mrp_account', 'al_stock_base'],
    'data': [
        'security/ir.model.access.csv',
        'wizards/piece_import_wizard_views.xml',
        'views/product_template_views.xml',
        'views/stock_picking_type_views.xml',
        'views/mrp_production_views.xml',
        'views/menus.xml',
    ],
    'pre_init_hook': 'pre_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
