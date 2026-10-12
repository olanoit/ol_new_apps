# PE - Liquidación de compra electrónica (AL)

Documentación funcional: [Liquidación de compra](../../mkdocs/content/applications/finance/fiscal_localizations/peru/electronic_invoicing/purchase_settlement.md)

Módulo técnico `al_l10n_pe_edi_purchase_settlement`. El comprador emite la
liquidación de compra electrónica (tipo 04) a personas naturales sin RUC,
retiene el IGV y el impuesto a la renta, la firma y la envía con el operador
electrónico de la compañía y la revierte con el resumen diario de reversiones.
Implementado desde la norma y las guías de SUNAT (no desde código de terceros).

## Qué hace

| Requisito | Norma | Cómo se cumple |
|---|---|---|
| Emisor: el comprador, a vendedores sin RUC | RCP, art. 6, num. 1.3 | Diario de compras marcado `l10n_pe_lce_journal`; vendedor con DNI, CE, pasaporte o cédula (catálogo 06: 1, 4, 7, A) |
| Serie L### y correlativo desde 1 | Anexo 27 | `l10n_pe_lce_serie` (validada) y numeración automática `L L001-00000001` |
| Retención del IGV | Manual LCE; formulario 1662 | Impuesto `-18% IGV retenido LC` en las líneas gravadas |
| Retención de renta 1,5 % / 4 % oro; nada hasta S/ 700 | R.S. 234-2005 (arts. 5, 6, 9); R.S. 028-2013 | Impuestos `-1,5%`/`-4% Retención IR LC` (40175) según el valor de venta en soles |
| XML `SelfBilledInvoice` | Anexo 6, literal e) | `account.edi.xml.ubl_pe_lce` (lxml, orden del XSD OASIS UBL 2.1) |
| Envío el día de emisión o el siguiente | R.S. 097-2012, art. 12.1.b | Botón **Enviar a SUNAT** (o al confirmar); aviso fuera de plazo |
| Reversión en 7 días por errores del vendedor o del producto | Art. 29-F; anexo 17 | `VoidedDocuments` RR con tipo 04 por `sendSummary`/`getStatus` |
| Representación impresa | Anexo 27 | Reporte con `al_report_base.report_pe_page` |
| Límite de 75 UIT del vendedor | RCP, art. 6, num. 1.3; art. 29-H | Aviso con las liquidaciones propias del año |

## Envío

Se reutilizan los servicios de `l10n_pe_edi` por el nombre del operador
(`_l10n_pe_edi_sign_service_<operador>`, `_l10n_pe_edi_cancel_invoices_step_1/2_<operador>`):
IAP, SUNAT directo, Digiflow y The Factory HKA (`al_ose_factory_hka`) sin
dependencia. Con SUNAT directo la liquidación va al servicio de facturas
(anexo 6) y el resumen de reversiones al de retenciones y percepciones
(anexo 22). Sin probar contra SUNAT ni un OSE reales.

## Datos de demostración

`tools/purchase_settlement_demo_data.py` (odoo shell, idempotente, prefijo
DEMO LC).
