# PE - Pago múltiple (AL)

Documentación funcional: [Pago múltiple](../../mkdocs/content/applications/finance/accounting/multiple_payments.md)

Módulo técnico `al_l10n_pe_payment_multi`:

- `l10n_pe.payment.multi`: líneas de tipo comprobante (apunte abierto por cobrar o por
  pagar de cualquier socio), anticipo (cuenta de `al_l10n_pe_payment_application`) y
  otro pago (cuenta libre con `analytic.mixin`). Importe en la moneda de la línea,
  convertido al cambio de la fecha del pago.
- Al validar crea **un** `account.payment` con el hook nativo `line_ids` del `create`
  (línea de liquidez en la cuenta de pendientes del método, o la de Odoo con
  `force_payment_move`, y una contrapartida por línea marcada con
  `account.move.line.l10n_pe_payment_multi_line_id`) y concilia cada comprobante con
  `reconcile()`; la diferencia de cambio la crea Odoo.
- `account.payment._synchronize_to_moves` no toca los pagos de un pago múltiple (la
  sincronización nativa supone una sola contrapartida); `action_draft` y `action_cancel`
  del pago se bloquean fuera del documento.
- Excluye la cuota de detracción (cuentas de `al_l10n_pe_detraction`) y rechaza las
  facturas con `l10n_pe_retention_applies` (CRE por proveedor).
- Comprobante de pago (`al_l10n_pe_payment_receipt`): socio por comprobante y anticipos
  detallados.
- Acción de servidor **Pago múltiple** en la lista de facturas.

Origen: proceso P2 de `docs/pagos/ANALISIS_PAGOS_INVERAGRO.md`.
