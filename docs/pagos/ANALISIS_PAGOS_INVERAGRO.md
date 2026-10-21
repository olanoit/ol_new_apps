# Pagos: análisis de las personalizaciones de Inveragro (v16) y procesos por desarrollar

Fecha: 21/10/2026. Proyecto revisado: `/home/och/odoo/ce16/new/inveragro/dv_proyecto_peru_agricola`
(`inveragro_pagos`, ~7 800 líneas, y 24 módulos más que tocan pagos o tesorería).
Comparado con la suite `ol_new_apps` (Odoo 19) y con lo nativo de Odoo 19 CE/EE.

Lo de Inveragro se usa como **referencia de procesos**, no como código a portar: tiene un
motor de pago propio que apaga la sincronización pago↔asiento de Odoo, numeración por `ilike`,
SQL crudo, cuentas y diarios fijos por código o nombre, y piezas rotas (sección 5).

## 1. Resumen

| Proceso | Inveragro v16 | Odoo 19 nativo | Nuestra suite | Veredicto |
|---|---|---|---|---|
| Medio de pago SUNAT (tabla 1) y nº de operación | `dv_l10n_pe_account_payment`, `number_operation_bank` | — | `al_account_payments` | **Cubierto** |
| Tipo de cambio compra/venta en el pago | TC manual en el pago | Diferencia de cambio automática | `al_l10n_pe_currency` | **Cubierto** (falta TC pactado, ver P8) |
| Retención IGV + CRE electrónico | Desde el pago y manual (CRE como `out_invoice` 20) | Marco de retención en pagos | `al_l10n_pe_retention` (CRE firmado, mínimo 700, NC deducidas) | **Cubierto** |
| TXT 0621 de retenciones | `dv_l10n_pe_sunat_0621_document_retention_txt` | — | `al_l10n_pe_monthly_tax` / retención | Verificar el TXT exacto |
| Detracciones: pago, constancias, TXT masivo | `modo_pago=detraccion`, TXT SPOT (parcialmente roto) | Bloque SPOT en XML | `al_l10n_pe_detraction` (depósito, TXT, importación de constancias) | **Cubierto** |
| Percepciones | — | — | `al_l10n_pe_perception` | Cubierto (más que Inveragro) |
| Pagos masivos a bancos | TXT Telecrédito BCP | Lotes (EE) sin formatos PE | `al_l10n_pe_batch_payment` (BCP, BBVA, Interbank, Scotiabank, BN) | **Cubierto** |
| Cheques recibidos y emitidos | `dv_account_inbound_check` | `l10n_latam_check` | `al_l10n_pe_check` | **Cubierto** (falta impresión, P10) |
| Letras de cambio | `dv_account_letter` (5 600 líneas) | — | `al_l10n_pe_account_letter` | **Cubierto** |
| Facturas negociables | `dv_negotiable_invoices` | — | `al_l10n_pe_factoring` (con CAVALI) | **Cubierto** |
| Caja chica / entregas a rendir / movilidad | `account.petty.cash`, `account.renders.payroll` | — | `al_l10n_pe_cash_fund` | **Cubierto** (falta arqueo, P4) |
| Transferencia entre cuentas con TC bancario | `transfer` + TC bancario | Transferencias internas | `al_account_payments` (compraventa de moneda) | **Cubierto** (falta ITF, P6) |
| Bancos: código SUNAT, tipo de cuenta, CCI | `dv_l10n_pe_res_bank*` | — | `al_l10n_pe_batch_payment` | Cubierto |
| Recibo de caja / comprobante de pago impreso | Muerto (no cargado) | Recibo genérico | `al_l10n_pe_payment_receipt` | **Cubierto** (P1) |
| Pago de varias facturas de **varios socios** en un pago | Núcleo del motor (`pago_multiproveedor`) | Agrupado solo por socio; lotes (EE) | `al_l10n_pe_payment_multi` | **Cubierto** (P2) |
| Anticipos de cliente/proveedor (122/422) y su aplicación | `account.payment.anticipos`, `is_anticipo`, `inveragro_aplicacion` | Anticipo de pedido; saldo a favor sin cuenta propia | `al_l10n_pe_payment_application` | **Cubierto** (P3) |
| Cruce / compensación de documentos | `application.document` (APD/AJD) | Conciliación manual | `al_l10n_pe_payment_application` | **Cubierto** (P3) |
| Cierre de caja diario por sucursal y método de pago | `close.sale.report` | Solo POS | — | **Brecha P4** |
| Proyección de cobranza / flujo de caja | `payment_projection` (3 900 líneas) | Flujo de efectivo histórico (EE) | — | **Brecha P5** |
| Plazos de pago: monto fijo en soles con factura en USD | `dv_..._payment_term_foreign_currency` | Plazos rediseñados en 17+ | — | **Brecha P7** (verificar si hace falta) |
| Bloqueo de pagos de letras ya bancarizadas | `inveragro_letter_validation` | — | Verificar en letras/factoring | P9 |
| Pagos recurrentes | `om_recurring_payments` | — | — | Baja prioridad |
| Importación de extractos | `om_account_bank_statement_import` | CSV/OFX/CAMT (EE) | — | Formatos de bancos PE: P11 |
| Ticket 80 mm de factura | `invoice_ticket.xml` | — | `al_l10n_pe_invoice` (ticket) | Cubierto |
| Metas de venta, cierre por sectorista, venta gratuita en pedido | Varios | — | — | Específico del cliente: no se desarrolla |

## 2. Procesos por desarrollar (propuesta)

Ordenados por valor para cualquier empresa peruana y por lo que pide el usuario (comprobantes,
anticipos, otros pagos, pagos múltiples, métodos de pago).

### P1. Comprobante de pago: recibo de ingreso y de egreso numerado — prioridad alta, esfuerzo bajo

- Serie propia por diario y tipo (RI-001 cobros, RE-001 pagos) con `ir.sequence`, no por `ilike`.
- PDF A4/medio A4 con el formato común (`al_report_base`): socio con RUC/DNI, medio de pago SUNAT,
  nº de operación, banco/cheque, monto en letras (`currency.amount_to_text`), detalle de
  comprobantes pagados (de la conciliación), retención/detracción si hay, firmas «Entregué / Recibí».
- Envío por correo y reimpresión. Base: `account.report_payment_receipt` nativo.
- Inveragro no lo tiene operativo (su `payment_report.xml` está fuera del manifiesto).

### P2. Pago múltiple: varios documentos y varios socios en un solo pago — prioridad alta, esfuerzo alto

> **Hecho (21/10/2026)** en `al_l10n_pe_payment_multi`: un solo `account.payment` con el hook
> nativo `line_ids` (no un asiento suelto ni un pago por socio). Retención y detracción quedan
> fuera a propósito: el CRE es por proveedor y la detracción va al Banco de la Nación.

Caso: un egreso bancario que paga facturas de varios proveedores, una planilla de movilidad y un
gasto sin comprobante; o un depósito de cliente que cubre facturas de varios socios del grupo.

- Documento `l10n_pe.payment.multi` («Pago múltiple») con líneas de tipo: comprobante (apunte
  abierto a cobrar/pagar de cualquier socio), anticipo, otro pago (cuenta libre + analítica) y
  diferencia de cambio/redondeo.
- Al validar genera **un `account.payment` por socio** (o un asiento único con liquidez en una
  línea, a decidir) y concilia con el ORM estándar; nada de reescribir `_synchronize_*`.
- Montos parciales por línea, en la moneda del documento o del pago, con el TC compra/venta de
  `al_l10n_pe_currency` y diferencia de cambio nativa.
- Integra retención (P2 llama a `al_l10n_pe_retention`), detracción y nº de operación.
- Imprime el comprobante de P1.
- Alternativa más simple: extender `account.payment.register` para permitir varios socios en un
  lote (`account_batch_payment`) — cubre proveedores, no «otros pagos».

### P3. Anticipos de clientes y proveedores, y aplicación/compensación — prioridad alta, esfuerzo medio

- Pago marcado **anticipo**: lleva a la 122 (clientes) o 422 (proveedores) por método de pago o
  cuenta configurable por moneda (Inveragro usa cuentas PEN/USD).
- **Aplicación del anticipo** a la factura: asistente desde la factura o el anticipo que
  reclasifica 122→121 / 422→421 y concilia; aplicación parcial; control de anticipos pendientes
  por socio (lista/reporte con antigüedad).
- **Cruce de documentos** (APD/AJD de Inveragro): compensar cobrar vs. pagar del mismo socio, o
  NC contra facturas de otro documento, con asiento en un diario de aplicaciones y saldo cero.
- Relación con lo existente: el anticipo de **venta** con comprobante (factura de anticipo) ya lo
  cubre Odoo + `al_l10n_pe_edi_downpayment_discount`; este proceso es el anticipo **financiero**
  sin comprobante (y el de proveedor, que SUNAT no exige facturar si no hay entrega).

### P4. Cierre de caja diario y arqueo — prioridad media, esfuerzo medio

- Por diario de caja / sucursal y fecha: cobros y pagos del día por **método de pago**, ventas al
  contado vs. crédito, depósitos en tránsito, saldo inicial y final.
- **Arqueo**: conteo por denominación, faltante/sobrante con asiento.
- Estados abierto → en cierre → cerrado (reapertura solo responsable) y PDF.
- Inveragro clasifica por **nombre** del diario («EFECTIVO»); aquí, por tipo de diario y método.

### P5. Proyección de cobranzas y pagos (flujo de caja proyectado) — prioridad media, esfuerzo medio

- Por semanas/meses: cuentas por cobrar y por pagar por vencimiento, letras en cartera y en banco,
  cheques diferidos, depósitos a plazo que vencen, detracciones por liberar; saldo de bancos.
- Escenario editable (fecha estimada de cobro por documento) y comparación proyectado vs. real.
- XLSX y vista pivote. Inveragro solo proyecta cobranza por sucursal.

### P6. ITF automático — prioridad media, esfuerzo bajo

- 0,005 % (Ley 28194) en pagos, cobros y transferencias de diarios bancarios marcados; línea al
  gasto 6411x/ITF; exoneraciones (cuentas propias de igual titular, montos). Hoy solo existe en
  depósitos a plazo y como marca del TXT BCP.

### P7. Plazos de pago con cuota fija en soles para facturas en dólares — prioridad baja

- Revisar si el rediseño de plazos de Odoo 17+ y la cuota de detracción de `al_l10n_pe_detraction`
  ya lo resuelven; si no, extender `account.payment.term`.

### P8. Tipo de cambio pactado por pago — prioridad baja, esfuerzo bajo

- TC manual en el pago (operación de cambio con el banco o el cliente) en lugar del SUNAT
  compra/venta, con la diferencia a 776/676.

### P9. Bloqueo de pagos de documentos bancarizados — prioridad baja

- Impedir registrar un pago directo a una letra o factura negociable que ya está en el banco
  (cobranza libre/descuento): debe cancelarse con el abono del banco. Verificar si letras y
  factoring ya lo impiden.

### P10–P11. Impresión de cheques con formato de banco peruano; TXT de recaudación y extractos de bancos peruanos — prioridad baja

## 3. Recomendación de orden

1. **P1 Comprobante de pago** (rápido, visible, lo usan todos).
2. **P3 Anticipos y aplicación/cruce** (pedido frecuente; el contador lo necesita para la 122/422).
3. **P2 Pago múltiple** (el más complejo; aprovecha P1 y P3).
4. **P6 ITF** y **P4 Cierre de caja**.
5. **P5 Proyección**.

Módulos sugeridos (OL-ACCOUNTING): `al_l10n_pe_payment_receipt` (P1), `al_l10n_pe_payment_advance`
(P3), `al_l10n_pe_payment_multi` (P2), `al_l10n_pe_itf` (P6), `al_l10n_pe_cash_closing` (P4),
`al_l10n_pe_cash_forecast` (P5). P1 y P6 podrían ir en `al_account_payments`.

## 4. Lo que **no** se trae de Inveragro

- El motor de pago que reemplaza la contabilidad de `account.payment` (frágil y contra el ORM).
- Contactos genéricos «Multiproveedor» (RUC 99999999) y «Multi-Trabajador».
- Cierre de ventas por sectorista, metas de venta, zonas, líneas de producto, venta gratuita en
  pedido, importación de facturas de proveedor desde Excel (lo cubre la importación nativa).
- Efectos colaterales globales: listas sin filas vacías, A4 apaisado por defecto, cambios a datos
  de `l10n_latam_base`, conciliación entre cuentas distintas.

## 5. Calidad del código de referencia (por qué no se porta)

- `_prepare_move_line_default_vals` devuelve `{}`, `_synchronize_to_moves` vacío,
  `_synchronize_from_moves` traga excepciones, `_check_amount` desactivado
  (`inveragro_pagos/models/account_payment.py:196-201, 385-387, 522-553`).
- Numeración de pagos y anticipos buscando el último nombre con `ilike` (duplicados en concurrencia).
- Conciliación dentro de `try/except: pass`; contactos creados dentro de onchanges.
- Rotos: recibo de pago (no cargado), importador de constancias de detracción, Excel de planillas
  de movilidad, TXT SPOT (`user_type_id`, `tax_totals_json` de v15), cheques (`type_operation`
  inexistente), `relativedelta` sin importar en plazos.
- Cuentas y diarios por código o nombre (`401141`, `121201`, `LIQC`, «EFECTIVO», `company_id.id == 1`).
