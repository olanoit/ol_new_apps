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
    'version': '12.20261027',
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
        # Mejoras E5-E8 (docs/farmacia/MEJORAS_PROCESOS.md): crónicos y
        # recompra, faltantes y sugerido de compra, fidelización sin receta.
        'al_pharmacy_care',
        'al_pharmacy_replenishment',
        'al_pharmacy_loyalty',
        # E9-E10: tienda en línea con receta y convenios con EPS.
        'al_pharmacy_website',
        'al_pharmacy_insurance',
        # Tarjetas de regalo y monedero con el criterio de SUNAT (097-2010).
        'al_l10n_pe_pos_loyalty',
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
        # Cobro con tarjeta y Yape en la caja: un método por pasarela, con su logo.
        'al_pos_payment_gateway',
        'al_payment_niubiz',
        'al_payment_culqi',
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
