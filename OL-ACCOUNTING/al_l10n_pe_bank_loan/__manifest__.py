# -*- coding: utf-8 -*-
{
    'name': 'PE - Préstamos y pagarés bancarios (AL)',
    'summary': 'Préstamos y pagarés con cronograma francés, alemán o al vencimiento (TEA, gracia, '
               'desgravamen y comisiones): desembolso, devengo mensual, pago de cuotas, prepago, '
               'TCEA, porción corriente y uso de la línea de crédito.',
    'description': """
Préstamos y pagarés bancarios
=============================
* **Cronograma** con la TEA y los días reales de cada periodo (base 360 o 365):
  francés (cuota fija), alemán (amortización constante) o al vencimiento;
  frecuencia mensual a anual; gracia parcial (solo intereses) o total
  (intereses capitalizados); seguro de desgravamen y comisión por cuota.
  **TCEA** con los gastos de desembolso.
* **Desembolso** al banco (4511 o 4544 del PCGE), **devengo mensual** de
  intereses (67311 / 45511) automático e idempotente, **pago de cuotas** con
  el interés realmente cobrado y **prepago** que reduce la cuota o el plazo.
* Movimientos de banco en la cuenta de pendientes del diario, listos para
  conciliar con el extracto; ITF opcional.
* Saldo de capital, **porción corriente y no corriente**, próximo
  vencimiento con aviso, uso de la **línea de crédito** del banco y cuotas en
  el **flujo de caja proyectado**.
* Préstamos en moneda extranjera (diferencia de cambio con el cierre de T.C.
  de la suite).
""",
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    # Ícono de la aplicación a la que pertenece (Tesorería).
    'icon': '/al_l10n_pe_bank_loan/static/description/icon.png',
    'version': '2.20261027',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['al_l10n_pe_treasury'],
    'data': [
        'security/ir.model.access.csv',
        'security/bank_loan_security.xml',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'views/bank_loan_views.xml',
        'views/bank_loan_account_config_views.xml',
        'wizards/bank_loan_payment_views.xml',
        'views/menus.xml',
        'data/bank_loan_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
