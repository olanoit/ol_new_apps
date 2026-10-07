# -*- coding: utf-8 -*-
{
    'name': 'TPV - Tema y marca blanca (AL)',
    'summary': 'Rediseño integral y marca blanca del TPV: tokens de diseño, '
               'logo, colores y nombre configurables por caja, sin rastros de Odoo.',
    'description': """
Tema y marca blanca del TPV
===========================
Adaptación a la suite AL del tema del TPV de Mobilize
(``mblz_pos_theme``), con marca neutra por defecto.

* **Marca por caja** en Ajustes ▸ Punto de venta ▸ Apariencia: nombre, logo,
  icono de la pestaña y colores primario, secundario, acento y fondo. Sin
  configurar, se usan el nombre y el logo de la compañía.
* **Sistema de diseño** (tokens ``--alpt-*``) con modo claro y oscuro: el
  contraste del texto sobre los colores elegidos se ajusta solo (AA).
* **Sin rastros de Odoo**: título y favicon del TPV, app instalable con el
  nombre de la caja, recibo sin «Powered by Odoo» y mensajes del sistema con
  el nombre de la marca.
* **Pago en el panel de la orden** (sin cambiar de pantalla), pantalla del
  cliente con la marca y compatibilidad con los módulos TPV de la suite
  (``al_pos_product_view``, ``al_pos_vendedor``, ``al_l10n_pe_edi_pos``).
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-POS/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/point_of_sale/static/description/icon.png',
    'version': '2.20261008',
    'license': 'OPL-1',
    # Solo point_of_sale: convive con los demás módulos TPV usando selectores
    # genéricos del core (ver compat_al.scss).
    'depends': ['point_of_sale'],
    'data': [
        'views/pos_index_templates.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        # Bundle principal de la UI del TPV (v19). Los SCSS van en orden:
        # variables -> tokens -> base -> componentes, porque el bundle se
        # compila como una sola unidad y los parciales dependen del anterior.
        'point_of_sale._assets_pos': [
            'al_pos_theme/static/src/scss/_variables.scss',
            'al_pos_theme/static/src/scss/_fonts.scss',
            'al_pos_theme/static/src/scss/_tokens.scss',
            'al_pos_theme/static/src/scss/_base.scss',
            'al_pos_theme/static/src/scss/components/*.scss',
            'al_pos_theme/static/src/js/**/*.js',
            'al_pos_theme/static/src/xml/order_receipt.xml',
            'al_pos_theme/static/src/xml/navbar.xml',
            'al_pos_theme/static/src/xml/product_screen.xml',
            'al_pos_theme/static/src/xml/order_summary.xml',
            'al_pos_theme/static/src/xml/payment_screen.xml',
            'al_pos_theme/static/src/xml/receipt_screen.xml',
            'al_pos_theme/static/src/xml/ticket_screen.xml',
            'al_pos_theme/static/src/xml/inline_payment.xml',
        ],
        # La pantalla del cliente es una página aparte con su propio bundle
        # (no incluye _assets_pos): se le entregan fuente, tokens y el
        # template que quita el «Powered by Odoo».
        'point_of_sale.customer_display_assets': [
            'al_pos_theme/static/src/scss/_variables.scss',
            'al_pos_theme/static/src/scss/_fonts.scss',
            'al_pos_theme/static/src/scss/_tokens.scss',
            'al_pos_theme/static/src/scss/customer_display.scss',
            'al_pos_theme/static/src/xml/customer_display.xml',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'application': False,
}
