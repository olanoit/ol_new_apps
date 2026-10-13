# -*- coding: utf-8 -*-
{
    'name': 'Aprobación de órdenes de venta (AL)',
    'summary': 'Las ventas de productos marcados no se confirman sin una solicitud '
               'aprobada en Aprobaciones.',
    'description': """
Aprobación de órdenes de venta
==============================
* En el producto: **Requiere aprobación de venta**.
* En Ajustes ▸ Ventas: la categoría de Aprobaciones de las ventas.
* En la orden de venta: botón **Solicitar aprobación** (crea la solicitud con
  la orden como referencia), estado de la aprobación y botón inteligente.
* La orden no se confirma mientras no tenga una solicitud aprobada. Las
  solicitudes anteriores al módulo valen si su referencia es el número de la
  orden.
* **Sin aprobación (carga histórica)**: para órdenes cargadas de otro sistema
  (solo gerencia de ventas).
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-INVOICING/Apps',
    'icon': '/approvals/static/description/icon.png',
    'version': '1.20261013',
    'license': 'OPL-1',
    'depends': ['sale_management', 'approvals'],
    'data': [
        'views/approval_request_views.xml',
        'views/product_template_views.xml',
        'views/sale_order_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
}
