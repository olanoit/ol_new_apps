# -*- coding: utf-8 -*-
{
    'name': 'Industria: Farmacia y botica (AL)',
    'summary': 'Farmacia o botica lista para vender: caja con boleta y factura electrónica, lotes con vencimiento y salida FEFO, datos DIGEMID del producto y libro de reclamaciones.',
    'description': """
Industria: Farmacia y botica
============================
Farmacias, boticas y droguerías minoristas que venden en caja, compran por lote y controlan vencimientos.

Paquete de industria al estilo de los de Odoo: instala las aplicaciones y los
módulos de la suite que usa el rubro y deja la base configurada (categorías,
etiquetas, opciones de inventario y la actividad CIIU 4772 de la
compañía). Lo que se configura por compañía está en Ajustes ▸ Usuarios y
compañías ▸ Industrias.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-INDUSTRIES/Apps',
    'icon': '/al_industry_pharmacy/static/description/icon.png',
    'version': '7.20261018',
    'license': 'OPL-1',
    'depends': [
        'al_industry_base',
        'al_pharmacy_base',
        'al_pharmacy_stock',
        'al_pharmacy_prescription',
        'al_pharmacy_pos',
        'al_l10n_pe_prescriber_cmp',
        'al_l10n_pe_pharmacy_controlled',
        'al_l10n_pe_pharmacy_digemid',
        'point_of_sale',
        'purchase_stock',
        'sale_stock',
        'product_expiry',
        'sale_margin',
        'pos_loyalty',
        'al_l10n_pe_edi_pos',
        'al_pos_pe_partner_lookup',
        'al_pos_pe_wallet_qr',
        'al_pos_theme',
        'al_pos_product_view',
        'ol_stock_kardex_pe',
        'al_l10n_pe_complaints_book',
    ],
    'data': [
        'data/al_industry_data.xml',
        'data/pharmacy_data.xml',
    ],
    'demo': [
        'demo/pharmacy_demo.xml',
    ],
    'installable': True,
    'application': True,
}
