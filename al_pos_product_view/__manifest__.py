# -*- coding: utf-8 -*-
{
    'name': 'TPV - Catálogo de productos: filtro por etiquetas y vista lista (AL)',
    'summary': 'Chips de filtro por etiqueta de producto sobre el catálogo '
               'del TPV y conmutador cuadrícula/lista con filas compactas, '
               'popup de información enriquecido y preferencia por cajero.',
    'description': """
Catálogo de productos del TPV: filtro por etiquetas y vista lista
==================================================================
Unificación en un solo módulo de dos funcionalidades (originalmente los
módulos ``mblz_pos_filter_products_by_active_ingredient`` y
``mblz_pos_product_switch_view``), usando las **etiquetas de producto
estándar** (``product.tag``) en lugar del modelo de principios activos —
sin dependencias externas.

**Filtro por etiquetas**

* Fila de **chips** (uno por etiqueta usada por algún producto cargado)
  sobre la grilla de productos, debajo del selector de categorías.
  Selección múltiple con semántica OR y botón *Limpiar*.
* Convive con la búsqueda por texto, las categorías y el modo "Agrupar
  por categoría"; se engancha antes del tope de 100 productos visibles.
* **Botón de recarga** para traer cambios del backend (nuevas,
  renombradas, recoloreadas, eliminadas) sin salir de la sesión.
* Campo **"Mostrar en la barra de filtros del TPV"** por etiqueta para
  acotar los chips visibles, con edición masiva en lista.
* Casilla de activación por caja en los ajustes del TPV (activada por
  defecto) y **etiquetas de ejemplo** (Bebidas, Textil, Abarrotes,
  Servicios, Promoción) para probar.

**Conmutador de vista cuadrícula/lista**

* Botón sobre el catálogo para alternar entre las tarjetas nativas y
  una **vista de lista compacta**: miniatura, nombre, SKU, código de
  barras, etiquetas, stock disponible, cantidad en carrito y precio con
  impuestos según ``iface_tax_included``.
* Botón de información en filas y tarjetas que abre el
  **ProductInfoPopup reorganizado**: banner superior de stock por
  bodega, productos opcionales como tarjetas y panel "Información
  General" en dos columnas.
* Vista por defecto configurable por TPV y **preferencia persistente
  por cajero** (cascada usuario → configuración → cuadrícula),
  editable también desde las preferencias del usuario.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-POS/Apps',
    'version': '2.20260721',
    'license': 'OPL-1',
    # `stock` ya viene transitivamente vía point_of_sale ->
    # stock_account -> stock; se declara explícito porque
    # models/product_template.py usa `qty_available` directamente.
    'depends': [
        'point_of_sale',
        'stock',
    ],
    'data': [
        'data/product_tag_data.xml',
        'views/product_tag_views.xml',
        'views/res_config_settings_views.xml',
        'views/res_users_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            # --- Filtro por etiquetas ---
            'al_pos_product_view/static/src/tag_filter/scss/tag_selector.scss',
            # El patch del PosStore va primero: los componentes de abajo
            # leen su nuevo estado/helpers.
            'al_pos_product_view/static/src/tag_filter/overrides/pos_store_patch.js',
            'al_pos_product_view/static/src/tag_filter/components/tag_selector/tag_selector.js',
            'al_pos_product_view/static/src/tag_filter/components/tag_selector/tag_selector.xml',
            'al_pos_product_view/static/src/tag_filter/overrides/product_screen/product_screen_patch.js',
            'al_pos_product_view/static/src/tag_filter/overrides/product_screen/product_screen_patch.xml',
            # --- Conmutador de vista cuadrícula/lista ---
            'al_pos_product_view/static/src/switch_view/scss/product_list_view.scss',
            'al_pos_product_view/static/src/switch_view/utils/product_price.js',
            'al_pos_product_view/static/src/switch_view/components/product_list_row/product_list_row.js',
            'al_pos_product_view/static/src/switch_view/components/product_list_row/product_list_row.xml',
            'al_pos_product_view/static/src/switch_view/overrides/product_screen/product_screen.js',
            'al_pos_product_view/static/src/switch_view/overrides/product_screen/product_screen.xml',
            'al_pos_product_view/static/src/switch_view/overrides/product_card/product_card.scss',
            'al_pos_product_view/static/src/switch_view/overrides/product_card/product_card.js',
            'al_pos_product_view/static/src/switch_view/overrides/product_card/product_card.xml',
            'al_pos_product_view/static/src/switch_view/overrides/product_info_popup/product_info_popup.scss',
            'al_pos_product_view/static/src/switch_view/overrides/product_info_popup/product_info_popup.js',
            'al_pos_product_view/static/src/switch_view/overrides/product_info_popup/product_info_popup.xml',
        ],
        # Los tours se cargan con `start_tour()` en HttpCase; viven en el
        # bundle genérico `web.assets_tests`, NO en el bundle del TPV.
        'web.assets_tests': [
            'al_pos_product_view/static/tests/tours/**/*',
        ],
    },
    'installable': True,
    'application': False,
}
