# PE - Préstamos y pagarés bancarios (AL)

Documentación funcional: [Préstamos y pagarés bancarios](../../mkdocs/content/applications/finance/treasury/bank_loans.md)

Módulo `al_l10n_pe_bank_loan` (depende de `al_l10n_pe_treasury`).

- `tools/schedule.py`: cálculo puro del cronograma (`build_schedule`, `due_dates`) e
  `irr_annual` para la TCEA. Interés por días reales: `saldo × ((1 + TEA)^(días/base) − 1)`;
  la cuota francesa es `saldo / Σ Π 1/(1 + iₖ)` para que quede fija con meses desiguales.
- `l10n_pe.bank.loan` + `l10n_pe.bank.loan.line`; cuentas por tipo y moneda en
  `l10n_pe.bank.loan.account.config` (PCGE por defecto: 4511/45511/67311, pagarés
  4544/45544/6733, 651 seguro, 6391 comisiones).
- Asientos: desembolso (cobros pendientes del diario ↔ capital), devengo lineal por días de las
  cuotas pendientes (`_l10n_pe_accrue`, idempotente), pago de cuota (`_l10n_pe_pay_line`, en
  orden), gracia total (capitaliza contra el capital), prepago (`_l10n_pe_prepay`: rehace las
  cuotas pendientes desde la fecha, cuota menor o plazo menor). ITF opcional con la regla de
  `al_l10n_pe_itf`.
- Cron diario `_cron_l10n_pe_bank_loans`: devengo al cierre del mes anterior, capitalización y
  aviso antes del vencimiento.
- Amplía `_l10n_pe_credit_usage` (saldo de capital) y las fuentes del flujo de caja
  (`category = 'loan'`).
