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
- Complementa a l10n_pe_reports_stock (EE), que genera el TXT PLE:
  reutiliza sus campos SUNAT (Tabla 5, Tabla 12, establecimiento anexo).
    """,
    'countries': ['pe'],
    'version': '0.2026071601',
    'category': 'OL-INVENTORY/Apps',
    'author': 'OLANOIT',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://github.com/olanoit',
    'license': 'LGPL-3',
    'depends': [
        'l10n_pe_reports_stock',
        'stock_account',
    ],
    'external_dependencies': {'python': ['xlsxwriter']},
    'data': [
        'security/ir.model.access.csv',
        'views/kardex_line_views.xml',
        'wizards/kardex_report_wizard_views.xml',
        'reports/kardex_report_actions.xml',
        'reports/kardex_report_templates.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
}
