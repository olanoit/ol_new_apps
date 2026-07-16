# -*- coding: utf-8 -*-
{
    'name': 'Tipo de cambio Perú (SUNAT)',
    'summary': 'Tipo de cambio SUNAT (compra/venta) para USD/PEN, con '
               'actualización diaria y visualización del T.C. aplicado en '
               'facturas en moneda extranjera.',
    'description': """
Tipo de cambio Perú — refactor Odoo 19
======================================
* Tasas de **compra y venta** de SUNAT en ``res.currency.rate`` (Odoo nativo
  solo maneja una tasa única).
* Fuente principal: **TXT oficial de SUNAT** (gratuito, sin token), con
  actualización diaria vía cron. Fechas históricas vía apis.net.pe.
* Muestra en las facturas en moneda extranjera el **tipo de cambio aplicado y
  su fecha**.
* Módulo autónomo: se eliminó la dependencia ``al_base_mixin`` (los campos de
  filtro de fechas viven en el propio asistente).
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'Accounting/Localizations',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['account'],
    'external_dependencies': {'python': ['requests']},
    'data': [
        'security/ir.model.access.csv',
        'data/decimal_precision.xml',
        'data/res_currency_data.xml',
        'data/cron_data.xml',
        'wizard/create_exchange_rate_wizard.xml',
        'views/res_currency_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
}
