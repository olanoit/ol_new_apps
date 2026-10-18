Historial de cambios — PE - Arrendamientos NIIF 16 (AL)
=======================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_lease.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 5.20261018 — 18/10/2026

- Los datos de demostración llevan nombres reales en lugar del prefijo DEMO; las bases que ya los tienen se renombran al actualizar.

## 4.20261012 — 12/10/2026

- Menú en Perú ▸ Contabilidad ▸ Arrendamientos; análisis en Informes ▸ Análisis.

## 3.20261012 — 12/10/2026

- Datos de demostración en «PE Company» (solo en bases con datos de demostración): oficina confirmada con dos facturas, almacén exento por corto plazo, montacargas en borrador y depósito remedido por el reajuste de la renta. El activo por derecho de uso lleva el tipo de activo 1 de la tabla 18 que exige el PLE 7.1.

## 2.20261010 — 10/10/2026

- Remedición (cuota, plazo o tasa) con ajuste del pasivo y del derecho de uso, y terminación anticipada con baja de ambos y su resultado; historial por contrato.
- Contratos en moneda extranjera: derecho de uso al tipo de cambio del inicio y diferencia de cambio del pasivo a fin de mes (cron y botón).
- Subcuentas 4521/4522 del pasivo (largo y corto plazo), producto de la cuota para el IGV y la detracción, saldos del pasivo según la tabla y el libro, y reporte de diferencias temporales del impuesto a la renta (impuesto diferido).

## 1.20261010 — 10/10/2026

- Primera versión: contratos de arrendamiento NIIF 16 con valor presente, derecho de uso en activos fijos, pasivo en préstamos, facturas del arrendador por cuota, exenciones de corto plazo y bajo valor, y menú Perú ▸ Arrendamientos.
