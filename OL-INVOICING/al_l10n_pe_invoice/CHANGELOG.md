Historial de cambios — PE - Comprobantes Electrónicos (AL)
==========================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_invoice.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 11.20260828 — 27/09/2026

- Las exportaciones y las operaciones gratuitas tienen su propia fila en el pie (**Op. exportación**, **Op. gratuitas**): antes la exportación no se sumaba y lo gratuito salía como «otros tributos», y el PDF no cuadraba con el XML.
- La fila **Descuento** muestra el descuento real sin IGV, tanto el porcentaje por línea como el descuento global; antes salía 0.00 o no salía.
- Las notas de crédito y de débito imprimen el **documento que modifican** y el **motivo**, también en A4 (la nota de débito antes no lo mostraba en ningún formato).
- Las cuotas de crédito se siguen viendo al reimprimir una factura ya pagada (antes salía una sola cuota de 0.00).
- La moneda se imprime según el documento (una factura en euros ya no dice «SOLES») y el IGV muestra la tasa aplicada, por ejemplo **IGV (10%)**.

## 14/09/2026

- Certificados digitales dentro de la sección **Comprobantes electrónicos** de la configuración de la app Perú.

## 8.20260828 — 28/08/2026

- Los certificados digitales, antes solo en Contabilidad, también desde la app Perú.

## 7.20260827 — 27/08/2026

- El descuento global vuelve a imprimirse; en Odoo 19 salía siempre en cero.
- Pruebas del desglose de IGV, exonerado, inafecto e ICBPER, moneda extranjera, notas de crédito, cuotas y descuento.

## 6.20260719 — 25/07/2026

- Versión para Odoo 19: formatos A4 y ticket, QR del XML firmado, monto en letras nativo y desglose tributario almacenado.
