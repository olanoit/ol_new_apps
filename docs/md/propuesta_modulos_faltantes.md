# Propuesta de módulos faltantes

Comparación de los módulos v16 de `new-inveragro` (unos 150) con la suite
`ol_new_apps` (Odoo 19) y con lo que ya trae Odoo 19 oficial y Enterprise
(`l10n_pe`, `l10n_pe_edi`, `l10n_pe_reports`, `l10n_pe_edi_stock`,
`account_asset`, `account_batch_payment`, `account_bank_statement_import`…).
Análisis del 11/10/2026; no incluye `inveragro_pagos`, que se analiza aparte.

## 1. Inventario v16 por área

| Área | Módulos v16 | Situación en la suite / Odoo 19 |
|---|---|---|
| Contabilidad PE | `dv_l10n_pe_account_account`, `_detractions`, `_retentions`, `_move_entry_type`, `_move_origin`, `_move_non_domiciled`, `_move_dua`, `_tax_amounts`, `dv_account_target_move`, `dv_account_seat_number`, `dv_account_letter`, `dv_aduana_letter`, `dv_negotiable_invoices`, `inveragro_close_tc`, `inveragro_conta`, `dv_l10n_pe_res_company_tax_regime_type`, `dv_l10n_pe_periodic_parameters` | Cubierto casi todo: destinos, numeración, letras, detracciones, retenciones, cierre y revaluación de T.C., factoring (factura negociable con CAVALI). Falta: origen de NC/ND fuera de Odoo, régimen tributario de la compañía y pagos a cuenta, DUA más allá del enlace oficial |
| Libros y registros | `dv_l10n_pe_sunat_moves_*`, `_ple*`, `_sire*`, `_physical*`, `_reports`, `_financial_reports`, `accounting_pdf_reports`, `account_reports_new` | Cubierto y mejor (al_l10n_pe_ple, al_l10n_pe_sire, al_l10n_pe_financial_reports, kárdex) |
| Facturación electrónica | `l10n_pe_edi_pse_factura`, `l10n_pe_edi_pse_guia`, `dv_l10n_pe_edi_*`, `dv_account_edi_process_*`, `dv_l10n_pe_sunat_cpe_validation_txt`, `dv_l10n_pe_sunat_0621_document_retention_txt` | Emisión cubierta (l10n_pe_edi + Factory HKA + comprobante impreso + anticipos). Falta: liquidación de compra electrónica, validación de CPE de proveedores |
| Tesorería y bancos | `dv_l10n_pe_account_batch_payment_bcp`, `_batch_payment_spot`, `dv_l10n_pe_res_bank*`, `dv_l10n_pe_account_payment`, `dv_account_inbound_check`, `petty_cash`, `payment_projection`, `payment_conditions`, `om_recurring_payments`, `om_account_bank_statement_import` | Pagos masivos solo para planillas (BCP, BBVA, Interbank, Scotiabank) y detracciones (BN). Falta: pagos masivos a proveedores, extractos de bancos peruanos. Caja chica y rendiciones: tarea de `inveragro_pagos` |
| Contactos y consultas | `dv_l10n_pe_partner_base`, `dv_l10n_pe_sunat_connection_*`, `partner_vat_unique`, `type_contact_partner`, `rh_partner` | Cubierto (l10n_pe_vat_sunat con ficha RUC, padrones, tipo de cambio) |
| Inventario y logística | `dv_l10n_pe_edi_stock_*`, `inveragro_guia`, `inveragro_partial_transfer`, `inverago_warehouse_daily_report`, `dv_mrp_custom`, `dv_l10n_pe_product` | Cubierto (guías, traslados, kárdex); el reporte diario de almacén es propio del cliente |
| Compras y ventas | `purchase_discount`, `dv_pos_and_sale_discount_custom`, `dv_sale_order_invoices`, `inveragro_creditos`, `inveragro_aprobacion`, `multi_level_approval` | Descuento en compras ya es nativo en Odoo 19. Aprobaciones: base_tier_validation. Créditos de clientes con aprobación: hueco menor |
| Planillas | `dv_l10n_pe_hr_*`, `voucher_*`, `holiday_*`, `legal_benefits_rule`, `basic_rule`, `extra_hours`… | Cubierto y mejor (OL-PAYROLL) |
| POS | `dv_l10n_pe_edi_pos`, `dv_pos_*`, `inveragro_pos`, `dv_analytic_account` | Cubierto (OL-POS) |
| Utilidades | `om_*`, `auto_backup`, `custom_list_view`, `web_responsive`, `opsway-2many-clickable-tag`, `web_action_conditionable`, `report_xlsx`, `multi_branch_base`, `dv_res_company_branches`, `dvl_web_enterprise_unlimited` | No migrar (ver §4) |

## 2. Huecos

| Necesidad | v16 | Suite / Odoo 19 | Propuesta |
|---|---|---|---|
| Retención de 4.ª categoría: 8 % a recibos por honorarios de más de S/ 1 500, suspensión (F.V. 1609), declaración | No | Solo la cuenta 40172 del plan contable; el PLE/SIRE ya clasifican el tipo 02 | **al_l10n_pe_fourth_category** |
| Liquidación de compra electrónica (tipo 04): obligatoria en el SEE desde el 01/07/2018 | No | `l10n_pe_edi` solo emite documentos de venta | **al_l10n_pe_edi_purchase_settlement** |
| Pagos masivos a proveedores con TXT de bancos | Solo Telecrédito BCP | Formatos de banco solo en planillas; `account_batch_payment` sin formatos peruanos | **al_l10n_pe_batch_payment** |
| Percepciones del IGV: sufridas (aplicación en el 621) y como agente (comprobante de percepción, F.V. 697) | No | El EDI oficial solo marca el tipo de operación 2001; el padrón tiene la casilla «agente de percepción» | **al_l10n_pe_perception** |
| Validación de comprobantes de proveedores ante SUNAT | TXT del validador masivo | No | **al_l10n_pe_cpe_validation** |
| Extractos de bancos peruanos (Excel o TXT de BCP, BBVA, Interbank, Scotiabank, BN) | `om_account_bank_statement_import` genérico | Importación CSV/OFX/CAMT genérica | **al_l10n_pe_bank_statement_import** |
| Importaciones: DUA, IGV y percepción aduanera, costos en destino | Registro de DUA | `l10n_pe_reports` enlaza la factura con la DUA; `stock_landed_costs` | **al_l10n_pe_import_dua** |
| Pagos a cuenta del impuesto a la renta (coeficiente o 1,5 %; 1 % en el RMT hasta 300 UIT) y régimen tributario | Régimen de la compañía | No | **al_l10n_pe_income_tax_advance** |
| Origen de NC/ND emitidas sobre comprobantes que no están en Odoo | Sí | Pendiente conocido del PLE | Ampliar **al_l10n_pe_ple** o la base contable (pequeño) |
| Créditos de clientes con aprobación por niveles | `inveragro_creditos` | Límite de crédito nativo con aviso | Configuración + base_tier_validation; desarrollo solo si el cliente lo exige |
| DAOT | No | No | No desarrollar: quien lleva registros electrónicos (PLE/SIRE) solo presenta la constancia de no información |

## 3. Módulos sugeridos, por prioridad

| # | Módulo | Área | Alcance | Depende de | Esfuerzo | Valor |
|---|---|---|---|---|---|---|
| 1 | `al_l10n_pe_fourth_category` | OL-ACCOUNTING | Recibos por honorarios del proveedor (tipo 02): retención automática del 8 % cuando el recibo supera S/ 1 500 y la empresa es agente; suspensión (F.V. 1609) por proveedor con vigencia anual; neto a pagar en el pago; reporte mensual de retenciones de 4.ª para la PLAME (prestadores) y el 621 | `al_account_base`, `l10n_pe`, (opcional) `al_hr_pe` para la PLAME | 4-6 días | Alto: lo usa toda empresa que contrata independientes |
| 2 | `al_l10n_pe_batch_payment` | OL-ACCOUNTING | Pagos masivos a proveedores sobre `account.batch.payment`: TXT de Telecrédito BCP, BBVA net cash, Interbank, Scotiabank y BN, reutilizando los formatos ya probados de `al_hr_pe_reports`; cuentas por banco y CCI; descuento de retenciones y detracciones | `account_batch_payment`, `al_account_payments`, `al_hr_pe_reports` (o mover los formatos a un módulo común) | 5-7 días | Alto: tesorería semanal |
| 3 | `al_l10n_pe_edi_purchase_settlement` | OL-INVOICING | Liquidación de compra electrónica (04) desde la factura de proveedor: vendedor con DNI, XML UBL 2.1, envío al OSE o SUNAT, retención del IR y del IGV que corresponda, PDF con `al_report_base`, límite de 75 UIT por vendedor | `l10n_pe_edi`, `al_ose_factory_hka`, `al_report_base` | 7-10 días | Alto para agro, reciclaje y artesanía (caso Inveragro) |
| 4 | `al_l10n_pe_perception` | OL-ACCOUNTING | Percepciones sufridas: registro y aplicación en el 621 (como las retenciones sufridas). Como agente: cálculo del 1 % / 0,5 % / 2 %, comprobante de percepción electrónico y resumen para el F.V. 697 | `al_l10n_pe_retention`, `l10n_pe_edi` | 5-8 días | Medio: proveedores de combustible y bienes del apéndice 1 de la Ley 29173 |
| 5 | `al_l10n_pe_cpe_validation` | OL-ACCOUNTING | Consulta de validez de los comprobantes de compra en SUNAT (servicio web de validez del CPE) antes de registrarlos o en lote; estado en la factura y bloqueo opcional del crédito fiscal | `l10n_pe`, `l10n_pe_vat_sunat` | 3-5 días | Medio: evita usar comprobantes de baja o inexistentes |
| 6 | `al_l10n_pe_bank_statement_import` | OL-ACCOUNTING | Importación de extractos en el formato de cada banco peruano, con número de operación y RUC del tercero para la conciliación; ITF como gasto automático | `account_bank_statement_import` | 3-5 días | Medio: acelera la conciliación |
| 7 | `al_l10n_pe_import_dua` | OL-ACCOUNTING | DUA como documento de compra (tipo 50): IGV, percepción y derechos aduaneros, enlace con la factura comercial, costos en destino y su lugar en el registro de compras | `l10n_pe_reports`, `stock_landed_costs`, `al_l10n_pe_sire` | 4-6 días | Medio para importadores |
| 8 | `al_l10n_pe_income_tax_advance` | OL-ACCOUNTING | Régimen tributario de la compañía (General, MYPE, RER), pago a cuenta mensual (coeficiente o 1,5 %; 1 % en el RMT hasta 300 UIT), asiento y resumen para el 621 | `al_account_base` | 3-4 días | Medio: cierre mensual |

## 4. Lo que de v16 no conviene migrar

- `dvl_web_enterprise_unlimited`: elimina el límite de la suscripción Enterprise; no se migra.
- `om_account_accountant`, `om_account_asset`, `om_account_budget`, `om_fiscal_year`, `om_recurring_payments`, `om_account_daily_reports`, `om_account_followup`, `accounting_pdf_reports`, `account_reports_new`: copias comunitarias de lo que Odoo 19 Enterprise ya trae.
- `multi_branch_base`, `dv_res_company_branches`: Odoo 19 tiene sucursales nativas.
- `custom_list_view`, `web_responsive`, `opsway-2many-clickable-tag`, `web_action_conditionable`: la interfaz de Odoo 19 ya los cubre.
- `purchase_discount`, `dv_l10n_pe_account_payment_term_foreign_currency`, `dv_account_invoice_date_currency_rate`: nativos o corregidos en Odoo 19 y en `al_l10n_pe_currency`.
- `auto_backup`: el respaldo es de infraestructura, no de un módulo.
- `dv_l10n_pe_sunat_0621_document_retention_txt`: SUNAT declara con el formulario virtual 621 (ver el análisis de retenciones).
- Los `inveragro_*`: personalizaciones del cliente; se evalúan una por una (pagos en su propia tarea).

## Fuentes

- Retención de 4.ª categoría: [SUNAT, cálculo del pago a cuenta de 4.ª](https://orientacion.sunat.gob.pe/node/283).
- Liquidación de compra: [R.S. 317-2017/SUNAT](https://www.sunat.gob.pe/legislacion/superin/2017/317-2017.pdf), [SUNAT CPE, liquidación de compra](https://cpe.sunat.gob.pe/tipos_de_comprobantes/liquidacion_de_compra), [Informe 083-2018-SUNAT](https://www.sunat.gob.pe/legislacion/oficios/2018/informe-oficios/i083-2018-7T0000.pdf).
- Percepciones: [SUNAT, comprobante de percepción](https://orientacion.sunat.gob.pe/node/1185), [ayuda del F.V. 697](https://www.sunat.gob.pe/operacLinea/ayudas/Ayuda_FV_697_Agente_de_Percepcion.pdf), [sistema de percepciones (charla SUNAT 2024)](https://charlas.sunat.gob.pe/sites/default/files/2024-06/SISTEMA%20DE%20PERCEPCIONES%202024x.pdf).
- Validez de CPE: [SUNAT, servicios web disponibles](https://orientacion.sunat.gob.pe/node/811).
- Pagos a cuenta: [SUNAT, impuestos a pagar](https://orientacion.sunat.gob.pe/node/1114).
- DAOT: [R.S. 024-2002/SUNAT](https://www.sunat.gob.pe/legislacion/superin/2002/024.htm).
