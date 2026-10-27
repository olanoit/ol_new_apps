{
    'name': 'PE - Pago múltiple (AL)',
    'summary': 'Un solo pago o cobro bancario que cancela documentos de varios socios, '
               'entrega anticipos y registra otros pagos sin comprobante.',
    'description': """
Pago múltiple
=============
* Documento **Pago múltiple** (egreso) o **Cobro múltiple** (ingreso) con líneas de
  tipo comprobante (cualquier socio, también parcial y en otra moneda), anticipo
  (122/422) y otro pago (cuenta libre con analítica).
* Al validar genera **un solo pago de Odoo** con una línea de banco y una
  contrapartida por línea, y concilia cada comprobante con la conciliación estándar
  (la diferencia de cambio la crea Odoo). Un movimiento del extracto, un pago.
* Imprime el comprobante de egreso o recibo de ingreso numerado.
* Acción **Pago múltiple** desde la lista de facturas.
* Las facturas con retención del IGV o la cuota de detracción se pagan con su propio
  flujo (CRE por proveedor, depósito en el Banco de la Nación).
""",
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    'icon': '/al_l10n_pe_payment_multi/static/description/icon.png',
    'version': '3.20261027',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['al_l10n_pe_payment_application'],
    'data': [
        'security/ir.model.access.csv',
        'security/payment_multi_security.xml',
        'data/ir_sequence_data.xml',
        'views/payment_multi_views.xml',
        'views/account_payment_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
}
