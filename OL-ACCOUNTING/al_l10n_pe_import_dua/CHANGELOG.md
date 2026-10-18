Historial de cambios — PE - DUA de importación y costos en destino (AL)
=======================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_import_dua.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 4.20261018 — 18/10/2026

- Los datos de demostración llevan nombres reales en lugar del prefijo DEMO; las bases que ya los tienen se renombran al actualizar.

## 3.20261012 — 12/10/2026

- Menú en Perú ▸ Proveedores ▸ Comprobantes.

## 2.20261012 — 12/10/2026

- Datos de demostración en «PE Company» (solo en bases con datos de demostración): importación de diez motobombas con recepción, factura del exterior, gastos del agente y la DAM publicada con su costo en destino.

## 1.20261012 — 12/10/2026

- DUA (tipo 50 y 52) como documento de compra con el número de la DAM (aduana-año-régimen-número) que leen el PLE y el SIRE.
- Liquidación de la DUA: derechos como costo en destino y base imponible con el IGV de importación (crédito fiscal).
- Percepción aduanera registrada al publicar (con al_l10n_pe_perception).
- Facturas del exterior y recepciones vinculadas; costos en destino con los derechos y los gastos de aduana.
