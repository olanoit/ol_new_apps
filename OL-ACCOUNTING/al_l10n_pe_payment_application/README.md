# PE - Anticipos y aplicación de documentos (AL)

Documentación funcional: [Anticipos y aplicación de documentos](../../mkdocs/content/applications/finance/accounting/advances.md)

Módulo técnico `al_l10n_pe_payment_application`:

- `account.payment.l10n_pe_is_advance`: `_compute_destination_account_id` devuelve la
  cuenta de anticipos de la compañía (`chart122` / `chart422` del plan, una por moneda
  opcional). No se toca la sincronización pago↔asiento.
- `l10n_pe.payment.application`: líneas sobre apuntes abiertos conciliables del socio;
  al validar, asiento en el diario de aplicaciones (`l10n_pe_application_journal`) con la
  contrapartida de cada línea al cambio de la fecha y `reconcile()` estándar (la
  diferencia de cambio la crea Odoo). Reversión con `_reverse_moves(cancel=True)`.
- `account.move.l10n_pe_advance_count` y botón «Anticipos»; aviso en el chatter al
  publicar si el socio tiene anticipos.
- Acción de servidor «Anticipos pendientes» (apuntes con saldo en las cuentas de
  anticipos).
- Hook: diario y cuentas en compañías existentes con el plan PE.

Origen: proceso P3 de `docs/pagos/PLAN_P1_P3.md`.
