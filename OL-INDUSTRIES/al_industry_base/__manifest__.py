# -*- coding: utf-8 -*-
{
    'name': 'Industrias: base común (AL)',
    'summary': 'Lo que comparten los paquetes de industria: la localización peruana de la suite y '
               'el registro de cada industria, con su actividad CIIU, aplicable por compañía.',
    'description': """
Industrias: base común
======================
Los paquetes ``al_industry_<rubro>`` (farmacia, construcción, mobiliario,
bodega, restaurante, tienda en línea) siguen el modelo de los paquetes de
industria de Odoo: instalan las aplicaciones del rubro y dejan la base
configurada para empezar a trabajar.

Esta base instala la localización peruana de la suite (comprobantes
electrónicos, tipo de cambio, consulta de RUC y DNI) y el registro de cada
industria (Ajustes ▸ Usuarios y compañías ▸ Industrias): la actividad
económica principal (CIIU) del RUC y, si el rubro planifica obras, el perfil de
vertical del planificador. Se aplica a la compañía activa al instalar y a las
demás con el botón «Aplicar a la compañía activa».
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-INDUSTRIES/Apps',
    'version': '2.20261027',
    'license': 'OPL-1',
    'depends': [
        'l10n_pe',
        'l10n_pe_vat_sunat',
        'al_l10n_pe_currency',
        'al_l10n_pe_invoice',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/al_industry_views.xml',
    ],
    'installable': True,
    'application': False,
}
