# -*- coding: utf-8 -*-
{
    'name': 'PE - Cuentas Destino (dinámica 6↔9)',
    'summary': 'Genera automáticamente el asiento de destino (clase 6 a 9 o '
               'viceversa) según los porcentajes configurados por cuenta.',
    'description': """
Cuentas de destino — dinámica de cuentas peruana
================================================
Al contabilizar un comprobante, las cuentas de gasto por naturaleza (clase 6)
se reflejan en cuentas por función/destino (clase 9), o viceversa, usando la
cuenta de carga (78/79) como contrapartida.

* Configuración por cuenta: cuentas destino con porcentajes (suma 100 %) y
  cuenta de carga.
* Asiento de destino generado automáticamente al postear, en el diario de
  destinos elegido en Ajustes ▸ Perú ▸ Asientos de destino.

Alcance: solo la dinámica del asiento de destino. La glosa, el menú "Perú" y
utilidades genéricas viven en el módulo base ``al_account_base``.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-ACCOUNTING/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/account/static/description/icon.png',
    'version': '10.20261008',
    'license': 'OPL-1',
    'depends': ['account', 'analytic', 'l10n_pe', 'al_account_base'],
    'data': [
        'security/ir.model.access.csv',
        'security/destination_security.xml',
        'views/res_config_settings_views.xml',
        'views/res_company_views.xml',
        'views/account_account_views.xml',
        'views/account_destinies_views.xml',
        'views/account_move_views.xml',
        'views/account_analytic_account_views.xml',
        'wizards/destination_period_wizard_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
}
