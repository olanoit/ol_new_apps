# PE - Cartas fianza (AL)

Documentación funcional: [Cartas fianza](../../mkdocs/content/applications/finance/treasury/bank_guarantees.md)

Módulo `al_l10n_pe_bank_guarantee` (depende de `al_l10n_pe_treasury`).

- `l10n_pe.bank.guarantee`: emitidas (`issued`) o recibidas (`received`); estados borrador,
  vigente, vencida, renovada, liberada, ejecutada, anulada.
- Comisión de las emitidas: tasa por trimestre o fracción con mínimo, debitada en la cuenta de
  pagos pendientes del banco (6391); ITF opcional.
- Cuentas de orden opcionales (`res.company.l10n_pe_guarantee_memo`): 0113/0114 emitidas,
  0129/0126 recibidas; se extornan al liberar o ejecutar; la renovación registra solo la
  diferencia de importe.
- `claim_deadline` = vencimiento + 15 días (art. 1898 del Código Civil): fecha límite de la
  actividad de aviso de las recibidas. Cron `_cron_l10n_pe_bank_guarantees`.
- Amplía `_l10n_pe_credit_usage` con las emitidas vigentes o vencidas.
