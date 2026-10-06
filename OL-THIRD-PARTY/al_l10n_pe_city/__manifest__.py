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
    'version': '2.20260730',
    'license': 'LGPL-3',

    'depends': ['base_address_extended'],
    'data': [
        "data/peru.xml",
        'data/res_country_data_enforce.xml'],

    'installable': True,
    'auto_install': False,
    'application': False,
}
