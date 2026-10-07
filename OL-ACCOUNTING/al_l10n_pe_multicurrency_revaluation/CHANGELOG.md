Historial de cambios — PE - T.C. compra/venta en ganancias y pérdidas no realizadas
===================================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_multicurrency_revaluation.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 4.20261008 — 08/10/2026

- Ícono nativo de la app de Odoo a la que pertenece (sin imágenes propias ni el logo de la Marca Perú).

## 3.20261007 — 07/10/2026

- Corregido: las cuentas con T.C. compra o venta se revaluaban con el que SUNAT muestra con fecha del informe, que es el cierre del día hábil anterior. Ahora usan el cierre de operaciones de la fecha del informe (art. 34 del Reglamento de la LIR), que SUNAT publica con fecha del día siguiente.

## 2.20260916 — 27/09/2026

- Si se escribe a mano un tipo de cambio en el filtro del informe, ese valor se usa también en las cuentas marcadas con T.C. compra o venta.
- El tipo de T.C. de la cuenta deja de ser obligatorio al editar la cuenta: sin elegirlo se usa el genérico del informe.

## 16/09/2026

- Primera versión para Odoo 19: T.C. compra o venta por cuenta, columna T.C., cabecera en soles por unidad y etiqueta del asiento de ajuste.
