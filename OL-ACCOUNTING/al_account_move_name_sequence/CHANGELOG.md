Historial de cambios — Numeración de asientos por secuencia (AL)
================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_account_move_name_sequence.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 9.20260828 — 27/09/2026

- Un comprobante devuelto a borrador conserva su Serie CPE aunque el diario tenga varias series. Antes la perdía y, al volver a publicarlo, quedaba sin serie.
- Los tipos de documento distintos de factura, boleta y sus notas de crédito y débito ya no se numeran con la secuencia de la serie.
- Las series de nota de crédito y de débito deben empezar con la letra del comprobante (F o B/E) y no pueden repetirse entre series de la misma compañía, para no emitir números duplicados.
- Con varias compañías, cada una ve solo sus Series CPE.

## 8.20260828 — 14/09/2026

- Series CPE y Tipos de documento en **Perú ▸ Configuración ▸ Comprobantes electrónicos**.

## 7.20260828 — 28/08/2026

- Series CPE y catálogo de tipos de documento accesibles desde la app Perú.

## 6.20260721 — 25/07/2026

- Series CPE con series rectificativas de nota de crédito y débito.
- Numeración opcional por diario, con prefijos simples y botones Generar.
