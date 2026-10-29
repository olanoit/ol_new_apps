# Part of OLANOIT. See LICENSE file for full copyright and licensing details.
{
    'name': 'PE - Kardex SUNAT (Formato 13.1 / 12.1)',
    'summary': 'Registro de Inventario Permanente Valorizado (13.1) y en '
               'Unidades Físicas (12.1) — formato imprimible SUNAT y kardex '
               'interactivo',
    'description': """
Kardex SUNAT para la localización peruana
=========================================
- Formato 13.1: Registro de Inventario Permanente Valorizado (XLSX/PDF).
- Formato 12.1: Registro de Inventario Permanente en Unidades Físicas.
- Kardex interactivo en pantalla con saldo corrido y navegación al
  documento origen.
- Costo promedio por almacén (opcional): cada almacén lleva su promedio y
  los traslados salen al costo del almacén de origen; el cierre mensual de
  almacén ajusta la cuenta de existencias contra la 69 y bloquea el periodo.
- Revalorizar el kardex desde una fecha del periodo abierto.
- Complementa a l10n_pe_reports_stock (EE), que genera el TXT PLE:
  reutiliza sus campos SUNAT (Tabla 5, Tabla 12, establecimiento anexo).
    """,
    'countries': ['pe'],
    'version': '16.20261028',
    'category': 'OL-INVENTORY/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/ol_stock_kardex_pe/static/description/icon.png',
    'author': 'OLANOIT',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://github.com/olanoit',
    'license': 'OPL-1',
    'depends': [
        'al_account_base',
        # Formato común de los documentos impresos (encabezado, pie y estilos).
        'al_report_base',
        'l10n_pe_reports_stock',
        'purchase_stock',
        'sale_stock',
        'stock_account',
    ],
    'external_dependencies': {'python': ['xlsxwriter']},
    'data': [
        'security/kardex_security.xml',
        'security/ir.model.access.csv',
        'security/ir_rules.xml',
        'data/ir_cron_data.xml',
        'views/kardex_line_views.xml',
        'views/kardex_report_views.xml',
        'wizards/kardex_report_wizard_views.xml',
        'views/l10n_pe_stock_cost_close_views.xml',
        'views/res_config_settings_views.xml',
        'reports/kardex_report_actions.xml',
        'reports/kardex_report_templates.xml',
        'views/menu_views.xml',
        'views/product_views.xml',
        'views/stock_move_views.xml',
    ],
    'installable': True,
    'application': False,
}
