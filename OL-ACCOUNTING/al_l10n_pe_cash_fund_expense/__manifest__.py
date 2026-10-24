# -*- coding: utf-8 -*-
{
    'name': 'PE - Gastos de empleados con caja chica (AL)',
    'summary': 'Gastos pagados con una caja chica o entrega a rendir: cada gasto es la '
               'factura de su proveedor con su tipo y número de comprobante, y la rendición '
               'del fondo la paga.',
    'description': """
Gastos de empleados con caja chica
==================================
Un gasto de la app Gastos pagado con un fondo (caja chica o entrega a rendir
de *al_l10n_pe_cash_fund*) no se registra como un recibo a nombre del
empleado:

* cada gasto es la **factura de su proveedor**, con su **tipo y número de
  comprobante**, en el diario de comprobantes de gastos (con su numeración por
  documento), lista para el registro de compras y el SIRE;
* la **rendición** del fondo paga esas facturas y abona la cuenta del fondo.

Los gastos sin fondo siguen como en Odoo.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    'icon': '/hr_expense/static/description/icon.png',
    'version': '1.20261024',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['hr_expense', 'al_l10n_pe_cash_fund', 'l10n_latam_invoice_document'],
    'data': [
        'views/hr_expense_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
}
