# PE - DUA de importación y costos en destino (AL)

Documentación funcional: [DUA de importación](../../mkdocs/content/applications/finance/accounting/import_dua.md)

Módulo `al_l10n_pe_import_dua` para Odoo 19.

- La DUA (DAM tipo 50; 52 la simplificada) es una factura de proveedor a nombre
  de la Aduana con el número de la DAM en sus partes (`l10n_pe_dua_*`), que arman
  `l10n_latam_document_number` (`118-2026-10-204518`).
- «Generar líneas de la DUA»: derechos (ad valorem, ISC, otros) como líneas de
  costo en destino y la base imponible con el IGV de compras más su compensación
  en la cuenta puente (`res.company.l10n_pe_dua_offset_account_id`).
- Al publicar, la percepción aduanera crea un `l10n_pe.perception.received`
  (tipo importación, documento DUA) si `al_l10n_pe_perception` está instalado.
- Facturas del exterior: el campo oficial `l10n_pe_dua_invoice_id`
  (`l10n_pe_reports`), editado desde la DUA.
- «Costos en destino»: `stock.landed.cost` sobre las recepciones con las líneas de
  costo de la DUA y de los gastos de aduana, con el método de reparto elegido.

Depende de `al_account_base`, `l10n_pe_reports`, `stock_landed_costs` y
`purchase_stock`. Datos de demostración: `tools/import_dua_demo_data.py`.
