Historial de cambios — PE - Pagos masivos a proveedores (AL)
============================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_batch_payment.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 3.20261012 — 12/10/2026

- BCP: archivo de pago a proveedores de Telecrédito con la marca de exoneración del ITF, la modalidad de pago y, debajo de cada abono, los comprobantes que se pagan (registro 3).
- BCP: un solo abono por proveedor y cuenta aunque el lote tenga varios pagos al mismo proveedor.
- BCP: exoneración del ITF, validación del documento del beneficiario y detalle de comprobantes configurables en el diario.
- El pago a un proveedor usa por defecto su cuenta en el mismo banco del diario (la corriente antes que la de ahorros), aunque la factura traiga la de otro banco.

## 2.20261012 — 12/10/2026

- Datos de demostración en «PE Company» (solo en bases con datos de demostración): diario BCP en soles con el pago masivo y un lote validado de tres pagos a proveedores de BCP, BBVA e Interbank.

## 1.20261012 — 12/10/2026

- Método de pago «Pago masivo (TXT de banco peruano)» en los lotes de pago, con archivo para BCP, BBVA, Interbank, Scotiabank y Banco de la Nación.
- Cuenta del proveedor o su CCI de 20 dígitos según el banco; controles de formato, cuenta de cargo, moneda, documento y detracciones al validar el lote.
- Número de registros y total del archivo guardados en el lote.
