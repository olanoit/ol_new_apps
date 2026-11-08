# -*- coding: utf-8 -*-
{
    'name': 'Industrias: base común (AL)',
    'summary': 'Lo que comparten los paquetes de industria que facturan desde Odoo: el '
               'registro de industrias y la localización peruana de la suite con '
               'comprobantes electrónicos.',
    'description': """
Industrias: base común
======================
Los paquetes ``al_industry_<rubro>`` (farmacia, construcción, mobiliario,
bodega, restaurante, tienda en línea) siguen el modelo de los paquetes de
industria de Odoo: instalan las aplicaciones del rubro y dejan la base
configurada para empezar a trabajar.

Esta base instala el registro de industrias (``al_industry_core``: actividad
CIIU y perfil del planificador por compañía) y la localización peruana de la
suite con comprobantes electrónicos y tipo de cambio. Los paquetes que no
facturan desde Odoo dependen solo de ``al_industry_core``.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-INDUSTRIES/Apps',
    'version': '3.20261108',
    'license': 'OPL-1',
    'depends': [
        'al_industry_core',
        'al_l10n_pe_currency',
        'al_l10n_pe_invoice',
    ],
    'data': [],
    'installable': True,
    'application': False,
}
