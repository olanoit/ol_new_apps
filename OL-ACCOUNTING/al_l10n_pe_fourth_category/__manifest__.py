# -*- coding: utf-8 -*-
{
    'name': 'PE - Retención de renta de 4.ª categoría (AL)',
    'summary': 'Recibos por honorarios: retención del 8 % sobre el tope, suspensión '
               '(Formulario 1609), reporte y archivo .4ta para la PLAME y certificado anual.',
    'description': """
Retención de renta de 4.ª categoría
===================================
El agente de retención retiene el impuesto a la renta de los prestadores de
servicios independientes al pagar sus recibos por honorarios:

* **Retención automática** en el recibo por honorarios (documento 02) de
  proveedor: 8 % del importe total cuando el recibo supera S/ 1 500 y la
  compañía es agente de retención. La cuenta por pagar queda por el neto y la
  retención en la 40172 (configurable). Tasa, tope y cuenta en Ajustes.
* **Suspensión de retenciones**: constancia del Formulario Virtual 1609 por
  prestador, vigente desde el día siguiente a su emisión hasta el 31 de
  diciembre; con constancia vigente el recibo no lleva retención.
* **Retenciones del mes (PLAME)**: recibos pagados en el periodo, con totales
  y el archivo de importación .4ta (estructura 20 del anexo 3 de la planilla
  electrónica) para el PDT PLAME, formulario 0601.
* **Certificado de rentas y retenciones** de 4.ª categoría por ejercicio para
  el prestador (art. 45 del Reglamento de la Ley del Impuesto a la Renta).
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-ACCOUNTING/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/account/static/description/icon.png',
    'version': '4.20261018',
    'license': 'OPL-1',
    'depends': [
        'al_account_base',
        'al_report_base',
        'l10n_pe',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'views/res_config_settings_views.xml',
        'views/fourth_category_suspension_views.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'views/fourth_category_report_views.xml',
        'reports/fourth_category_certificate_report.xml',
        'views/menus.xml',
    ],
    # Solo en bases con datos de demostración, en «PE Company» (l10n_pe).
    'demo': ['demo/al_l10n_pe_fourth_category_demo.xml'],
    'installable': True,
    'application': False,
}
