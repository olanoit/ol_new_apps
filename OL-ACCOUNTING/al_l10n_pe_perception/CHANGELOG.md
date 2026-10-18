Historial de cambios — PE - Percepciones del IGV (AL)
=====================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_perception.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 4.20261018 — 18/10/2026

- Los datos de demostración llevan nombres reales en lugar del prefijo DEMO; las bases que ya los tienen se renombran al actualizar.

## 3.20261012 — 12/10/2026

- Menús en Perú ▸ Clientes y Proveedores ▸ Detracciones, retenciones y percepciones; resúmenes en SUNAT ▸ Declaraciones.

## 2.20261012 — 12/10/2026

- Datos de demostración en «PE Company» (solo en bases con datos de demostración): agente de percepción con tres ventas, dos cobradas con su comprobante de percepción, y dos percepciones sufridas (proveedor agente e importación).

## 1.20261012 — 12/10/2026

- Primera versión: cálculo en la factura (2 %, 0,5 % y 1 %, con las exclusiones del reglamento), XML de la factura (operación 2001, cargo del catálogo 53 y monto con la percepción) y leyenda en el PDF.
- Comprobante de percepción electrónico (tipo 40, serie P001) desde el cobro o las facturas: factor de seis decimales, tipo de cambio de la fecha de cobro, asiento conciliado, envío por el operador de la compañía, reversión y PDF.
- Percepciones que nos cobran (comprobante del proveedor, factura o DUA) con su asiento, y resúmenes por periodo para los F.V. 697 y 621.
