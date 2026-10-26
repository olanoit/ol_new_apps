# Finanzas

Lo que la suite agrega a la contabilidad y la facturación de Odoo para operar
en el Perú.

## Localización peruana

| Página | Qué cubre |
|---|---|
| [Perú](fiscal_localizations/peru.md) | Visión general, módulos y flujo de un mes |
| [Configuración contable básica](fiscal_localizations/peru/accounting_base.md) | Glosa, diarios, código SUNAT del banco, establecimiento anexo |
| [Consulta de RUC y DNI](fiscal_localizations/peru/ruc_dni_lookup.md) | Autocompletado de contactos y padrones de SUNAT |
| [Numeración de asientos y series](fiscal_localizations/peru/entry_numbering.md) | Series CPE y numeración sin huecos |
| [Medios de pago SUNAT](fiscal_localizations/peru/payment_methods.md) | Bancarización: medio de pago y número de operación |
| [Tipo de cambio](fiscal_localizations/peru/exchange_rates.md) | Compra y venta de SUNAT y BCRP en cada comprobante |
| [Diferencia de cambio](fiscal_localizations/peru/exchange_differences.md) | Cierre de tipo de cambio y ganancias o pérdidas no realizadas |
| [Asientos de destino](fiscal_localizations/peru/destination_entries.md) | Clase 6 al Elemento 9 y cuadre de la 79 |
| [Detracciones (SPOT)](fiscal_localizations/peru/detractions.md) | Cálculo, depósito y depósito masivo |
| [Retenciones del IGV](fiscal_localizations/peru/withholdings.md) | Retención al pagar, CRE (también sin pago), reversión, retenciones sufridas y PDT 626 |
| [Percepciones del IGV](fiscal_localizations/peru/perceptions.md) | Percepción como agente (comprobante tipo 40, F.V. 697) y percepciones que nos cobran |
| [Retención de renta de 4.ª categoría](fiscal_localizations/peru/fourth_category.md) | Recibos por honorarios, suspensiones (F. 1609), archivo .4ta de la PLAME y certificado |
| [Consulta de validez de comprobantes](fiscal_localizations/peru/cpe_validation.md) | Validez en SUNAT de los comprobantes de proveedores |
| [Declaración mensual IGV y renta (621)](fiscal_localizations/peru/monthly_tax.md) | Régimen tributario, pago a cuenta y resumen del F.V. 621 con sus saldos |
| [Facturación electrónica](fiscal_localizations/peru/electronic_invoicing.md) | Comprobante y guía impresos, anticipos y descuentos, liquidación de compra, OSE |
| [Libro de reclamaciones](fiscal_localizations/peru/complaints_book.md) | Hoja de reclamación en el sitio web |
| [Libros electrónicos (PLE)](fiscal_localizations/peru/ple.md) | Libros que Odoo no genera y formatos simplificados |
| [Registros SIRE](fiscal_localizations/peru/sire.md) | Conciliación del RVIE y el RCE con la propuesta de SUNAT |
| [Estados financieros](fiscal_localizations/peru/financial_statements.md) | Estado de cambios en el patrimonio neto |

## Contabilidad y facturación

| Página | Qué cubre |
|---|---|
| [Letras de cambio](accounting/bills_of_exchange.md) | Canje de facturas por letras, renovación y protesto |
| [Factoring](accounting/factoring.md) | Cesión de facturas a una entidad de factoring |
| [Depósitos a plazo y garantías](accounting/term_deposits.md) | Depósitos, intereses y garantías |
| [Arrendamientos (NIIF 16)](accounting/leases.md) | Derecho de uso y pasivo por arrendamiento |
| [Entregas a rendir y caja chica](accounting/cash_fund.md) | Entregas, rendición por facturas y movilidad, caja chica y reposición |
| [Pagos masivos a proveedores](accounting/batch_payments.md) | Archivo TXT de pago masivo para BCP, BBVA, Interbank, Scotiabank y Banco de la Nación |
| [Cheques recibidos y girados](accounting/checks.md) | Cartera de cheques de terceros, depósito, rechazo, cheques propios y plazo de presentación |
| [DUA de importación](accounting/import_dua.md) | DUA como compra: derechos, IGV, percepción aduanera y costos en destino |

## Tesorería

| Página | Qué cubre |
|---|---|
| [Tesorería](treasury.md) | Posición diaria, programación y aprobación de pagos, transferencias y cambio de moneda, líneas de crédito y bancarización |
| [Préstamos y pagarés bancarios](treasury/bank_loans.md) | Cronograma con TEA, desembolso, devengo, cuotas, prepagos y TCEA |
| [Cartas fianza](treasury/bank_guarantees.md) | Emitidas y recibidas: comisión, renovación, liberación, ejecución y avisos |

## Proveedores de pago

| Página | Qué cubre |
|---|---|
| [Culqi](payment_providers/culqi.md) | Pagos con tarjeta y Yape |
| [Izipay](payment_providers/izipay.md) | Pagos con tarjeta en el formulario de Izipay, con anulación y devoluciones |
| [Niubiz](payment_providers/niubiz.md) | Pagos con tarjeta |
| [PagoEfectivo](payment_providers/pagoefectivo.md) | Código de pago (CIP) para pagar en efectivo en agentes y bodegas o por banca |
