# -*- coding: utf-8 -*-
{
    'name': 'Industria: Restaurante (AL)',
    'summary': 'Restaurante listo para atender: salón con mesas, comandas a cocina, división de cuentas y propinas, boleta y factura electrónica desde la caja, cobro con Yape y Plin y libro de reclamaciones.',
    'description': """
Industria: Restaurante
======================
Restaurantes, cafeterías y pollerías que atienden en mesa, para llevar y por delivery.

Paquete de industria al estilo de los de Odoo: instala las aplicaciones y los
módulos de la suite que usa el rubro y deja la base configurada (categorías,
etiquetas, opciones de inventario y la actividad CIIU 5610 de la
compañía). Lo que se configura por compañía está en Ajustes ▸ Usuarios y
compañías ▸ Industrias.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-INDUSTRIES/Apps',
    'icon': '/al_industry_restaurant/static/description/icon.png',
    'version': '4.20261027',
    'license': 'OPL-1',
    'depends': [
        'al_industry_base',
        'pos_restaurant',
        'purchase_stock',
        'al_l10n_pe_edi_pos',
        'al_pos_pe_partner_lookup',
        'al_pos_pe_wallet_qr',
        'al_pos_theme',
        'al_pos_vendedor',
        'al_l10n_pe_complaints_book',
    ],
    'data': [
        'data/al_industry_data.xml',
        'data/restaurant_data.xml',
    ],
    'demo': [
        'demo/restaurant_demo.xml',
    ],
    'installable': True,
    'application': True,
}
