# -*- coding: utf-8 -*-
{
    'name': 'TPV - Vendedor por orden (AL)',
    'summary': 'Vendedor por orden en el TPV: selector en la pantalla de pago, '
               'vendedor predeterminado por sesión, vendedor en el ticket y en '
               'el análisis de ventas.',
    'description': """
Vendedor por orden en el Punto de Venta
=======================================
Permite asignar un vendedor (empleado de ``hr.employee``) a cada orden
del TPV, restringiendo la selección a una lista blanca por punto de venta:

* **Vendedores autorizados por TPV**: ajuste ``authorized_seller`` +
  lista ``seller_ids`` en la configuración del punto de venta. Los
  vendedores configurados aparecen en el selector aunque no pertenezcan
  a los grupos de acceso de ``pos_hr``.
* **Selector en la pantalla de pago**: botón "Vendedor" junto al de
  cliente que abre un diálogo con búsqueda en vivo, tarjetas con avatar
  (iniciales + color determinista) y acción de quitar selección.
* **Apertura automática al validar**: si la venta requiere vendedor y no
  hay ninguno asignado, el selector se abre solo; únicamente si el
  cajero lo cierra sin elegir se muestra la advertencia y se cancela.
* **Vendedor predeterminado por sesión**: estrella en cada tarjeta para
  fijar/quitar el predeterminado; toda orden nueva lo hereda. Se guarda
  en ``localStorage`` con clave acotada a la sesión abierta.
* **Vendedor en el recibo y en reporting**: el ticket muestra
  "Vendedor: <nombre>" y ``report.pos.order`` agrega ``seller_id`` para
  agrupar/filtrar el análisis de ventas por vendedor.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-POS/Apps',
    'version': '1.20260721',
    'license': 'OPL-1',
    'depends': [
        'point_of_sale',
        'hr',
        'pos_hr',
    ],
    'data': [
        'views/pos_config_view.xml',
        'views/pos_order_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'al_pos_vendedor/static/src/css/vendedor_pos.css',
            'al_pos_vendedor/static/src/js/order.js',
            'al_pos_vendedor/static/src/js/pos_store.js',
            'al_pos_vendedor/static/src/js/selection_popup_custom.js',
            'al_pos_vendedor/static/src/js/payment_screen.js',
            'al_pos_vendedor/static/src/xml/payment_screen.xml',
            'al_pos_vendedor/static/src/xml/order_receipt.xml',
            'al_pos_vendedor/static/src/xml/selection_popup_custom.xml',
        ],
    },
    'installable': True,
    'application': False,
}
