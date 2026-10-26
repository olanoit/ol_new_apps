# -*- coding: utf-8 -*-
{
    'name': 'Planificación de obra: ventas de mobiliario (AL)',
    'summary': 'Partidas del contrato por familia de la tipología (cocinas, closets…).',
    'description': """
Planificación de obra: ventas de mobiliario
===========================================
Enlace automático de la valorización e ingresos con el rubro mobiliario
(paquete 1.7, M17-07): cada línea de la orden de venta del contrato es la
partida de una familia de tipologías y toma las líneas del plan de los
ambientes de esa familia; la única partida sin familia toma el resto.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    'icon': '/al_construction_planner/static/description/icon.png',
    'version': '2.20261013',
    # LGPL-3 como el planificador del que depende (base_tier_validation es AGPL).
    'license': 'LGPL-3',
    'depends': ['al_construction_planner_sale', 'al_construction_planner_furniture'],
    'data': [
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
}
