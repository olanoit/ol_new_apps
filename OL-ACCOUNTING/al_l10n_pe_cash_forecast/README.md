# PE - Flujo de caja proyectado (AL)

Documentación funcional: [Flujo de caja proyectado](../../mkdocs/content/applications/finance/accounting/cash_forecast.md)

Módulo técnico `al_l10n_pe_cash_forecast` (solo depende de `al_account_base`; las fuentes de
otros módulos se usan si están instaladas):

- `l10n_pe.cash.forecast`: `action_refresh` lee el saldo inicial (`asset_cash` de los diarios
  de banco y caja, sin los marcados `l10n_pe_forecast_exclude` ni la cartera de cheques de
  terceros) y genera `l10n_pe.cash.forecast.line` desde apuntes abiertos: cuentas de pendientes
  de los métodos (tránsito), por cobrar / por pagar (sin anticipos ni detracciones por cobrar),
  `l10n_latam.check` (propios `handed` y de terceros en cartera) y `l10n_pe.term.deposit`
  vigentes. Lo vencido va a la fecha «Desde».
- Escenario: `date_expected` / `amount` editados marcan `is_edited` y se reaplican por apunte
  (`move_line_id` o `source_ref`) al actualizar; las partidas `manual` se conservan.
- `l10n_pe.cash.forecast.period`: saldos encadenados (no almacenados) y real vs proyectado
  (`asset_cash` del periodo) solo en periodos terminados.
- Pivote y gráfico sobre las partidas; exportación XLSX con `xlsxwriter`.

Origen: proceso P5 de `docs/pagos/ANALISIS_PAGOS_INVERAGRO.md`.
