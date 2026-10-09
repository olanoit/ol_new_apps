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
[al_l10n_pe_complaints_book](al_l10n_pe_complaints_book/) | 7.20261009 | OPL-1 | Libro de Reclamaciones físico y virtual conforme al Código del Consumidor y al D.S. 011-2011-PCM: hoja del Anexo I, constancia por correo, plazo de 15 días hábiles, respuesta, SIREC y multicompañía.
[al_l10n_pe_delivery_guide_report](al_l10n_pe_delivery_guide_report/) | 11.20261008 | OPL-1 | Representación impresa propia de la guía de remisión electrónica remitente (SUNAT) para stock.picking.
[al_l10n_pe_edi_downpayment_discount](al_l10n_pe_edi_downpayment_discount/) | 3.20261008 | OPL-1 | Corrige el XML UBL 2.1 de SUNAT con anticipos y descuentos globales: anticipos exonerados e inafectos, un anticipo por comprobante, descuentos de partes no gravadas y notas de crédito sin bloqueos.
[al_l10n_pe_invoice](al_l10n_pe_invoice/) | 18.20261008 | OPL-1 | Presentación del comprobante electrónico: QR SUNAT, monto en letras, detalle tributario, detracción, cuotas de crédito, firmas y reportes propios A4 y ticket 80mm.
[//]: # (end addons)
