# Análisis y plan de unificación — `tecport/l10n_pe` (Odoo 18) → localización peruana Odoo 19

- **Origen analizado:** `/home/och/odoo/ce18/mblz/tecport/l10n_pe` — 60 módulos, ~21 400 LOC Python, ~7 400 LOC XML.
- **Destino:** `/home/och/odoo/ce19/myodoo/ol_new_apps` — suite `al_*` sobre Odoo 19 Enterprise.
- **Fecha de análisis:** 15/08/2026.
- **Autoría del código origen:** IT SERVICE S.A.C. (58 módulos, licencia *Other proprietary*), Mobilize Spa. (1 módulo, OPL-1), 1 módulo LGPL-3.
- **Régimen de trabajo:** ⚖️ **clean-room** — el proyecto origen es mapa de requisitos, no fuente de código. Ver [FASE0_ACTA_LICENCIAS.md](FASE0_ACTA_LICENCIAS.md).

---

## 1. Resumen ejecutivo

`tecport/l10n_pe` es la localización peruana más amplia de las bases de código disponibles. Cubre procesos que **hoy no existen** en la suite `al_*` ni en Enterprise 19: los formatos del régimen SIRE (**RCE 8.4/8.5 y RVIE 14.4**), los **libros en PDF físico**, un **proveedor OSE genérico** para factura electrónica, y un **framework de proveedores de tipo de cambio** con tres integraciones reales (BCRP, Decolecta, ApisPeru).

Sus debilidades son igual de claras: granularidad excesiva (60 módulos para lo que la suite `al_*` resuelve con 15), acoplamiento a internals de Odoo 18 (SQL crudo con alias del ORM, framework UBL antiguo), cobertura de pruebas prácticamente nula (6 archivos de test en 60 módulos) y licenciamiento propietario de terceros.

**Recomendación:** no migrar el proyecto tal cual. Migrar **capacidades, no módulos**, dentro de la arquitectura `al_*` ya existente.

| Decisión | Módulos | LOC Py aprox. |
|---|---:|---:|
| **Absorber** — capacidad que no existe en v19 ni en `al_*` | 24 | ~10 700 |
| **Reconstruir sobre Enterprise** — el libro ya lo genera EE; solo se aprovecha el PDF/XLSX y los criterios SUNAT | 13 | ~6 150 |
| **Fusionar** — campos o ideas sueltas dentro de módulos `al_*` existentes | 11 | ~3 100 |
| **Descartar** — redundante o resuelto por el core de v19 | 12 | ~1 460 |

Los 24 módulos a absorber no se traducen en 24 módulos destino: colapsan en **8 módulos `al_*`** (5 ampliados, 3 nuevos), porque buena parte de la granularidad del origen es empaquetado, no funcionalidad.

Esfuerzo estimado: **9 fases, ~26–33 días de desarrollo**, con la Fase 3 (libros electrónicos) concentrando el 35 % del trabajo.

---

## 2. Inventario funcional del proyecto origen

Los 60 módulos se agrupan en seis familias:

### 2.1 Base transversal (7 módulos, ~600 LOC)
`base_country_filter`, `contact_bank_code`, `contact_identification_validation`, `l10n_pe_annex_establishment`, `l10n_pe_bank_code`, `l10n_pe_localization_menu`, `l10n_pe_journal_type`.

Aportan: filtro de visibilidad de campos por país de la compañía (`_tags_invisible_per_country`), código de banco SUNAT en cuentas bancarias, validación estructural de RUC/DNI parametrizada en `l10n_latam.identification.type` (`vat_length`, `vat_structure`), código de establecimiento anexo en el contacto, y marca de diario (movimiento/apertura/cierre).

### 2.2 Facturación y formatos (12 módulos, ~2 300 LOC Py + 1 300 XML)
`invoice_format_base`, `invoice_report_format`, `l10n_pe_format_base`, `l10n_pe_report_format`, `l10n_pe_edi_format_base`, `l10n_pe_edi_report_format`, `invoice_serie_correlative`, `invoice_origin_document`, `invoice_other_document_type` (+ variante `l10n_pe_*`), `invoice_override_functions`, `invoice_fix_sequence`, `l10n_pe_invoice_price_unit_reference`.

Lo relevante:
- **`invoice_serie_correlative`** es la pieza más interesante: propaga tipo de documento + serie + correlativo **a nivel de apunte contable** (`account.move.line.serie_correlative`), con índice SQL propio (`init()`) y un cron de reparación por lotes (`cron_update_invoice_fields_smart`). Es la base sobre la que se construyen todos los libros.
- **`invoice_report_format`**: formato de factura PDF de 938 líneas XML con 9 interruptores de configuración por compañía (logo, cuotas, anticipos, pagos, cuentas bancarias, términos…).
- **`l10n_pe_invoice_price_unit_reference`**: precio unitario referencial para operaciones gratuitas, tocando el motor de impuestos (`_prepare_product_base_line_for_taxes_computation`).

### 2.3 Tipo de cambio (8 módulos, ~2 300 LOC)
`invoice_break_currency_rate`, `invoice_currency_rate_update`, `invoice_exchange_rate`, `invoice_exchange_rate_type`, `invoice_force_exchange_rate`, `invoice_purchase_exchange_rate`, `l10n_pe_rate_update_{bcrp,decolecta,api_peru_dev}`, `mblz_l10n_pe_multicurrency_revaluation`.

Es el bloque mejor diseñado del proyecto:
- Modelo **`res.currency.rate.provider`** (patrón OCA) con `service` extensible, programación por intervalos, `next_run`/`last_successful_run`, trazabilidad `mail.thread` sobre `res.currency.rate` y wizard de recarga por rango.
- Tres proveedores reales: **BCRP** (series oficiales), **Decolecta** (con carga mensual masiva) y **ApisPeru**.
- **Tipo de cambio compra/venta diferenciado** (`exchange_rate_type`) propagado a factura, pago y `account.payment.register`, con `_force_convert` sobre `res.currency`.
- Múltiples tasas por día (`invoice_break_currency_rate`) reescribiendo `_get_query_rates`.
- **`mblz_l10n_pe_multicurrency_revaluation`**: tipo de cambio compra/venta **por cuenta contable** aplicado al reporte Enterprise de ganancias/pérdidas no realizadas.

### 2.4 Libros electrónicos y físicos (21 módulos, ~11 000 LOC)
Arquitectura: un modelo base `l10n_pe_reports.base` (periodo, indicador de operación, rango de fechas) + un wizard unificado `l10n_pe_reports.accounting.book.wizard` que despacha al libro concreto; cada libro es un `TransientModel` con `_get_query` → `_execute_query` → `_process_query` → generadores TXT/XLSX/ZIP en `reports/*.py`, más un módulo gemelo que añade el PDF físico.

| Libro | Formatos | LOC electrónico | PDF físico |
|---|---|---:|:--:|
| Registro de Compras (RCE) | **8.4 / 8.5** | 1 778 | sí |
| Registro de Ventas (RVIE) | **14.4** | 838 | sí |
| Libro Diario | 5.1 / 5.3 | 945 | sí |
| Diario simplificado | **5.2 / 5.4** | 929 | sí |
| Libro Mayor | 6.1 | 691 | sí |
| Caja y Bancos | 1.1 / 1.2 | 1 116 | sí |
| Activos Fijos | **7.1 / 7.4** | 964 | sí |
| Inventario Valorizado | 13.1 | 891 | sí |

Además `l10n_pe_reports_fields` (campos SUNAT sobre asiento/apunte/cuenta/diario: fecha SUNAT, estado PLE 1/8/9, exclusiones por diario) y `l10n_pe_reports_stock_fields` (estado PLE y tipo de operación sobre `stock.move`, `stock.move.line`, `stock.picking`, `stock.valuation.layer`).

**Incluye un manual de usuario de 714 líneas** (`docs/manual_usuario_libros_electronicos_peru.md`) que documenta criterios de inclusión columna por columna. Es documentación reutilizable tal cual.

### 2.5 Facturación electrónica (2 módulos, ~1 400 LOC)
`l10n_pe_edi_efact` extiende `l10n_pe_edi` de Enterprise con:
- Un **cuarto proveedor EDI: `ose`**, con WSDL de producción y pruebas configurables por compañía (`l10n_pe_edi_provider_ose_prod_wsdl` / `_test_wsdl`), firma, baja en dos pasos y consulta de CDR vía SOAP/zeep. Odoo solo trae IAP, Digiflow y SUNAT directo.
- 14 overrides sobre `account.edi.xml.ubl_pe` para casos reales: gratuitas, exportación, retenciones línea a línea, direcciones, términos de pago, totales.
- Wizard **nota de crédito motivo 13** (corrección de comprobante) y motivos de NC/ND extendidos.

### 2.6 Detracciones e inventario (8 módulos, ~2 900 LOC)
- `l10n_pe_detraction` (765): catálogo de 288 líneas de bienes/servicios sujetos a detracción, contabilización con diario y cuenta dedicados, tipo de operación.
- **`l10n_pe_txt_detraction`** (850): **TXT masivo para el Banco de la Nación** en las dos modalidades (proveedor y cliente), con número de lote, validaciones, HTML de excluidos, y creación + conciliación del pago desde el mismo wizard.
- `l10n_pe_sunat_catalog` / `l10n_pe_stock_sunat_catalog`: catálogos SUNAT 05, 12, 13, 53, 59 como modelos con datos maestros.
- `stock_delivery_guide`, `stock_related_document`, `stock_date_effective`, `invoice_dispatch_guide`: series de guías electrónicas por almacén, documentos relacionados en el picking con parsing serie-correlativo, fecha efectiva editable en el albarán.

---

## 3. Evaluación de calidad

### 3.1 Fortalezas
1. **Cobertura normativa única.** Es el único de los tres proyectos que genera los formatos **RCE 8.4/8.5 y RVIE 14.4** del régimen SIRE, además de **5.2/5.4** y **7.1/7.4**, que Enterprise 19 no cubre.
2. **Formatos físicos PDF y XLSX** de los ocho libros. Obligatorios para contribuyentes que legalizan libros y para revisión interna; hoy ausentes en `al_*` y en Enterprise.
3. **Criterios SUNAT explícitos.** La fecha SUNAT del asiento (`l10n_pe_reports_date`), el estado PLE 1/8/9 y las exclusiones por diario son reglas de negocio reales que los exportadores genéricos de Enterprise no aplican. Este es el aporte más subestimado del proyecto.
4. **Patrón de generación consistente**: `_get_query` → `_execute_query` → `_process_query` → `_generate_txt_file`/`_generate_xlsx_file`, con las clases de escritura separadas en `reports/`. Fácil de auditar y extender.
5. **Framework de proveedores de tasa** extensible y ya probado con 3 servicios.
6. **Datos maestros valiosos**: catálogo de detracciones (288 líneas), catálogos SUNAT 05/12/13/53/59, mapeo de impuestos PE.
7. **Documentación funcional** de 714 líneas, con tablas de criterios por columna.
8. Traducciones completas: 53 archivos `.po` en `es`, `es_PE` y `es_419`.
9. Seguridad correcta: los 20 módulos que declaran modelos nuevos traen su `ir.model.access.csv` (los que no lo traen solo declaran `AbstractModel` de reportes QWeb, que no lo requiere).

### 3.2 Debilidades
1. **Granularidad excesiva.** 60 módulos con un grafo de dependencias de hasta 6 niveles (`l10n_pe_edi_efact` depende de 12 módulos encadenados). Instalar la localización completa implica resolver un orden no trivial, y desinstalar una pieza rompe el conjunto.
2. **Cobertura de pruebas casi nula.** Solo 3 módulos (`invoice_currency_rate_update`, `l10n_pe_rate_update_decolecta`, `mblz_l10n_pe_multicurrency_revaluation`) tienen tests: 6 archivos para 21 400 LOC. Para 11 000 líneas de generación de archivos legales, es el riesgo más serio del proyecto.
3. **SQL crudo acoplado al ORM de la v18.** 15 archivos usan `cr.execute` con consultas construidas por f-string que referencian **alias generados por el query builder** (`account_move_line__move_id__l10n_latam_document_type_id`). Esos alias no son API pública y cambian entre versiones. El propio código lo admite: `# TODO: refactor query in the future`.
4. **Interpolación de identificadores en SQL.** `company_ids_str = f"({','.join(map(str, ...))})"` inyectado en el `WHERE`. Los valores vienen de `_get_company_ids()` (enteros del ORM), así que **no hay vector explotable hoy**, pero debe corregirse al migrar (parámetros `%s` con tupla).
5. **`requirements.txt` desactualizado.** Declara `pdf417gen==0.7.1`, `PyPDF2==2.12.1` y `Babel==2.9.1`; ninguno se importa en el código. Las dependencias reales son `xlsxwriter`, `zeep`, `requests`, `num2words`, `lxml`, `pytz`.
6. **Duplicación interna.** El par electrónico/físico de cada libro repite `_get_physical_period_label`, `_render_physical_pdf`, `_generate_physical_pdf_file` en los 8 módulos físicos, y `_generate_txt_file`/`_generate_xlsx_file`/`_save_generate_files` en los 8 electrónicos: ~16 implementaciones casi idénticas sin mixin común.
7. **Licencia propietaria de terceros.** Reutilizar el código exige verificar la titularidad antes de redistribuir.

---

## 4. Compatibilidad con Odoo 19 — hallazgos verificados

Se contrastaron los 406 métodos que el proyecto sobreescribe contra el árbol de código de Odoo 19 (`addons`, `odoo`, `ee19`).

### 4.1 Ruptura crítica: el generador UBL se reescribió por completo
En Odoo 19, `account_edi_ubl_cii` abandonó el modelo `_export_invoice_vals` / `_get_invoice_line_vals` (diccionarios + plantilla QWeb) y adoptó un **árbol de nodos** construido con `_add_invoice_*_nodes(document_node, vals)`.

Los 14 overrides de `l10n_pe_edi_efact` sobre `account.edi.xml.ubl_pe` apuntan a métodos que **ya no existen**:

| Método v18 sobreescrito | Estado en v19 |
|---|---|
| `_export_invoice_vals` | eliminado (solo sobrevive en CII/Factur-X) |
| `_get_invoice_line_vals` | → `_add_invoice_line_nodes` / `_get_invoice_line_node` |
| `_get_invoice_tax_totals_vals_list` | → `_add_invoice_tax_total_nodes` |
| `_get_invoice_monetary_total_vals` | → `_add_invoice_monetary_total_nodes` |
| `_get_invoice_line_price_vals` | → `_add_invoice_line_price_nodes` |
| `_get_invoice_line_item_vals` | → `_add_document_line_item_nodes` |
| `_get_partner_address_vals` | → `_get_address_node` |
| `_get_partner_party_legal_entity_vals_list` | → `_get_party_node` |
| `_get_invoice_payment_terms_vals_list` | → `_add_invoice_payment_terms_nodes` |

**Consecuencia:** el XML personalizado de eFact debe **reescribirse desde cero** contra la nueva API. La buena noticia: `l10n_pe_edi` de v19 ya implementa nativamente varios casos que eFact parcheaba — `_add_invoice_line_pricing_reference_nodes` (precio referencial), `_get_document_withholding_node` (retenciones), `_add_document_allowance_charge_nodes` (descuentos).

### 4.2 Lo que sí sobrevive
- **`account.edi.format` sigue existiendo** en v19: `l10n_pe_edi` mantiene `account_edi_format.py` y `account_edi_document.py`, y depende de `account_edi`. El mecanismo del proveedor OSE (firma, baja en dos pasos, consulta de CDR) es portable con cambios menores.
- **`zeep` cambió de ubicación**: en v19 se importa como `odoo.tools.zeep` (`from odoo.tools.zeep import Client, Settings`). Cambio mecánico de 4 imports.
- `_sync_tax_lines`, `_add_tax_details_in_base_line` y `_prepare_product_base_line_for_taxes_computation` siguen existiendo: los parches del motor de impuestos son portables, pero **deben revalidarse** porque el motor cambió su comportamiento interno entre 18 y 19.
- Las vistas **no usan `attrs=` ni `<tree>`** en ningún archivo: ya están en sintaxis moderna. No hay deuda de migración de vistas.

### 4.3 Lo que Enterprise 19 ya resuelve (verificado en código)
Buena parte de los formatos PLE **ya están implementados en Enterprise 19**, aunque no como archivos de datos sino como handlers de reportes, lo que los hace fáciles de pasar por alto:

| Formato | Dónde está en EE 19 |
|---|---|
| 1.1 / 1.2 Caja y Bancos | `l10n_pe_reports/models/account_ple_cash_bank.py` (`l10n_pe_export_ple_11/12_to_txt`) |
| 5.1 / 5.3 Diario | `l10n_pe_reports/models/account_general_ledger.py` (`l10n_pe_export_ple_51/53_to_txt`) |
| 6.1 Mayor | mismo archivo (`l10n_pe_export_ple_61_to_txt`) |
| 8.1 / 8.2 Compras | `data/account_ple_purchase_8_1/8_2_report.xml` |
| 14.1 Ventas | `data/account_ple_sales_14_1_report.xml` |
| 12.1 / 13.1 Inventario | `l10n_pe_reports_stock/wizard/stock_move_ple_report.py` |
| EEFF (balance, resultados) | `data/balance_sheet.xml`, `data/profit_loss.xml` |

**Enterprise 19 NO cubre:** 5.2/5.4 (diario simplificado), 7.1/7.4 (activos fijos), **8.4/8.5 (RCE)**, **14.4 (RVIE)**, ni ningún formato XLSX o PDF físico. Tampoco aplica los criterios SUNAT de fecha/estado/exclusión que sí implementa tecport.

**Esto cambia la decisión sobre 5 libros:** caja-bancos, diario, mayor e inventario valorizado no deben portarse como generadores propios — duplicarían a Enterprise. De ellos solo se aprovecha el **PDF físico, el XLSX y los criterios SUNAT**, montados encima del handler de EE.

### 4.4 Riesgo transversal: las consultas SQL
Los libros que sí se porten dependen de alias de JOIN generados por el ORM de la v18. En v19 el query builder cambió (objeto `SQL`, `_field_to_sql`). **Cada consulta debe reescribirse y revalidarse contra datos reales**; es el trabajo más voluminoso e imposible de automatizar de toda la migración.

---

## 5. Solapamiento con la suite `al_*` existente

### 5.1 Formatos PLE — cobertura comparada

| Formato | EE 19 | `al_l10n_pe_ple` | `ol_stock_kardex_pe` | tecport | Decisión |
|---|:--:|:--:|:--:|:--:|---|
| 1.1 / 1.2 Caja y Bancos | ✅ | — | — | ✅ | **reconstruir sobre EE** (solo PDF/XLSX + criterios) |
| 3.8 / 3.9 / 3.19 | — | ✅ | — | — | mantener `al_` |
| 4.1 | — | ✅ | — | — | mantener `al_` |
| 5.1 / 5.3 Diario | ✅ | — | — | ✅ | **reconstruir sobre EE** |
| 5.2 / 5.4 Diario simplificado | — | ✅ | — | ✅ | **contrastar** las dos implementaciones |
| 6.1 Mayor | ✅ | — | — | ✅ | **reconstruir sobre EE** |
| 7.1 / 7.3 / 7.4 Activos fijos | — | ✅ (7.1/7.3/7.4) | — | ✅ (7.1/7.4) | **contrastar** |
| 8.1 / 8.2 Compras PLE | ✅ | — | — | — | usar EE |
| 8.3 | — | ✅ | — | — | mantener `al_` |
| **8.4 / 8.5 Compras RCE** | — | — | — | ✅ | **absorber (clave)** |
| 9.1 / 9.2 | — | ✅ | — | — | mantener `al_` |
| 10.1–10.4 | — | ✅ | — | — | mantener `al_` |
| 12.1 / 13.1 Inventario | ✅ | — | ✅ | ✅ | **contrastar**; probable: EE/kardex + PDF de tecport |
| 14.1 Ventas PLE | ✅ | — | — | — | usar EE |
| 14.2 | — | ✅ | — | — | mantener `al_` |
| **14.4 Ventas RVIE** | — | — | — | ✅ | **absorber (clave)** |
| PDF físicos de los 8 libros | — | — | parcial | ✅ | **absorber** |
| XLSX de revisión de los 8 libros | — | — | ✅ (kardex) | ✅ | **absorber** |

### 5.2 Resto de procesos

| Proceso | Módulo `al_*` actual | Qué añade tecport | Decisión |
|---|---|---|---|
| Detracciones | `al_l10n_pe_detraction` (completo, con wizard de depósito) | **TXT masivo Banco de la Nación** (proveedor y cliente), catálogo de 288 líneas, tipo de operación | **fusionar**: portar `l10n_pe_txt_detraction` y el catálogo |
| Retenciones IGV | `al_l10n_pe_retention` (sobre `l10n_account_withholding_tax` nativo) | modelo más antiguo, integrado en eFact | descartar; mantener `al_` |
| Tipo de cambio | `al_l10n_pe_currency` (SUNAT + apis.net, compra/venta) | **framework multiproveedor**, BCRP, Decolecta, ApisPeru, cron programable, tasa compra/venta en pagos y `payment.register` | **absorber**: es superior al actual |
| Cierre de tipo de cambio | `al_l10n_pe_exchange_closure` (acumulado, auto-corrector) | tipo de cambio por cuenta en el reporte EE de revaluación | **fusionar** el campo por cuenta |
| Facturación electrónica | `al_l10n_pe_invoice` (+ `al_l10n_pe_edi_pos`) | **proveedor OSE genérico**, motivo NC 13, precio unitario referencial | **absorber** OSE; contrastar el resto |
| Formato PDF de factura | `al_l10n_pe_invoice` (`action_print_pdf`) | formato con 9 interruptores de configuración | **fusionar** los interruptores útiles |
| Serie y correlativo | `al_account_move_name_sequence` | **serie/correlativo a nivel de apunte** + índice + cron de reparación | **absorber**: es prerrequisito de los libros |
| Guías de remisión | `al_l10n_pe_delivery_guide_report` | series por almacén, documentos relacionados en picking | **fusionar** |
| Catálogos SUNAT | disperso | modelos `sunat.catalog.12/53/59`, `stock.sunat.catalog.05/12/13` con datos | **absorber** en `al_account_base` |
| Validación RUC/DNI | `l10n_pe_vat_sunat` (consulta a SUNAT) | validación **estructural** parametrizada por tipo de documento | **fusionar** |
| SIRE (API SUNAT) | `al_l10n_pe_sire` (completo, envío por API) | — (tecport solo genera archivos) | mantener `al_`; **conectar** con los formatos 8.4/8.5/14.4 |

---

## 6. Arquitectura destino propuesta

El principio es el que ya sigue la suite `al_*`: **un módulo por proceso de negocio**, no por campo.

```
al_account_base                 ← catálogos SUNAT 05/12/13/53/59, código de banco,
                                  establecimiento anexo, validación estructural RUC/DNI,
                                  tipo de diario (movimiento/apertura/cierre)

al_l10n_pe_currency  (ampliar)  ← res.currency.rate.provider + BCRP + Decolecta + ApisPeru
                                  + tipo de cambio compra/venta en move/payment/register
                                  + múltiples tasas por día
                                  + tipo de cambio por cuenta contable

al_l10n_pe_invoice   (ampliar)  ← serie/correlativo en apunte (+ índice + cron)
                                  + interruptores de formato PDF
                                  + motivo NC 13 / motivos NC-ND extendidos

al_l10n_pe_edi_ose   (NUEVO)    ← proveedor EDI OSE genérico (WSDL configurable),
                                  reescrito contra la API UBL de nodos de v19

al_l10n_pe_ple       (ampliar)  ← formatos 8.4/8.5 y 14.4 (RCE/RVIE) completos
                                  + campos SUNAT (fecha, estado PLE 1/8/9, exclusiones)
                                  + criterios aplicados también a los libros de EE

al_l10n_pe_ple_books (NUEVO)    ← capa de presentación de los 8 libros:
                                  PDF físico + XLSX de revisión, alimentados por
                                  los handlers de EE donde EE ya genera el TXT

al_l10n_pe_detraction (ampliar) ← TXT masivo Banco de la Nación + catálogo 288 líneas

al_l10n_pe_stock     (NUEVO)    ← series de guías por almacén, documentos relacionados
                                  en picking, fecha efectiva, campos PLE de inventario
```

### 6.1 Correcciones de diseño obligatorias en la absorción

1. **No duplicar a Enterprise.** Donde EE ya emite el TXT (1.1, 1.2, 5.1, 5.3, 6.1, 8.1, 8.2, 14.1, 12.1, 13.1), el módulo destino aporta el PDF/XLSX y los criterios SUNAT, consumiendo los datos del handler de EE. Duplicar el extractor es la forma más rápida de acabar con dos cifras distintas para el mismo mes.
2. **Mixin único de generación.** Sustituir las ~16 implementaciones duplicadas por un `l10n_pe.ple.book.mixin` con `_get_rows()` abstracto y `_generate_txt/_xlsx/_pdf/_zip` concretos.
3. **Eliminar el SQL con alias del ORM.** Reescribir las consultas que sí se porten con el ORM de v19 (`_search` + objeto `SQL`), o al menos con nombres de tabla explícitos y parámetros `%s`. Nunca interpolar identificadores por f-string.
4. **Tests desde el primer commit.** Cada formato absorbido entra con, como mínimo: test de estructura de línea (longitudes y separadores del TXT), test de importes/redondeo y test de periodo. Es la condición para confiar en archivos que se presentan a SUNAT.
5. **Versionado según la convención del proyecto:** `N.AAAAMMDD`.
6. **Un solo punto de entrada de menú**, integrado en el menú de localización existente, sin módulos `*_menu` separados.

---

## 7. Plan de migración por fases

| Fase | Alcance | Entregable | Días |
|---|---|---|---:|
| **0. Preparación** ✅ | Auditoría de licencias; verificación del entorno; exportación de los libros de referencia desde v18; inventario de dependencias | [Acta de licencias](FASE0_ACTA_LICENCIAS.md) · [Entorno y validación](FASE0_ENTORNO_Y_VALIDACION.md) · [Estructura de referencia](REFERENCIA_ESTRUCTURA.md) | **hecha** |
| **1. Base y catálogos** | Absorber catálogos SUNAT, código de banco, establecimiento anexo, validación estructural RUC/DNI y tipo de diario en `al_account_base` | `al_account_base` v2 + tests de validación de RUC | 2–3 |
| **2. Tipo de cambio** | Portar `res.currency.rate.provider` y los 3 proveedores; unificar con `al_l10n_pe_currency`; migrar tipo de cambio compra/venta a factura/pago/register; añadir tipo de cambio por cuenta al cierre | `al_l10n_pe_currency` v2 + tests de los 3 proveedores (respuestas mockeadas) | 3–4 |
| **3. RCE 8.4 / 8.5** ✅ | Enterprise 19 ya los emitía, pero incompletos y con el motor de consulta roto: extracción reescrita con el ORM y campos 33/38/39/40 poblados | [Estructura oficial](ESTRUCTURA_RCE_8_4_8_5.md) · [Bug de EE](BUG_EE_RCE_SQL.md) · `al_l10n_pe_ple` v4.20260815, 59 tests | **hecha** |
| **3b. RVIE 14.4** ✅ | Mismo tratamiento para el registro de ventas: 33 campos (la nota 7 del anexo excluye del archivo los campos 34-40), extracción por ORM, reglas de anulados a cero y de notas de crédito de periodos anteriores | [Estructura oficial](ESTRUCTURA_RVIE_14_4.md) · 11 tests | **hecha** |
| **4. Libros restantes y contraste** | Contrastar 5.2/5.4 y 7.1/7.4 (tecport vs `al_l10n_pe_ple`) y 12.1/13.1 (EE vs kardex vs tecport) con el mismo juego de datos; quedarse con una implementación por formato y borrar la otra | Decisión documentada + formato ganador por libro | 3–4 |
| **5. Presentación de libros** | `al_l10n_pe_ple_books`: render PDF base parametrizado + XLSX para los 8 libros, alimentado por los handlers de EE donde corresponda (recordar: el div raíz del QWeb necesita clase `article`) | `al_l10n_pe_ple_books` | 4–5 |
| **6. Serie/correlativo y formato de factura** | Absorber `serie_correlative` en el apunte (con índice y cron); integrar los interruptores del formato PDF en `al_l10n_pe_invoice`; motivo NC 13 | `al_l10n_pe_invoice` v7 | 3–4 |
| **7. EDI OSE** ⚠️ | Módulo nuevo `al_l10n_pe_edi_ose`: proveedor con WSDL configurable sobre `account.edi.format` de v19; **reescribir los overrides UBL contra la API de nodos**, descartando los que v19 ya resuelve nativamente | `al_l10n_pe_edi_ose` + tests de firma/baja mockeados | 4–5 |
| **8. Detracciones e inventario** | TXT Banco de la Nación (proveedor y cliente) + catálogo de 288 líneas en `al_l10n_pe_detraction`; guías por almacén y documentos relacionados en `al_l10n_pe_stock` | 2 módulos ampliados/nuevos | 3–4 |
| **9. Documentación y cierre** | Adaptar el manual de 714 líneas a la suite `al_*`; README + `index.html` por módulo según la convención del proyecto | Documentación completa | 2 |

**Total: 32–42 días**, o **26–33 días** si las fases 1, 2, 6 y 8 (independientes entre sí) se solapan. Las fases 3 → 4 → 5 son secuenciales.

### 7.1 Orden recomendado si hay que priorizar
Para entregar valor pronto: **Fase 3 (RCE 8.4/8.5 y RVIE 14.4) → Fase 2 (tipo de cambio) → Fase 8 (TXT detracciones) → Fase 7 (OSE)**. Son las cuatro capacidades que hoy no existen ni en `al_*` ni en Enterprise y que un cliente peruano nota de inmediato.

---

## 8. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Las consultas SQL no se pueden portar mecánicamente | Alto — es el grueso del esfuerzo de la Fase 3 | Reescribir con el ORM de v19 en lugar de traducir; validar cada libro contra un cierre mensual real comparando el TXT byte a byte con el generado en v18 |
| El XML UBL de eFact hay que rehacerlo | Alto | Antes de reescribir, verificar caso por caso qué resuelve ya `l10n_pe_edi` v19: puede que la mitad de los 14 overrides sobren |
| Cero tests heredados | Alto — un TXT mal formado es un rechazo de SUNAT | Ningún formato se da por migrado sin test de estructura, importes y periodo |
| Duplicar generadores que EE ya tiene | Alto — dos cifras distintas para el mismo mes | Regla de la sección 6.1.1: donde EE emite el TXT, el módulo `al_*` solo aporta presentación y criterios |
| Licencia propietaria de terceros | Legal | Fase 0 bloqueante: confirmar por escrito el derecho de reutilización |
| Solapamiento 5.2/5.4, 7.1/7.4, 13.1 entre tecport y `al_*` | Medio — riesgo de regresión | Fase 4 dedicada: elegir una implementación por formato comparando salidas con el mismo juego de datos |
| Dependencia de Enterprise (`l10n_pe_reports`, `l10n_pe_edi`) | Medio | Ya asumida por ambas suites; documentarla explícitamente en los manifests |

---

## 9. Criterios de aceptación

1. Cada formato migrado genera un TXT **idéntico en estructura** al de referencia (nº de campos, orden, longitudes, nomenclatura del archivo), comparado automáticamente contra [REFERENCIA_ESTRUCTURA.md](REFERENCIA_ESTRUCTURA.md). **Excepción:** para 5.1, 5.2, 5.3, 5.4 y 6.1 la referencia del origen está defectuosa (los tres primeros emiten el mismo archivo) — ahí la referencia es la especificación de SUNAT y la salida de Enterprise 19.
2. Cobertura de tests ≥ 1 test de estructura + 1 de importes por cada formato PLE migrado.
3. Ningún generador propio duplica un formato que Enterprise 19 ya emite.
4. Ningún módulo nuevo usa `cr.execute` con identificadores interpolados.
5. La suite completa instala en una base v19 limpia en un solo `-i`, sin resolver orden manualmente.
6. Cada módulo nuevo o ampliado trae README + página de descripción, según la convención de la suite.
7. `requirements.txt` refleja únicamente las dependencias realmente importadas.

---

## 10. Anexo — matriz de decisión completa (60 módulos)

| Módulo origen | LOC Py | Decisión | Destino |
|---|---:|---|---|
| base_country_filter | 89 | descartar | — |
| contact_bank_code | 34 | absorber | `al_account_base` |
| contact_identification_validation | 146 | fusionar | `al_account_base` |
| invoice_break_currency_rate | 63 | absorber | `al_l10n_pe_currency` |
| invoice_currency_rate_update | 513 | absorber | `al_l10n_pe_currency` |
| invoice_dispatch_guide | 81 | fusionar | `al_l10n_pe_stock` |
| invoice_exchange_rate | 214 | absorber | `al_l10n_pe_currency` |
| invoice_exchange_rate_type | 429 | absorber | `al_l10n_pe_currency` |
| invoice_fix_sequence | 41 | descartar | — |
| invoice_force_exchange_rate | 85 | fusionar | `al_l10n_pe_currency` |
| invoice_format_base | 206 | fusionar | `al_l10n_pe_invoice` |
| invoice_origin_document | 104 | fusionar | `al_l10n_pe_invoice` |
| invoice_other_document_type | 82 | fusionar | `al_l10n_pe_invoice` |
| invoice_override_functions | 284 | descartar (revalidar en v19) | — |
| invoice_purchase_exchange_rate | 161 | absorber | `al_l10n_pe_currency` |
| invoice_report_format | 196 | fusionar | `al_l10n_pe_invoice` |
| invoice_serie_correlative | 430 | **absorber** | `al_l10n_pe_invoice` |
| its_editar_digito_decimal | 46 | descartar | — |
| l10n_pe_annex_establishment | 61 | absorber | `al_account_base` |
| l10n_pe_bank_code | 78 | absorber | `al_account_base` |
| l10n_pe_detraction | 765 | fusionar (catálogo y tipo de operación) | `al_l10n_pe_detraction` |
| l10n_pe_edi_efact | 1287 | **absorber con reescritura** | `al_l10n_pe_edi_ose` |
| l10n_pe_edi_format_base | 99 | descartar | — |
| l10n_pe_edi_report_format | 32 | descartar | — |
| l10n_pe_format_base | 186 | descartar | — |
| l10n_pe_invoice_dispatch_guide | 65 | descartar | — |
| l10n_pe_invoice_other_document_type | 50 | descartar | — |
| l10n_pe_invoice_price_unit_reference | 248 | fusionar (v19 ya trae `_add_invoice_line_pricing_reference_nodes`) | `al_l10n_pe_invoice` |
| l10n_pe_journal_type | 45 | absorber | `al_account_base` |
| l10n_pe_localization_menu | 27 | descartar | — |
| l10n_pe_rate_update_api_peru_dev | 245 | absorber | `al_l10n_pe_currency` |
| l10n_pe_rate_update_bcrp | 252 | **absorber** | `al_l10n_pe_currency` |
| l10n_pe_rate_update_decolecta | 590 | **absorber** | `al_l10n_pe_currency` |
| l10n_pe_report_format | 214 | descartar | — |
| l10n_pe_reports_electronic_cash_bank | 1116 | reconstruir sobre EE (1.1/1.2) | `al_l10n_pe_ple_books` |
| l10n_pe_reports_electronic_diary | 945 | reconstruir sobre EE (5.1/5.3) | `al_l10n_pe_ple_books` |
| l10n_pe_reports_electronic_diary_simplified | 929 | contrastar (5.2/5.4) | `al_l10n_pe_ple` |
| l10n_pe_reports_electronic_fixed_assets | 964 | contrastar (7.1/7.4) | `al_l10n_pe_ple` |
| l10n_pe_reports_electronic_inventory_valued | 891 | contrastar (13.1) | `al_l10n_pe_ple` / kardex |
| l10n_pe_reports_electronic_ledger | 691 | reconstruir sobre EE (6.1) | `al_l10n_pe_ple_books` |
| l10n_pe_reports_electronic_purchase | 1778 | **absorber** (8.4/8.5) | `al_l10n_pe_ple` |
| l10n_pe_reports_electronic_sale | 838 | **absorber** (14.4) | `al_l10n_pe_ple` |
| l10n_pe_reports_fields | 278 | **absorber** | `al_l10n_pe_ple` |
| l10n_pe_reports_menu | 325 | descartar (empaquetado) | — |
| l10n_pe_reports_physical_* (8 módulos) | 1581 | reconstruir (contenido PDF) | `al_l10n_pe_ple_books` |
| l10n_pe_reports_stock_fields | 310 | absorber | `al_l10n_pe_stock` |
| l10n_pe_stock_sunat_catalog | 594 | absorber | `al_account_base` / `al_l10n_pe_stock` |
| l10n_pe_sunat_catalog | 208 | absorber | `al_account_base` |
| l10n_pe_txt_detraction | 850 | **absorber** | `al_l10n_pe_detraction` |
| mblz_l10n_pe_multicurrency_revaluation | 935 | fusionar (tipo de cambio por cuenta) | `al_l10n_pe_exchange_closure` |
| stock_date_effective | 237 | fusionar | `al_l10n_pe_stock` |
| stock_delivery_guide | 134 | absorber | `al_l10n_pe_stock` |
| stock_related_document | 389 | absorber | `al_l10n_pe_stock` |
