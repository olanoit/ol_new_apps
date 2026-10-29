# -*- coding: utf-8 -*-
{
    'name': 'PE - Costeo de órdenes de fabricación',
    'summary': 'Costo hora desde la planilla, tareo por orden, cierre de costos del mes '
               '(ajuste de mano de obra y prorrateo de CIF) y costo por elemento.',
    'description': """
Costeo de órdenes de fabricación (Perú)
=======================================
* Costo hora de cada empleado desde la planilla cerrada (ingresos, aportes del
  empleador y provisiones de beneficios sociales entre las horas laboradas);
  queda como su costo hora en Odoo.
* Importar el tareo (Excel) como registros de tiempo de las órdenes.
* Cierre de costos del mes: ajuste de la mano de obra al costo hora real y
  prorrateo de los gastos indirectos (CIF) publicados en el mes por horas,
  cantidad, peso, volumen o costo directo. Se carga con un costo en destino
  sobre las órdenes terminadas (asiento contra la 71 del PCGE).
* Análisis del costo de cada orden por elemento: material, máquina, mano de
  obra, ajuste de mano de obra y CIF.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-INVENTORY/Apps',
    'icon': '/al_l10n_pe_mrp_cost/static/description/icon.png',
    'version': '1.20261029',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['mrp_workorder', 'mrp_landed_costs', 'hr_hourly_cost', 'al_hr_pe'],
    'external_dependencies': {'python': ['openpyxl']},
    'data': [
        'data/product_data.xml',
        'views/l10n_pe_mrp_labor_rate_views.xml',
        'views/l10n_pe_mrp_cost_pool_views.xml',
        'views/l10n_pe_mrp_cost_close_views.xml',
        'views/l10n_pe_mrp_cost_analysis_views.xml',
        'wizards/l10n_pe_mrp_timesheet_import_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu.xml',
        'security/ir.access.csv',
    ],
    'installable': True,
    'application': False,
}
