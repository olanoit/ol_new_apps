# PE - Cuota fija en soles (AL)

Documentación funcional: [Cuota fija en soles](../../mkdocs/content/applications/finance/accounting/payment_terms_pen.md)

Módulo técnico `al_l10n_pe_payment_term_currency`:

- `account.payment.term.line.l10n_pe_company_currency`: cuota fija en la moneda de la compañía.
- `account.payment.term._compute_terms`: llama a `super()` y, si la factura está en otra moneda,
  rehace las cuotas marcadas (salvo la última) con `value_amount` en soles y
  `value_amount × rate` en la moneda de la factura (`rate` = el de la factura, como el nativo,
  con el redondeo de efectivo nativo) y recalcula la última cuota como saldo. No reescribe el
  método.

Origen: proceso P7 de `docs/pagos/ANALISIS_PAGOS_INVERAGRO.md` (reemplaza a
`dv_l10n_pe_account_payment_term_foreign_currency` de Inveragro; en Odoo 19 la cuota fija ya es
coherente y la detracción la separa `al_l10n_pe_detraction`).
