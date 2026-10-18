OL-INVOICING
============

**Facturación y documentos electrónicos.**

Para qué es esta carpeta
------------------------

Representaciones impresas y documentos electrónicos de venta y traslado: factura y boleta (formato SUNAT) y guía de remisión electrónica.

Qué va aquí
-----------

- Reportes PDF de comprobantes de pago y guías de remisión.
- Ajustes a la emisión de documentos electrónicos (CPE, GRE) que no sean del TPV.
- Controles de la orden de venta (aprobación antes de confirmar).

Qué no va aquí
--------------

- Registros y libros tributarios (PLE, SIRE, detracciones, retenciones) → `OL-ACCOUNTING/`.
- Boletas y facturas emitidas desde el TPV → `OL-POS/`.

Módulos disponibles
-------------------

Tabla generada desde los manifiestos con `python3 scripts/gen_addons_table.py`
(no editar a mano).

[//]: # (addons)
módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_l10n_pe_complaints_book](al_l10n_pe_complaints_book/) | 9.20261013 | OPL-1 | Libro de Reclamaciones físico y virtual conforme al Código del Consumidor y al D.S. 011-2011-PCM: hoja del Anexo I, constancia por correo, plazo de 15 días hábiles, respuesta, SIREC y multicompañía.
[al_l10n_pe_delivery_guide_report](al_l10n_pe_delivery_guide_report/) | 12.20261012 | OPL-1 | Representación impresa propia de la guía de remisión electrónica remitente (SUNAT) para stock.picking.
[al_l10n_pe_edi_downpayment_discount](al_l10n_pe_edi_downpayment_discount/) | 5.20261018 | OPL-1 | Corrige el XML UBL 2.1 de SUNAT con anticipos y descuentos globales: anticipos exonerados e inafectos, un anticipo por comprobante, descuentos de partes no gravadas y notas de crédito sin bloqueos.
[al_l10n_pe_edi_purchase_settlement](al_l10n_pe_edi_purchase_settlement/) | 4.20261018 | OPL-1 | Liquidación de compra electrónica (tipo 04) a personas naturales sin RUC: XML UBL 2.1 firmado y enviado, retención del IGV y del impuesto a la renta, PDF y reversión.
[al_l10n_pe_invoice](al_l10n_pe_invoice/) | 21.20261018 | OPL-1 | Presentación del comprobante electrónico: QR SUNAT, monto en letras, detalle tributario, detracción, cuotas de crédito, firmas y reportes propios A4 y ticket 80mm.
[al_ose_factory_hka](al_ose_factory_hka/) | 4.20261012 | OPL-1 | The Factory HKA como Operador de Servicios Electrónicos: facturas, boletas, notas, bajas, comprobantes de retención (CRE) y su reversión, con funciones que se activan en Ajustes.
[al_sale_approval](al_sale_approval/) | 2.20261013 | OPL-1 | Las ventas de productos marcados no se confirman sin una solicitud aprobada en Aprobaciones.
[al_website_sale_pe](al_website_sale_pe/) | 1.20261014 | OPL-1 | Checkout de la tienda en línea para Perú: el cliente elige boleta o factura, su RUC o DNI se consulta en SUNAT/RENIEC y llena el nombre y la dirección.
[//]: # (end addons)
