# -*- coding: utf-8 -*-
{
    'name': 'PE - Base Contabilidad (AL)',
    'summary': 'Personalizaciones genéricas de la localización contable '
               'peruana: glosa en asientos/líneas, menú "Perú" y utilidades '
               'compartidas.',
    'description': """
Base de contabilidad Perú
=========================
Módulo base y liviano del que dependen las demás personalizaciones AL de la
localización peruana. Provee:

* Glosa (`l10n_pe_gloss`) en asientos contables y sus líneas.
* Menú raíz "Perú" y su rama de Configuración.
* Utilidad `account.move.l10n_pe_is_pe()`.

Sin código muerto: reemplaza a la versión previa que arrastraba placeholders y
campos sin uso.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-ACCOUNT/Apps',
    'version': '2.20260815',
    'license': 'OPL-1',
    'depends': ['account'],
    'data': [
        'views/res_company_views.xml',
        'views/res_config_settings_views.xml',
        'views/account_move_views.xml',
        'views/pe_base_views.xml',
        'views/menu_pe.xml',
    ],
    'installable': True,
    'application': False,
}
