# -*- coding: utf-8 -*-
{
    'name': 'Tesorería (AL)',
    'summary': 'Aplicación de tesorería para Perú: posición diaria de bancos y cajas, '
               'programación y aprobación de pagos, transferencias entre cuentas propias, '
               'compra y venta de moneda extranjera con T.C. pactado, líneas de crédito y '
               'control de bancarización.',
    'description': """
Tesorería
=========
Reúne el trabajo diario del tesorero en una aplicación:

* **Posición de tesorería** por cuenta y moneda: saldo contable, saldo del
  extracto, cobros y pagos en tránsito, pagos programados, saldo mínimo,
  sobregiro autorizado, cuentas restringidas (detracciones) y disponible, con
  su equivalente en soles. Una posición guardada por día (cron).
* **Programación de pagos**: propuesta de documentos por vencimiento,
  proveedor y prioridad, importe por documento, aprobación por importe (una o
  dos firmas, sin que apruebe quien prepara) y pago con el asistente de Odoo
  (actúan la retención, el ITF y el T.C. pactado de la suite).
* **Transferencias y cambio de moneda** entre cuentas propias: dos pagos
  enlazados contra la cuenta de transferencias, T.C. pactado con el banco o la
  casa de cambio, diferencia de cambio a 676/776 si se valoriza al T.C. del
  día, ITF por lado y aprobación desde un importe.
* **Líneas de crédito** por banco: límite, uso, disponible y vigencia (los
  préstamos y las cartas fianza las consumen).
* **Bancarización** (TUO de la Ley 28194): aviso o bloqueo de los pagos en
  efectivo desde S/ 2 000 o US$ 500.

Agrupa en su menú el flujo de caja proyectado, los depósitos a plazo, los
cheques, los cierres de caja y las entregas a rendir de la suite.
""",
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    'icon': '/al_l10n_pe_treasury/static/description/icon.png',
    'version': '3.20261027',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': [
        'mail',
        'al_account_base',
        'al_account_payments',
        'al_l10n_pe_itf',
        'al_l10n_pe_currency',
        'al_l10n_pe_cash_forecast',
        'al_l10n_pe_term_deposit',
        'al_l10n_pe_check',
        'al_l10n_pe_cash_closing',
        'al_l10n_pe_cash_fund',
    ],
    'data': [
        'security/treasury_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'views/account_journal_views.xml',
        'views/treasury_position_views.xml',
        'views/treasury_transfer_views.xml',
        'views/treasury_payment_plan_views.xml',
        'views/treasury_credit_line_views.xml',
        'views/account_payment_views.xml',
        'views/res_config_settings_views.xml',
        'wizards/payment_plan_propose_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
