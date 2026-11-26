# -*- coding: utf-8 -*-
{
    'name': 'PE - Reportes PDF en el navegador en los ajustes de Perú (AL)',
    'summary': 'Muestra en Ajustes ▸ Perú la opción de abrir los reportes PDF '
               'en el navegador, además de en Ajustes generales.',
    'description': """
Reportes PDF en el navegador en los ajustes de Perú
===================================================
Puente entre la aplicación Perú y «Reportes PDF en el navegador»
(``al_report_preview``): agrega a **Ajustes ▸ Perú** el bloque **Reportes
PDF**, con el mismo ajuste de Ajustes generales (todos los reportes o solo
los elegidos) y el acceso a la lista para elegir por reporte.

Se instala solo cuando están los dos módulos. Es el mismo ajuste: cambiarlo
en un lugar lo cambia en el otro.
""",
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    'icon': '/al_l10n_pe_report_preview/static/description/icon.png',
    'version': '20261126.1',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['al_account_base', 'al_report_preview'],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
}
