# -*- encoding: UTF-8 -*-
{
    'name': "PE - Datos de la ciudad",
    'summary': 'Datos de la ciudad',
    'description': "Datos de la ciudad",

    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-TOOLS/Apps',
    'version': '1.20260730',
    'license': 'LGPL-3',

    'depends': ['base_address_extended'],
    'data': [
        "data/peru.xml",
        'data/res_country_data_enforce.xml'],

    'installable': True,
    'auto_install': False,
    'application': True,
    'pre_init_hook': 'pre_init_check'
}
