Historial de cambios — PE - Pagos masivos a proveedores (AL)
============================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_batch_payment.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 1.20261012 — 12/10/2026

- Método de pago «Pago masivo (TXT de banco peruano)» en los lotes de pago, con archivo para BCP, BBVA, Interbank, Scotiabank y Banco de la Nación.
- Cuenta del proveedor o su CCI de 20 dígitos según el banco; controles de formato, cuenta de cargo, moneda, documento y detracciones al validar el lote.
- Número de registros y total del archivo guardados en el lote.
