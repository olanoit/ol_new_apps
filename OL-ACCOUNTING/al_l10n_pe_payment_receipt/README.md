# PE - Comprobante de pago (AL)

Documentación funcional: [Comprobante de pago](../../mkdocs/content/applications/finance/accounting/payment_receipts.md)

Módulo técnico `al_l10n_pe_payment_receipt`. Recibo de ingreso / comprobante de egreso
sobre `account.payment` nativo:

- `account.journal.l10n_pe_receipt_enabled` y dos `ir.sequence` sin huecos por diario
  (`RI-<código>-`, `RE-<código>-`), creadas al activar la opción.
- `account.payment.l10n_pe_receipt_number`: se asigna en `action_post`, una sola vez
  (único por compañía); no en transferencias internas.
- PDF `report_payment_receipt_pe` con `al_report_base.report_pe_page`. El detalle sale
  de las conciliaciones parciales del asiento del pago o, sin asiento (diario sin
  cuenta de pendientes, v19), del reparto del importe entre `invoice_ids`.
- Plantilla de correo con el PDF adjunto.

Origen: proceso P1 de `docs/pagos/PLAN_P1_P3.md`.
