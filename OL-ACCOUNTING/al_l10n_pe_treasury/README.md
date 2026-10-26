# Tesorería (AL)

Documentación funcional: [Tesorería](../../mkdocs/content/applications/finance/treasury.md)

Aplicación `al_l10n_pe_treasury` (menú raíz **Tesorería**). Análisis y plan en
[docs/tesoreria/](../../docs/tesoreria/PLAN_TESORERIA.md).

- `l10n_pe.treasury.position` (+ `.line`): una línea por diario de banco o caja. Saldo de la
  `default_account_id` a la fecha (`amount_currency` en diarios en moneda extranjera), último
  `balance_end_real` de extracto, pagos confirmados sin conciliar (`is_matched = False`) como
  tránsito, líneas aprobadas y sin pagar de las programaciones, saldo mínimo y sobregiro del
  diario. Restringidas = `l10n_pe_forecast_exclude` (del flujo de caja): disponible 0. Cron
  diario `_cron_l10n_pe_daily_position` (una posición por compañía y día).
- `l10n_pe.treasury.transfer`: dos `account.payment` (salida y entrada) con
  `destination_account_id = company.transfer_account_id`, conciliados entre sí. En la compra o
  venta de moneda, `l10n_pe_agreed_rate` (de `al_l10n_pe_currency`) en el pago en moneda
  extranjera si se valoriza al T.C. pactado; si no, asiento de diferencia de cambio (676/776)
  contra la cuenta de transferencias. El ITF lo crea `al_l10n_pe_itf` (se sobrescribe
  `_l10n_pe_itf_applies` para las transferencias marcadas). Aprobación desde un importe.
- `l10n_pe.treasury.payment.plan` (+ `.line`): apuntes `liability_payable` abiertos;
  aprobación simple o doble (`res.company` umbrales), quien prepara no aprueba. «Pagar» usa
  `account.payment.register` por proveedor (agrupado si todo es total; uno por documento si hay
  parciales). Gancho `_l10n_pe_after_pay` (lo usa `al_l10n_pe_treasury_batch_payment`).
- `l10n_pe.treasury.credit.line`: uso calculado por `_l10n_pe_credit_usage`, que amplían
  `al_l10n_pe_bank_loan` y `al_l10n_pe_bank_guarantee`.
- Bancarización en `account.payment.action_post`: medio de pago 008/009 (o diario de caja sin
  medio) desde S/ 2 000 o US$ 500 → aviso en el chatter o `UserError`.
- `account.journal._l10n_pe_treasury_outstanding_account(direction)`: cuenta de pendientes del
  diario para los movimientos de banco que registran los módulos de financiamiento.
- Grupos (`res.groups.privilege` «Tesorería»): Usuario, Aprobador, Administrador.
- Menú: Posición, Operaciones (con espejos de cheques, cierres de caja y entregas a rendir),
  Financiamiento (depósitos a plazo), Planificación (flujo de caja proyectado), Configuración;
  espejo en Perú ▸ Tesorería ▸ Operaciones de tesorería.
