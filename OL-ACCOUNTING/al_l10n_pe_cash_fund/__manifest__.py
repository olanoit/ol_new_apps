# -*- coding: utf-8 -*-
{
    'name': 'PE - Entregas a rendir y caja chica (AL)',
    'summary': 'Entregas a rendir y cajas chicas a cargo de un responsable: '
               'aprobación, entrega, rendición con comprobantes y planilla de '
               'movilidad, devolución, reembolso o reposición, con sus asientos.',
    'description': """
Entregas a rendir y caja chica
==============================
El dinero que la empresa entrega a un trabajador para un encargo o para una caja
chica queda en su cuenta por cobrar (PCGE 1413 «Personal - Entregas a rendir
cuenta») hasta que lo rinde:

* **Entrega a rendir**: solicitud, aprobación (contabilidad), entrega con un
  pago del banco o la caja, rendiciones y cierre con la **devolución** de lo no
  gastado o el **reembolso** de lo gastado de más.
* **Caja chica** (fondo fijo): apertura con su monto fijo, rendiciones y
  **reposición** de lo rendido.
* **Rendición**: los comprobantes del proveedor (facturas, boletas, recibos por
  honorarios ya registrados) se pagan con el fondo y quedan conciliados, y los
  **gastos de movilidad** se sustentan con la planilla.
* **Planilla de gastos de movilidad** (art. 37 a1 de la Ley del Impuesto a la
  Renta y art. 21 v de su Reglamento): número correlativo, trabajador, fecha,
  motivo, destino y monto; aviso del exceso sobre el tope diario (4 % de la
  RMV), que no es deducible; PDF con el formato común.
* Fondos vencidos («Por rendir vencidas»), liquidación del fondo en PDF,
  cuentas, diario y tope configurables por compañía y multicompañía.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/al_l10n_pe_cash_fund/static/description/icon.png',
    'version': '3.20261027',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['account', 'analytic', 'l10n_pe', 'al_account_base', 'al_report_base'],
    'data': [
        'security/ir.model.access.csv',
        'security/cash_fund_security.xml',
        'data/ir_sequence_data.xml',
        'views/cash_fund_views.xml',
        'views/cash_settlement_views.xml',
        'views/account_payment_views.xml',
        'views/res_config_settings_views.xml',
        'reports/cash_fund_reports.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
