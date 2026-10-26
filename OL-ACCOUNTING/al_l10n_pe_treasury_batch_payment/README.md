# PE - Programación de pagos con lote bancario (AL)

Documentación funcional: [Tesorería](../../mkdocs/content/applications/finance/treasury.md#programacion-de-pagos)

Puente `auto_install` entre `al_l10n_pe_treasury` y `al_l10n_pe_batch_payment`: si el método
de pago de la programación es de modo `multi` (p. ej. `pe_bank_txt`), `_l10n_pe_after_pay`
crea el `account.batch.payment` con los pagos y lo enlaza (`batch_payment_id`).
