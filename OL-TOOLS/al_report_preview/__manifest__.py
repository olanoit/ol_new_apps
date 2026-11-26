# -*- coding: utf-8 -*-
{
    'name': 'Reportes PDF en el navegador (AL)',
    'summary': 'Abre los reportes PDF en una pestaña del navegador en vez de '
               'descargarlos: todos, o solo los reportes que se elijan.',
    'description': """
Reportes PDF en el navegador
============================
Odoo descarga cada reporte PDF. Con este módulo el reporte se abre en una
pestaña nueva, con el visor del navegador, y desde ahí se imprime o se guarda.

Es configurable:

* **Ajustes ▸ Ajustes generales ▸ Reportes PDF**: se abren en el navegador
  **todos los reportes** o **solo los reportes elegidos**.
* **Cada reporte** (Ajustes ▸ Técnico ▸ Informes) decide por sí mismo: sigue
  el ajuste general, se abre siempre en el navegador o se descarga siempre.
  Así se puede, por ejemplo, abrir solo las facturas en el navegador, o
  abrir todo menos las etiquetas.

Convive con Odoo: la ruta nativa del reporte se sigue usando (``super()``),
solo se le agrega la cabecera para mostrarlo en línea con su nombre de
archivo. Si el navegador bloquea la pestaña o falta wkhtmltopdf, el reporte
sigue el flujo nativo y se descarga.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-TOOLS/Apps',
    'icon': '/al_report_preview/static/description/icon.png',
    'version': '20261126.1',
    'license': 'OPL-1',
    'depends': ['web', 'base_setup'],
    'data': [
        'views/ir_actions_report_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'al_report_preview/static/src/**/*',
        ],
    },
    'installable': True,
    'application': False,
}
