# MIGRATION_CHANGELOG — ol_stock_kardex_pe

## Origen

Reemplaza funcionalmente a `apps/peru/l10n_pe_kardex` (v16, "Odoo Peru").
**No es una migración 1:1**: el legado quedó inviable en v19 y el módulo se
reescribió sobre la arquitectura nueva.

## Por qué no se migró el legado

| Problema del legado (v16) | Solución en ol_stock_kardex_pe (v19) |
|---|---|
| Construido sobre `stock.valuation.layer` (`move.stock_valuation_layer_ids`, `value_svl`) — **modelo eliminado en v19** | `stock.move.value` / `is_in` / `is_out` / `_get_valued_qty()`; saldo inicial con `qty_available`/`total_value` + contexto `to_date`/`warehouse_id` |
| Dominio `[('type','=','product')]` (obsoleto) | `[('is_storable','=',True)]` |
| XLSX escrito a disco (`~/Reporte Kardex.xlsx`) | `io.BytesIO`, descarga vía campo Binary del wizard |
| Columna "operación" en texto libre (`picking_type_id.name`) | Códigos SUNAT Tabla 12 (`l10n_pe_operation_type` del picking + fallback por ubicaciones) |
| Sin cabecera SUNAT (RUC, Tabla 5/6, método de valuación) | Bloque de cabecera completo según plantilla oficial `234_formato131.xls` |
| Modelo muerto `kardex.report.rc` con `create()` de campos inexistentes | Eliminado |
| Modelo auxiliar `report.base` para descargar | Patrón del wizard EE (`report_data`/`report_filename` + `act_url`) |
| Solo XLSX | XLSX + PDF QWeb + vista interactiva con drill-down |

## Decisiones (plan: `ol_new_apps/docs/PLAN_ol_stock_kardex_pe.md`)

- Depende de `l10n_pe_reports_stock` (EE) para reutilizar los campos SUNAT
  (Tabla 5/12, establecimiento anexo) y de `l10n_pe_edi` (indirecto) para la
  Tabla 6; el TXT PLE sigue siendo responsabilidad del módulo EE.
- D1: el 13.1 por almacén es aproximado (valorización por compañía en Odoo);
  el modo consolidado es el que cuadra con el TXT PLE.
- D3: no se hereda `_append_historic_valuation_lines` del wizard EE (bug
  aparente: `dictfetchall()` sin query previa); el saldo inicial usa la API
  nativa `to_date`.

## 0.2026071602 — Rendimiento y arquitectura

- **`l10n_pe.kardex.line` deja de ser `TransientModel` y pasa a vista SQL**
  (`_auto = False`): ya no se puebla en cada corrida. El saldo corrido se
  calcula con *window functions* de PostgreSQL (consolidado y por almacén).
  El `init()` detecta el `relkind` para migrar la tabla previa a vista sin
  romper el upgrade.
- Saldo inicial vía un único `DISTINCT ON` sobre la vista (sin recorrer la
  historia). Campos de documento/operación como computados no almacenados,
  por lote. Filas de saldo inicial/totales solo en memoria (`SimpleNamespace`).
- **Generación en segundo plano**: modelo persistente `l10n_pe.kardex.report`
  + `ir.cron` (despertado con `_trigger()`), menú *Kardex SUNAT · Generados*.
- El PDF/XLSX y la cuadratura contable quedan idénticos; el refactor es
  transparente al renderizado. Análisis en `docs/kardex/ANALISIS_RENDIMIENTO.md`.
- Gotcha v19: `registry.in_test_mode()` no existe → usar `config['test_enable']`
  / `modules.module.current_test`.

## 0.2026071601

- Versión inicial: wizard, motor de cálculo, vista interactiva, XLSX 13.1 y
  12.1, PDF QWeb, menú en Inventario ▸ Informes.
