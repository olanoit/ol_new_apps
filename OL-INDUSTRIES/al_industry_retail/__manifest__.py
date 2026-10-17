# -*- coding: utf-8 -*-
{
    'name': 'Industria: Bodega y minimarket (AL)',
    'summary': 'Bodega o minimarket listo para vender: caja con boleta y factura electrónica, cobro con Yape y Plin, cliente por RUC o DNI, vendedor por venta, kárdex SUNAT y libro de reclamaciones.',
    'description': """
Industria: Bodega y minimarket
==============================
Bodegas, minimarkets y tiendas de barrio que venden en caja y compran a distribuidores.

Paquete de industria al estilo de los de Odoo: instala las aplicaciones y los
módulos de la suite que usa el rubro y deja la base configurada (categorías,
etiquetas, opciones de inventario y la actividad CIIU 4711 de la
compañía). Lo que se configura por compañía está en Ajustes ▸ Usuarios y
compañías ▸ Industrias.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-INDUSTRIES/Apps',
    'icon': '/al_industry_retail/static/description/icon.png',
    'version': '1.20261017',
    'license': 'OPL-1',
    'depends': [
        'al_industry_base',
        'point_of_sale',
        'purchase_stock',
        'al_l10n_pe_edi_pos',
        'al_pos_pe_partner_lookup',
        'al_pos_pe_wallet_qr',
        'al_pos_product_view',
        'al_pos_vendedor',
        'ol_stock_kardex_pe',
        'al_l10n_pe_complaints_book',
    ],
    'data': [
        'data/al_industry_data.xml',
        'data/retail_data.xml',
    ],
    'demo': [
        'demo/retail_demo.xml',
    ],
    'installable': True,
    'application': True,
}
