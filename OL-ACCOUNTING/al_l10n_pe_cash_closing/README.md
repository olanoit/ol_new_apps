# PE - Cierre de caja y arqueo (AL)

Documentación funcional: [Cierre de caja y arqueo](../../mkdocs/content/applications/finance/accounting/cash_closing.md)

Módulo técnico `al_l10n_pe_cash_closing`:

- `l10n_pe.cash.closing` (único por caja y fecha): saldo según libros = suma de los apuntes
  publicados del diario en sus cuentas de liquidez (`default_account_id` + `payment_account_id`
  de sus métodos), con `amount_currency` si la caja es en moneda extranjera. Los movimientos
  del día se agrupan por asiento y se descartan los que suman cero (extracto que cruza
  pendientes contra la caja). Categoría por `origin_payment_id` (cobro, pago, transferencia a
  `transfer_account_id`) y venta al contado / cobranza por `reconciled_invoice_ids`.
- Arqueo: `l10n_pe.cash.closing.count` por `l10n_pe.cash.denomination` (datos BCRP PEN/USD).
- `action_close`: asiento de la diferencia contra `loss_account_id` / `profit_account_id` del
  diario (o `shortage_account_id` + socio); `account.move._post` y `button_draft` bloquean los
  asientos de una caja con un cierre cerrado en esa fecha o posterior.
- `action_reopen` (administrador de contabilidad, del más reciente al más antiguo): anula la
  diferencia con `button_cancel`.
- PDF con `al_report_base.report_pe_page`; `i18n/es.po` propio (mail.thread).

Origen: proceso P4 de `docs/pagos/ANALISIS_PAGOS_INVERAGRO.md`.
