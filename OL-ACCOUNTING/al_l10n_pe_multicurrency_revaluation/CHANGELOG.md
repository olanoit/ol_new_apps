Historial de cambios — PE - T.C. compra/venta en ganancias y pérdidas no realizadas
===================================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_multicurrency_revaluation.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 2.20260916 — 27/09/2026

- Si se escribe a mano un tipo de cambio en el filtro del informe, ese valor se usa también en las cuentas marcadas con T.C. compra o venta.
- El tipo de T.C. de la cuenta deja de ser obligatorio al editar la cuenta: sin elegirlo se usa el genérico del informe.

## 16/09/2026

- Primera versión para Odoo 19: T.C. compra o venta por cuenta, columna T.C., cabecera en soles por unidad y etiqueta del asiento de ajuste.
