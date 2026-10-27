{
    'name': 'Tablero Perú (AL)',
    'summary': 'Tablero de la app Perú: ventas, compras e IGV, comprobantes electrónicos, '
               'detracciones, retenciones, percepciones, tesorería y declaraciones.',
    'description': """
Tablero Perú
============
Tablero nativo de Odoo 19 (hoja de cálculo de la app Tableros) que abre la app **Perú**:

* **Ventas, compras e IGV** del periodo: base, débito y crédito fiscal, IGV resultante,
  ventas y compras por mes, comprobantes por tipo y principales clientes y proveedores.
* **Comprobantes electrónicos**: por enviar, con error, bajas pendientes y aceptados; guías
  de remisión y comprobantes de retención por enviar.
* **Detracciones, retenciones y percepciones** de ventas y compras.
* **Tesorería**: por cobrar y por pagar, letras y tipo de cambio SUNAT.
* **Declaraciones mensuales** (IGV y renta).

Cada bloque aparece solo si su módulo está instalado: el tablero se rearma solo al instalar
o desinstalar módulos de la localización. Filtros por periodo y por cliente o proveedor.
""",
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    'version': '2.20261027',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['al_account_base', 'l10n_pe_edi', 'spreadsheet_dashboard'],
    'data': [
        'security/ir.model.access.csv',
        'security/dashboard_security.xml',
        'data/dashboard_data.xml',
        'views/dashboard_tax_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
}
