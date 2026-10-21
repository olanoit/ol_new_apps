# PE - ITF automático (AL)

Documentación funcional: [ITF automático](../../mkdocs/content/applications/finance/accounting/itf.md)

Módulo técnico `al_l10n_pe_itf`:

- `itf_amount()` (`models/res_company.py`): 0,005 % con el redondeo del art. 13 de la Ley
  28194 (múltiplo de 0,05 inferior), en `Decimal` para no perder céntimos.
- `account.journal.l10n_pe_itf_applies` (opt-in por diario de banco).
- `account.payment.action_post`: crea un asiento propio en el diario del pago (gasto
  `res.company._l10n_pe_itf_account()`, por defecto `chart6412`, contra
  `outstanding_account_id`) y lo enlaza en `l10n_pe_itf_move_id` /
  `account.move.l10n_pe_itf_payment_id`. No toca el asiento del pago. Sin asiento del pago
  (diario sin cuenta de pendientes) no se crea: se usa la regla de conciliación «ITF»
  (`_l10n_pe_itf_reconcile_model`, creada en el post_init_hook y desde Ajustes).
- No aplica a transferencias internas (`paired_internal_transfer_payment_id` o destino
  `transfer_account_id`), a la caja ni a pagos con `l10n_pe_itf_exempt`.
- `action_draft` / `action_cancel`: el asiento del ITF se anula con `button_cancel`.
- Tasa y cuenta delegadas a la compañía raíz.

Origen: proceso P6 de `docs/pagos/ANALISIS_PAGOS_INVERAGRO.md`.
