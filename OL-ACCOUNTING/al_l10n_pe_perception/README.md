# PE - Percepciones del IGV (AL)

Documentación funcional: [Percepciones del IGV](../../mkdocs/content/applications/finance/fiscal_localizations/peru/perceptions.md)

Módulo `al_l10n_pe_perception` para Odoo 19.

- `product.template`: `l10n_pe_perception_type` (Apéndice 1, numerales 1-3,
  gas licuado o combustible).
- `res.partner`: `l10n_pe_perception_excluded`; `l10n_pe_is_perception_agent`
  (de `al_l10n_pe_retention`) se marca al consultar la ficha RUC si figura en
  ese padrón (`_apply_api_result`).
- `res.company`: agente de venta interna y de combustibles (delegados a la
  compañía raíz), cuentas, diarios y la secuencia P001 creada bajo demanda.
- `account.move`: régimen, tasa, base y percepción estimada
  (`_l10n_pe_perception_values`, R.S. 058-2006/SUNAT arts. 5-7 y R.S.
  128-2002/SUNAT), operación 2001 al publicar, cargo del catálogo 53 y
  `cac:PaymentTerms` «Percepcion» en el XML (`perception_xml.py`), leyenda en el
  PDF A4 de `al_l10n_pe_invoice`.
- `l10n_pe.perception` (+ líneas): comprobante de percepción tipo 40 sobre
  `l10n_pe.retention.edi.mixin` (ganchos `_l10n_pe_edi_cpe_type/_number/_export`):
  factor de 6 decimales, T.C. de la fecha de cobro, reparto proporcional en
  facturas mixtas, asiento conciliado con el exceso del cobro, envío, reversión
  RR y PDF con `al_report_base.report_pe_page`. XML UBL 2.0 (`Perception-1`) en
  `account.edi.xml.ubl_pe_perception`.
- `l10n_pe.perception.received` (+ líneas): percepciones que nos cobran
  (comprobante, factura o DUA) con su asiento.
- Resúmenes F.V. 697 y F.V. 621: vistas pivote por periodo.
- Datos de demostración: `tools/perception_demo_data.py`.

Pendiente: XML de la factura y del comprobante sin validar con un OSE real;
reparto de un cobro entre facturas con tasas distintas (se emite un
comprobante por tasa); arrastre del saldo no aplicado del F.V. 621.
