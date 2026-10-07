# -*- encoding: UTF-8 -*-
{
    'name': "PE - Datos de la ciudad",
    'summary': 'Datos de la ciudad',
    'description': "Datos de la ciudad",

    # Módulo de Laxicon Solution (l10n_pe_city), adaptado a la suite: se
    # conserva su autoría y licencia; CRISTÓBAL OCH mantiene la copia.
    'author': 'Laxicon Solution',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.laxicon.in',
    'countries': ['pe'],
    'category': 'Accounting/Localizations',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/contacts/static/description/icon.png',
    'version': '3.20261008',
    'license': 'LGPL-3',

    'depends': ['base_address_extended'],
    'data': [
        "data/peru.xml",
        'data/res_country_data_enforce.xml'],

    'installable': True,
    'auto_install': False,
    'application': False,
}
