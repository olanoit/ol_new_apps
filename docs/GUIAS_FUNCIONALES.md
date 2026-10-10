# Guías funcionales de la suite

Una guía por módulo para consultores funcionales: para qué sirve, la norma que lo respalda,
el proceso de inicio a fin con un ejemplo que cuadra y referencias oficiales verificadas.
Todas siguen [la plantilla común](validacion/PLANTILLA_GUIA_FUNCIONAL.md); los enlaces se
verifican con `python3 docs/validacion/verificar_enlaces.py OL-*/*/GUIA_FUNCIONAL.md`.
Guías: 47 (todas las áreas OL-*; `ol_licencia_perpetua` no tiene guía funcional).


## Contabilidad

| Guía | Módulo | Versión |
|---|---|---|
| [PE - Base Contabilidad (AL)](../OL-ACCOUNTING/al_account_base/GUIA_FUNCIONAL.md) | `al_account_base` | 9.20261009 |
| [PE - Cuentas Destino (dinámica 6↔9)](../OL-ACCOUNTING/al_account_destinations/GUIA_FUNCIONAL.md) | `al_account_destinations` | 11.20261009 |
| [Numeración de asientos por secuencia (AL)](../OL-ACCOUNTING/al_account_move_name_sequence/GUIA_FUNCIONAL.md) | `al_account_move_name_sequence` | 13.20261008 |
| [PE - Medios de Pago (AL)](../OL-ACCOUNTING/al_account_payments/GUIA_FUNCIONAL.md) | `al_account_payments` | 7.20261008 |
| [PE - Letras de cambio y canje (AL)](../OL-ACCOUNTING/al_l10n_pe_account_letter/GUIA_FUNCIONAL.md) | `al_l10n_pe_account_letter` | 18.20261009 |
| [Tipo de cambio Perú (SUNAT)](../OL-ACCOUNTING/al_l10n_pe_currency/GUIA_FUNCIONAL.md) | `al_l10n_pe_currency` | 13.20261008 |
| [PE - Detracciones SPOT (AL)](../OL-ACCOUNTING/al_l10n_pe_detraction/GUIA_FUNCIONAL.md) | `al_l10n_pe_detraction` | 21.20261008 |
| [PE - Cierre de tipo de cambio (AL)](../OL-ACCOUNTING/al_l10n_pe_exchange_closure/GUIA_FUNCIONAL.md) | `al_l10n_pe_exchange_closure` | 9.20261008 |
| [PE - Factoring de facturas (AL)](../OL-ACCOUNTING/al_l10n_pe_factoring/GUIA_FUNCIONAL.md) | `al_l10n_pe_factoring` | 4.20261010 |
| [PE - Reportes financieros (AL)](../OL-ACCOUNTING/al_l10n_pe_financial_reports/GUIA_FUNCIONAL.md) | `al_l10n_pe_financial_reports` | 2.20261008 |
| [PE - Arrendamientos NIIF 16 (AL)](../OL-ACCOUNTING/al_l10n_pe_lease/GUIA_FUNCIONAL.md) | `al_l10n_pe_lease` | 2.20261010 |
| [PE - T.C. compra/venta en ganancias y pérdidas no realizadas](../OL-ACCOUNTING/al_l10n_pe_multicurrency_revaluation/GUIA_FUNCIONAL.md) | `al_l10n_pe_multicurrency_revaluation` | 5.20261009 |
| [PE - Libros Electrónicos PLE (AL)](../OL-ACCOUNTING/al_l10n_pe_ple/GUIA_FUNCIONAL.md) | `al_l10n_pe_ple` | 23.20261009 |
| [PE - Retenciones de IGV (AL)](../OL-ACCOUNTING/al_l10n_pe_retention/GUIA_FUNCIONAL.md) | `al_l10n_pe_retention` | 18.20261009 |
| [Perú - SIRE (RVIE / RCE)](../OL-ACCOUNTING/al_l10n_pe_sire/GUIA_FUNCIONAL.md) | `al_l10n_pe_sire` | 18.20261009 |
| [PE - Depósitos a plazo y garantías (AL)](../OL-ACCOUNTING/al_l10n_pe_term_deposit/GUIA_FUNCIONAL.md) | `al_l10n_pe_term_deposit` | 2.20261010 |
| [Pagos con Culqi (AL)](../OL-ACCOUNTING/al_payment_culqi/GUIA_FUNCIONAL.md) | `al_payment_culqi` | 1.20261006 |
| [Pagos con Niubiz (AL)](../OL-ACCOUNTING/al_payment_niubiz/GUIA_FUNCIONAL.md) | `al_payment_niubiz` | 2.20261009 |
| [Búsqueda RUC/DNI desde SUNAT](../OL-ACCOUNTING/l10n_pe_vat_sunat/GUIA_FUNCIONAL.md) | `l10n_pe_vat_sunat` | 17.20261009 |

## Facturación

| Guía | Módulo | Versión |
|---|---|---|
| [Perú - Libro de Reclamaciones](../OL-INVOICING/al_l10n_pe_complaints_book/GUIA_FUNCIONAL.md) | `al_l10n_pe_complaints_book` | 7.20261009 |
| [PE - Reporte de Guía de Remisión Electrónica (AL)](../OL-INVOICING/al_l10n_pe_delivery_guide_report/GUIA_FUNCIONAL.md) | `al_l10n_pe_delivery_guide_report` | 11.20261008 |
| [PE - Anticipos y descuentos globales en el CPE (AL)](../OL-INVOICING/al_l10n_pe_edi_downpayment_discount/GUIA_FUNCIONAL.md) | `al_l10n_pe_edi_downpayment_discount` | 3.20261008 |
| [PE - Comprobantes Electrónicos (AL)](../OL-INVOICING/al_l10n_pe_invoice/GUIA_FUNCIONAL.md) | `al_l10n_pe_invoice` | 18.20261008 |
| [PE - OSE The Factory HKA (AL)](../OL-INVOICING/al_ose_factory_hka/GUIA_FUNCIONAL.md) | `al_ose_factory_hka` | 2.20261010 |

## Planillas

| Guía | Módulo | Versión |
|---|---|---|
| [Planillas Perú - Núcleo (AL)](../OL-PAYROLL/al_hr_pe/GUIA_FUNCIONAL.md) | `al_hr_pe` | 34.20261010 |
| [Planillas Perú - Contabilización (AL)](../OL-PAYROLL/al_hr_pe_account/GUIA_FUNCIONAL.md) | `al_hr_pe_account` | 11.20261010 |
| [Planillas Perú - Asistencia y turnos (AL)](../OL-PAYROLL/al_hr_pe_attendance/GUIA_FUNCIONAL.md) | `al_hr_pe_attendance` | 19.20261010 |
| [Planillas Perú - Beneficios sociales (AL)](../OL-PAYROLL/al_hr_pe_benefits/GUIA_FUNCIONAL.md) | `al_hr_pe_benefits` | 22.20261008 |
| [Planillas Perú - Construcción civil (AL)](../OL-PAYROLL/al_hr_pe_construction/GUIA_FUNCIONAL.md) | `al_hr_pe_construction` | 22.20261010 |
| [Planillas Perú - Importadores Excel (AL)](../OL-PAYROLL/al_hr_pe_import/GUIA_FUNCIONAL.md) | `al_hr_pe_import` | 9.20261008 |
| [Planillas Perú - Feriados (AL)](../OL-PAYROLL/al_hr_pe_public_holidays/GUIA_FUNCIONAL.md) | `al_hr_pe_public_holidays` | 10.20261008 |
| [Planillas Perú - Documentos y bancos (AL)](../OL-PAYROLL/al_hr_pe_reports/GUIA_FUNCIONAL.md) | `al_hr_pe_reports` | 21.20261009 |

## Punto de venta

| Guía | Módulo | Versión |
|---|---|---|
| [PE - Comprobantes Electrónicos en el TPV (AL)](../OL-POS/al_l10n_pe_edi_pos/GUIA_FUNCIONAL.md) | `al_l10n_pe_edi_pos` | 12.20261008 |
| [TPV - Impresora de red ESC/POS (AL)](../OL-POS/al_pos_network_printer/GUIA_FUNCIONAL.md) | `al_pos_network_printer` | 4.20261009 |
| [TPV - Catálogo de productos: filtro por etiquetas y vista lista (AL)](../OL-POS/al_pos_product_view/GUIA_FUNCIONAL.md) | `al_pos_product_view` | 6.20261009 |
| [TPV - Tema y marca blanca (AL)](../OL-POS/al_pos_theme/GUIA_FUNCIONAL.md) | `al_pos_theme` | 2.20261008 |
| [TPV - Vendedor por orden (AL)](../OL-POS/al_pos_vendedor/GUIA_FUNCIONAL.md) | `al_pos_vendedor` | 3.20261008 |

## Inventario

| Guía | Módulo | Versión |
|---|---|---|
| [PE - Traslados internos y bienes de terceros (AL)](../OL-INVENTORY/al_l10n_pe_stock_transfer/GUIA_FUNCIONAL.md) | `al_l10n_pe_stock_transfer` | 2.20261010 |
| [PE - Base Inventario (AL)](../OL-INVENTORY/al_stock_base/GUIA_FUNCIONAL.md) | `al_stock_base` | 1.20261008 |
| [PE - Kardex SUNAT (Formato 13.1 / 12.1)](../OL-INVENTORY/ol_stock_kardex_pe/GUIA_FUNCIONAL.md) | `ol_stock_kardex_pe` | 12.20261009 |

## Proyectos

| Guía | Módulo | Versión |
|---|---|---|
| [Requerimiento de materiales de obra (AL)](../OL-PROJECTS/al_construction_material_request/GUIA_FUNCIONAL.md) | `al_construction_material_request` | 9.20261009 |
| [Gantt de Proyectos — Asistente IA (AL)](../OL-PROJECTS/al_project_gantt_ai/GUIA_FUNCIONAL.md) | `al_project_gantt_ai` | 5.20261008 |
| [Gantt de Proyectos — Backend (AL)](../OL-PROJECTS/al_project_gantt_backend/GUIA_FUNCIONAL.md) | `al_project_gantt_backend` | 14.20261009 |
| [Gantt de Proyectos — Base (AL)](../OL-PROJECTS/al_project_gantt_base/GUIA_FUNCIONAL.md) | `al_project_gantt_base` | 16.20261008 |
| [Gantt de Proyectos — Website (AL)](../OL-PROJECTS/al_project_gantt_website/GUIA_FUNCIONAL.md) | `al_project_gantt_website` | 12.20261008 |

## Herramientas

| Guía | Módulo | Versión |
|---|---|---|
| [Aplicaciones - Ficha completa del módulo (AL)](../OL-TOOLS/al_base_module_info/GUIA_FUNCIONAL.md) | `al_base_module_info` | 2.20261008 |
| [Servidor MCP para Odoo (AL)](../OL-TOOLS/al_mcp_server/GUIA_FUNCIONAL.md) | `al_mcp_server` | 8.20261009 |
