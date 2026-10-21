OL-ACCOUNTING
=============

**Contabilidad y tributación peruana.**

Para qué es esta carpeta
------------------------

Localización contable y tributaria de Perú sobre Odoo 19: la app **Perú**, plan de cuentas y destinos, numeración de asientos, medios de pago SUNAT, letras, tipo de cambio de compra y venta, detracciones (SPOT), retenciones de IGV, cierre y revaluación por diferencia de cambio, estados financieros, libros electrónicos (PLE) y registros SIRE.

Qué va aquí
-----------

- La app **Perú** (`al_account_base`) y lo que cuelga de ella: configuración contable, catálogos y menús fiscales.
- Obligaciones tributarias: detracciones, retenciones, PLE, SIRE y padrón SUNAT de contactos.
- Tipo de cambio, cierre de diferencia de cambio, revaluación multimoneda y reportes financieros.

Qué no va aquí
--------------

- Representación impresa y documentos electrónicos (factura, boleta, guía) → `OL-INVOICING/`.
- Planillas, aunque generen asientos contables → `OL-PAYROLL/`.
- Comprobantes emitidos desde el TPV → `OL-POS/`.

Módulos disponibles
-------------------

Tabla generada desde los manifiestos con `python3 scripts/gen_addons_table.py`
(no editar a mano).

[//]: # (addons)
módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_account_base](al_account_base/) | 17.20261013 | OPL-1 | Personalizaciones genéricas de la localización contable peruana: glosa en asientos/líneas, menú "Perú" y utilidades compartidas.
[al_account_destinations](al_account_destinations/) | 12.20261012 | OPL-1 | Genera automáticamente el asiento de destino (clase 6 a 9 o viceversa) según los porcentajes configurados por cuenta.
[al_account_move_name_sequence](al_account_move_name_sequence/) | 13.20261008 | OPL-1 | Secuencia ir.sequence OPCIONAL por diario para controlar la numeración (serie-correlativo SUNAT) de los comprobantes.
[al_account_payments](al_account_payments/) | 10.20261012 | OPL-1 | Medio de pago SUNAT (catálogo 1) y número de operación bancaria en pagos y en el asistente de registro de pagos.
[al_l10n_pe_account_letter](al_l10n_pe_account_letter/) | 21.20261018 | OPL-1 | Canje, refinanciación y gestión de letras de cambio para clientes y proveedores (Perú).
[al_l10n_pe_batch_payment](al_l10n_pe_batch_payment/) | 5.20261018 | OPL-1 | Lotes de pago a proveedores con el archivo TXT de BCP, BBVA, Interbank, Scotiabank y Banco de la Nación: cuenta o CCI del proveedor, controles y totales del archivo.
[al_l10n_pe_cash_fund](al_l10n_pe_cash_fund/) | 2.20261012 | OPL-1 | Entregas a rendir y cajas chicas a cargo de un responsable: aprobación, entrega, rendición con comprobantes y planilla de movilidad, devolución, reembolso o reposición, con sus asientos.
[al_l10n_pe_check](al_l10n_pe_check/) | 2.20261018 | OPL-1 | Cartera de cheques de terceros y cheques propios sobre el módulo nativo de Odoo: diarios y cuentas del PCGE, emisor con RUC o DNI y plazo de presentación de la Ley de Títulos Valores.
[al_l10n_pe_cpe_validation](al_l10n_pe_cpe_validation/) | 3.20261018 | OPL-1 | Consulta integrada de comprobantes de pago de SUNAT para las facturas de proveedor: de una en una, en lote o al publicar, con aviso o bloqueo.
[al_l10n_pe_currency](al_l10n_pe_currency/) | 14.20261012 | OPL-1 | Tipo de cambio SUNAT (compra/venta) para USD/PEN desde cuatro fuentes —SUNAT, BCRP, Decolecta y apis.net.pe—, con actualización diaria, registro manual coherente y visualización del T.C. aplicado en facturas en moneda extranjera.
[al_l10n_pe_detraction](al_l10n_pe_detraction/) | 25.20261018 | OPL-1 | Detracciones SUNAT (SPOT): catálogo 54 administrable con porcentajes y montos mínimos, cálculo automático en facturas, depósito/constancia y enlace con el PLE 8.1.
[al_l10n_pe_exchange_closure](al_l10n_pe_exchange_closure/) | 12.20261018 | OPL-1 | Ajuste mensual por diferencia de cambio de las partidas monetarias en moneda extranjera: T.C. compra para activos y T.C. venta para pasivos (art. 61 LIR / art. 34 Reglamento).
[al_l10n_pe_factoring](al_l10n_pe_factoring/) | 9.20261018 | OPL-1 | Cesión de facturas a un factor con y sin recurso: asientos de cesión, desembolso, devengo de intereses, cobro del factor y recompra, con cuentas del PCGE configurables.
[al_l10n_pe_financial_reports](al_l10n_pe_financial_reports/) | 3.20261012 | OPL-1 | Estados financieros peruanos sobre el motor de informes de Odoo: 3.19 Estado de Cambios en el Patrimonio Neto, junto al Balance y el Estado de resultados, en la app Perú.
[al_l10n_pe_fourth_category](al_l10n_pe_fourth_category/) | 4.20261018 | OPL-1 | Recibos por honorarios: retención del 8 % sobre el tope, suspensión (Formulario 1609), reporte y archivo .4ta para la PLAME y certificado anual.
[al_l10n_pe_import_dua](al_l10n_pe_import_dua/) | 4.20261018 | OPL-1 | La DUA (tipo 50) como documento de compra: IGV e IPM con crédito fiscal, derechos aduaneros, percepción aduanera y costos en destino del producto.
[al_l10n_pe_lease](al_l10n_pe_lease/) | 5.20261018 | OPL-1 | Contratos de alquiler como arrendatario según NIIF 16: pasivo a valor presente, derecho de uso con su depreciación, cuotas del arrendador, remedición, terminación anticipada, contratos en dólares e impuesto diferido.
[al_l10n_pe_monthly_tax](al_l10n_pe_monthly_tax/) | 3.20261012 | OPL-1 | Régimen tributario, pago a cuenta del impuesto a la renta y resumen del Formulario Virtual 621 con saldo a favor, percepciones y retenciones.
[al_l10n_pe_multicurrency_revaluation](al_l10n_pe_multicurrency_revaluation/) | 6.20261012 | OPL-1 | Revalúa cada cuenta con el tipo de cambio SUNAT de compra o de venta en el informe de ganancias/pérdidas de moneda no realizadas, y muestra el T.C. aplicado en cada línea.
[al_l10n_pe_perception](al_l10n_pe_perception/) | 4.20261018 | OPL-1 | Régimen de percepciones del IGV: comprobante de percepción electrónico (tipo 40) como agente, percepciones que nos cobran para el F.V. 621 y resumen del F.V. 697.
[al_l10n_pe_ple](al_l10n_pe_ple/) | 26.20261012 | OPL-1 | Completa los libros electrónicos PLE de SUNAT no cubiertos por la localización oficial: Libro 7 (Activos Fijos), 4.1 (Retenciones LIR), 9.1/9.2 (Consignaciones), complementos del Libro 3 (3.8/3.9/3.19/3.23), Libro 10 (Costos) y formatos simplificados (5.2/5.4, 8.3, 14.2). Corrige además el RCE 8.4 y 8.5 del SIRE.
[al_l10n_pe_retention](al_l10n_pe_retention/) | 24.20261018 | OPL-1 | Régimen de Retenciones del IGV (R.S. 037-2002/SUNAT): agente de retención, aplicabilidad con excepciones y retención del 3% en el pago sobre el marco nativo.
[al_l10n_pe_sire](al_l10n_pe_sire/) | 22.20261012 | OPL-1 | Conciliación con el Sistema Integrado de Registros Electrónicos de SUNAT
[al_l10n_pe_term_deposit](al_l10n_pe_term_deposit/) | 5.20261018 | OPL-1 | Depósitos a plazo, fondos en garantía y depósitos en garantía entregados: apertura, devengo mensual de intereses (TEA), vencimiento, cancelación, renovación y liberación con sus asientos.
[al_payment_culqi](al_payment_culqi/) | 2.20261018 | OPL-1 | Culqi como proveedor de pago de Odoo: tarjetas y Yape con Checkout Custom, autenticación 3DS y devoluciones totales o parciales.
[al_payment_izipay](al_payment_izipay/) | 2.20261018 | OPL-1 | Izipay como proveedor de pago de Odoo: formulario emergente de Izipay con tarjetas y cuotas, confirmación por IPN firmada, anulaciones y devoluciones.
[al_payment_niubiz](al_payment_niubiz/) | 3.20261018 | OPL-1 | Niubiz Checkout All-In-One como proveedor de pago: tarjetas, Yape, Plin, Cuotéalo BCP y PagoEfectivo, con anulación y devoluciones.
[l10n_pe_vat_sunat](l10n_pe_vat_sunat/) | 22.20261012 | OPL-1 | Consulta y actualización automática de datos de RUC y DNI desde el portal SUNAT, ApiPerú, Apis.net.pe y JSON-PE. Padrón de buenos contribuyentes y agentes de retención con caché diaria.
[//]: # (end addons)
