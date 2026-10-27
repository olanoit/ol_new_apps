# -*- coding: utf-8 -*-
{
    'name': 'Industria: Tienda en línea (AL)',
    'summary': 'Tienda en línea lista para vender: catálogo web, checkout con RUC o DNI y ubigeo, pagos con Culqi, Niubiz o Izipay, boleta y factura electrónica y libro de reclamaciones virtual.',
    'description': """
Industria: Tienda en línea
==========================
Comercios que venden por su propia web con pago en línea y despacho a domicilio.

Paquete de industria al estilo de los de Odoo: instala las aplicaciones y los
módulos de la suite que usa el rubro y deja la base configurada (categorías,
etiquetas, opciones de inventario y la actividad CIIU 4791 de la
compañía). Lo que se configura por compañía está en Ajustes ▸ Usuarios y
compañías ▸ Industrias.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-INDUSTRIES/Apps',
    'icon': '/al_industry_ecommerce/static/description/icon.png',
    'version': '2.20261027',
    'license': 'OPL-1',
    'depends': [
        'al_industry_base',
        'website_sale_stock',
        'al_website_sale_pe',
        'al_payment_culqi',
        'al_payment_niubiz',
        'al_payment_izipay',
        'ol_stock_kardex_pe',
        'al_l10n_pe_complaints_book',
    ],
    'data': [
        'data/al_industry_data.xml',
        'data/ecommerce_data.xml',
    ],
    'demo': [
        'demo/ecommerce_demo.xml',
    ],
    'installable': True,
    'application': True,
}
