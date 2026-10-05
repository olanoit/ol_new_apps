invoicing
=========

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

- Registros y libros tributarios (PLE, SIRE, detracciones, retenciones) → `accounting/`.
- Boletas y facturas emitidas desde el TPV → `pos/`.

Módulos disponibles
-------------------

Tabla generada desde los manifiestos con `python3 scripts/gen_addons_table.py`
(no editar a mano).

[//]: # (addons)
módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_l10n_pe_delivery_guide_report](al_l10n_pe_delivery_guide_report/) | 7.20260828 | OPL-1 | Representación impresa propia de la guía de remisión electrónica remitente (SUNAT) para stock.picking.
[al_l10n_pe_invoice](al_l10n_pe_invoice/) | 11.20260828 | OPL-1 | Presentación del comprobante electrónico: QR SUNAT, monto en letras, detalle tributario, detracción, cuotas de crédito, firmas y reportes propios A4 y ticket 80mm.
[//]: # (end addons)
