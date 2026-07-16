# Plan de desarrollo — `ol_stock_kardex_pe` (Kardex SUNAT Formato 13.1 / 12.1)

**Fecha:** 2026-07-16 · **Target:** Odoo 19 Enterprise (EE19) · **Autor plan:** Claude + Vicente Catacora
**Ubicación destino:** `myodoo/ol_new_apps/ol_stock_kardex_pe/`

---

## 1. Objetivo

Construir un módulo de **Kardex** (Registro de Inventario Permanente) para la localización peruana en Odoo 19 que entregue:

1. **Formato 13.1 SUNAT** — *Registro de Inventario Permanente Valorizado — Detalle del Inventario Valorizado* — en formato **imprimible/legalizable** (XLSX y PDF), replicando la plantilla oficial `docs/234_formato131.xls`.
2. **Formato 12.1 SUNAT** — *Registro de Inventario Permanente en Unidades Físicas* (mismo motor, sin columnas de costo).
3. **Kardex operativo interactivo** (estilo `qt_stock_card_kardex`): consulta en pantalla por producto/almacén/período con saldo corrido, drill-down al documento origen y reporte resumen (saldo inicial, entradas, salidas, saldo final por producto).

> **No duplicar**: la generación del **TXT PLE** 12.1/13.1 ya la resuelve el módulo oficial EE `l10n_pe_reports_stock`. Este módulo cubre lo que falta: el formato *visual* con cabeceras SUNAT, totales y saldo corrido por movimiento, más la vista operativa.

---

## 2. Contexto normativo — Formato 13.1 (según `docs/234_formato131.xls`, SUNAT)

Estructura de la hoja oficial (una sección por **producto × establecimiento**):

**Cabecera:**
| Campo | Fuente en Odoo 19 |
|---|---|
| PERÍODO | wizard (`date_from`/`date_to`) |
| RUC | `company_id.vat` |
| APELLIDOS Y NOMBRES / RAZÓN SOCIAL | `company_id.name` |
| ESTABLECIMIENTO (1) | `stock.warehouse.l10n_pe_anexo_establishment_code` (campo del módulo EE) o dirección del almacén |
| CÓDIGO DE LA EXISTENCIA | `product.default_code` |
| TIPO (TABLA 5) | `product.template.l10n_pe_type_of_existence` (campo del módulo EE) |
| DESCRIPCIÓN | `product.name` |
| CÓDIGO UNIDAD DE MEDIDA (TABLA 6) | `uom.uom.l10n_pe_edi_measure_unit_code` (de `l10n_pe_edi`) |
| MÉTODO DE VALUACIÓN | `product.categ_id.property_cost_method` → mapa SUNAT: average=`PROMEDIO`, fifo=`PEPS`, standard=`COSTO ESTÁNDAR` |

**Columnas de detalle (14):**

| Grupo | Columnas |
|---|---|
| Documento de traslado / comprobante | FECHA · TIPO (TABLA 10) · SERIE · NÚMERO |
| Operación | TIPO DE OPERACIÓN (TABLA 12) |
| ENTRADAS | CANTIDAD · COSTO UNITARIO · COSTO TOTAL |
| SALIDAS | CANTIDAD · COSTO UNITARIO · COSTO TOTAL |
| SALDO FINAL | CANTIDAD · COSTO UNITARIO · COSTO TOTAL |

Fila **TOTALES** al pie de cada sección. El 12.1 es idéntico sin las columnas de costo (solo cantidades).

**Tablas SUNAT involucradas y su fuente:**
- **Tabla 5** (tipo de existencia): ya modelada como Selection en `l10n_pe_reports_stock/models/product.py`.
- **Tabla 6** (unidad de medida): `uom.uom.l10n_pe_edi_measure_unit_code` (`l10n_pe_edi`).
- **Tabla 10** (tipo de comprobante): `l10n_latam_document_type_id.code` de la factura/boleta vinculada; `00` si no hay comprobante.
- **Tabla 12** (tipo de operación): `stock.picking.l10n_pe_operation_type` (Selection completa de 38+9 códigos ya en `l10n_pe_reports_stock/models/stock_picking.py`, con default por tipo de picking: outgoing→01, incoming→02, internal→21).

---

## 3. Estado del arte analizado

### 3.1 Odoo 19 — cambio radical en valorización (CRÍTICO)

**`stock.valuation.layer` YA NO EXISTE en v19** (verificado: no hay `_name = 'stock.valuation.layer'` en `addons/` ni `ee19/`). La valorización se movió a `stock.move` (`addons/stock_account/models/stock_move.py`):

- `value` (Monetary): valor del movimiento; 0 si no está valorado.
- `is_in` / `is_out` (Boolean, stored compute): movimiento valorado de entrada/salida.
- `remaining_qty` / `remaining_value` (compute): remanente para FIFO.
- `price_unit` (Float — marcado con comentario "To remove and only use value": **no construir sobre él**).
- Métodos: `_get_price_unit()`, `_get_valued_qty(lot=None)`, `_is_in()`, `_is_out()`.
- **`product.value`** (`product_value.py`): historial de revaluaciones manuales (cambio de standard_price, valor de lote o valor de move) — equivale a las antiguas capas manuales.
- **`product.product`**: `avg_cost` y `total_value` (compute con `@api.depends_context('to_date', 'company', 'warehouse_id')`) → **valuación histórica a fecha** vía `product.with_context(to_date=...).total_value / avg_cost`; también `qty_available` con `to_date`.

Consecuencia: cualquier lógica tipo kardex en v19 se construye **sobre `stock.move` directamente**, no sobre capas.

### 3.2 Módulo oficial EE `l10n_pe_reports_stock` (referencia principal)

`ee19/l10n_pe_reports_stock` — depends: `l10n_pe_edi`, `purchase`, `sale_stock`. Aporta:

- Wizard `l10n_pe.stock.ple.wizard`: genera TXT PLE 12.1/13.1 (nombre `LE{RUC}{AAAA}{MM}00{1201|1301}...txt`).
- Campos reutilizables: `l10n_pe_type_of_existence` (product.template), `l10n_pe_operation_type` (stock.picking), `l10n_pe_anexo_establishment_code` + `country_code` (stock.warehouse).
- Patrones de datos a reutilizar (`wizard/stock_move_ple_report.py`):
  - Dominio de moves: `state='done'`, rango fechas, `location_id.usage` o `location_dest_id.usage` in `('supplier','customer','inventory','production')`, orden `product_id.id, date`.
  - Serie/folio: `_get_serie_folio()` con regex sobre `l10n_latam_document_number` del picking o `invoice.name`/`bill.name`.
  - Documento: `move.sale_line_id.invoice_lines.move_id[:1]` (factura venta) / `move.purchase_line_id.invoice_lines.move_id[:1]` (factura compra).
  - Valorizado: `move._get_valued_qty()`, `move._get_price_unit()`, `move.value`, `move.remaining_qty/remaining_value`.
  - Saldo inicial: asiento `A1` con `qty_available` a `date_from` y tipo de operación `16` (saldo inicial).
  - Método de valuación: `{'average':'1','fifo':'2','standard':'3'}` desde `property_cost_method`.
- **Limitaciones observadas** (oportunidad para nuestro módulo): no lleva saldo corrido por movimiento con costo promedio recalculado (usa `remaining_qty/value` del move, orientado a FIFO); una sola línea de saldo inicial global (no por almacén); no hay salida visual XLSX/PDF; el bloque `_append_historic_valuation_lines` referencia `self.env.cr.dictfetchall()` sin query previa (bug aparente en la versión actual).

### 3.3 Módulo legado `apps/peru/l10n_pe_kardex` (v16, análisis completo)

Wizards transient `kardex.report` (físico) y `valuation.kardex.report` (valorizado), salida solo XLSX. **Veredicto: no migrable 1:1, solo sirve como referencia funcional.** Problemas:

- Construido sobre `stock.valuation.layer` (`move.stock_valuation_layer_ids`, `value_svl`) → **inexistente en v19**.
- Dominio `[('type','=','product')]` → en v19 es `is_storable = True`.
- Escribe el XLSX a `~/Reporte Kardex.xlsx` en disco (antipatrón; debe ser `io.BytesIO`).
- "Operación" en texto libre (`picking_type_id.name`), no códigos Tabla 12; no es conforme SUNAT.
- Modelo `kardex.report.rc` con `create()` de campos inexistentes (código muerto/roto).
- Sí rescatable como idea: hoja por ubicación, saldo corrido `saldo_valor/saldo_cantidad` (promedio móvil), filas de saldo inicial y totales por producto.

### 3.4 Referencia comercial `qt_stock_card_kardex` (apps.odoo.com, 19.0)

Features a igualar/superar: valorización AVCO con recálculo por recepción; Stock Card por producto + Summary global; XLSX/PDF rápidos sin wkhtmltopdf externo para Excel; filtros por período/categoría/productos; vistas con búsqueda, agrupación por categoría y referencias clickeables; manejo de devoluciones, landed costs, multi-moneda, revaluaciones, stock negativo. Requisitos que impone (AVCO + valuación automática) — nuestro módulo debe soportar también standard/FIFO reportando el costo que Odoo registró en `move.value`.

---

## 4. Decisión de arquitectura

**Opción elegida: módulo complementario sobre EE.**

```
ol_stock_kardex_pe
└── depends: ['l10n_pe_reports_stock', 'stock_account']
```

Justificación: reutiliza los campos SUNAT (Tabla 5/12, establecimiento anexo) y la semántica de datos ya validada por Odoo/Vauxoo, evita duplicar configuración para el usuario, y el proyecto es EE19 (memoria del proyecto Inveragro). `l10n_pe_reports_stock` arrastra `l10n_pe_edi`, `purchase`, `sale_stock` — todo necesario de todos modos.

*Plan B (si algún despliegue fuera CE):* extraer los 3 campos a un mini-módulo `ol_stock_kardex_pe_base` con las mismas Selections y hacer que `ol_stock_kardex_pe` dependa de él con un bridge auto-instalable hacia EE. **No se implementa en fase 1.**

### Motor de cálculo: Python sobre `stock.move` (sin SQL crudo)

- Universo: mismo dominio del wizard EE (state done, usages externos) **+ opción interna por almacén** (ver §6, decisión D2).
- Saldo inicial por producto: `product.with_context(to_date=date_from, warehouse_id=wh.id).qty_available` y `avg_cost/total_value` (API v19 nativa, respeta compañía).
- Saldo corrido: acumulación en Python `(saldo_qty, saldo_val)`; costo unitario de salida según método:
  - `average`/`standard`: CU salida = `abs(move.value) / qty` que Odoo ya calculó (fiel a contabilidad).
  - `fifo`: ídem — `move.value` ya refleja el consumo de capas; el kardex reporta lo contabilizado.
  - Saldo final CU = `saldo_val / saldo_qty` (con guarda división por cero y `float_round` a `decimal_precision` de costo).

---

## 5. Diseño del módulo

### 5.1 Estructura de archivos

```
ol_stock_kardex_pe/
├── __init__.py
├── __manifest__.py
├── README.md
├── MIGRATION_CHANGELOG.md          # referencia al legado l10n_pe_kardex
├── security/
│   └── ir.model.access.csv         # wizard + línea: grupo stock.group_stock_user
├── wizards/
│   ├── __init__.py
│   ├── kardex_report_wizard.py     # l10n_pe.kardex.report.wizard
│   └── kardex_report_wizard_views.xml
├── models/
│   ├── __init__.py
│   └── kardex_line.py              # l10n_pe.kardex.line (transient) para vista interactiva
├── reports/
│   ├── kardex_xlsx.py              # generación xlsxwriter (BytesIO → Binary)
│   ├── kardex_report_templates.xml # QWeb PDF formato 13.1 / 12.1
│   └── kardex_report_actions.xml
└── views/
    └── menu_views.xml              # Inventario ▸ Informes ▸ Kardex SUNAT
```

### 5.2 Manifest (convenciones del proyecto)

```python
{
    'name': 'PE - Kardex SUNAT (Formato 13.1 / 12.1)',
    'countries': ['pe'],
    'version': '0.2026071601',
    'category': 'OL-INVENTORY/Apps',
    'author': 'OLANOIT',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://github.com/olanoit',
    'license': 'LGPL-3',
    'depends': ['l10n_pe_reports_stock', 'stock_account'],
    'external_dependencies': {'python': ['xlsxwriter']},
    'data': [...],
    'installable': True,
}
```

### 5.3 Wizard `l10n_pe.kardex.report.wizard`

| Campo | Tipo | Notas |
|---|---|---|
| `date_from` / `date_to` | Date, required | default mes anterior completo (patrón EE con `daterange`) |
| `report_type` | Selection `[('13.1','Valorizado'),('12.1','Físico')]` | default 13.1 |
| `warehouse_ids` | M2m `stock.warehouse` | vacío = todos; una sección/hoja por almacén |
| `product_ids` | M2m `product.product`, domain `[('is_storable','=',True)]` | vacío = todos con movimientos o saldo |
| `categ_ids` | M2m `product.category` | filtro alternativo |
| `group_by_warehouse` | Boolean | si False: kardex consolidado compañía (coincide con TXT PLE) |
| `include_zero` | Boolean | incluir productos sin movimientos con saldo inicial |
| `report_data`/`report_filename`/`mimetype` | Binary/Char | patrón de descarga del wizard EE |

Acciones: `action_view` (abre `l10n_pe.kardex.line` en list view), `action_export_xlsx`, `action_print_pdf`.

Validación en `default_get`: `company.country_code == 'PE'` (patrón EE).

### 5.4 Modelo de líneas `l10n_pe.kardex.line` (TransientModel)

Campos: wizard_id, product_id, warehouse_id, date, document_type_code (Tabla 10), serie, folio, operation_type (Tabla 12, related/copy del picking), picking_id, move_id, qty_in, cost_unit_in, cost_total_in, qty_out, cost_unit_out, cost_total_out, balance_qty, balance_unit_cost, balance_value, `line_type` (`opening|move|total`).

Vista list: `open_form_view` deshabilitado, botón que abre el `picking_id`/factura origen (drill-down estilo qt). Agrupable por producto y almacén. `default_order = 'product_id, date, id'`.

### 5.5 Algoritmo (pseudocódigo)

```
para cada almacén seleccionado (o compañía si consolidado):
    moves = stock.move búsqueda con dominio EE ± filtro almacén, orden producto/fecha
    para cada producto:
        saldo_qty  = product.with_context(to_date=date_from, warehouse_id=wh).qty_available
        saldo_val  = product.with_context(to_date=date_from, warehouse_id=wh).total_value
        emitir línea 'opening' (op 16, doc '00')
        para cada move del período:
            qty  = move._get_valued_qty()          # UdM base
            val  = abs(move.value)
            si move.is_in:  saldo_qty += qty; saldo_val += val
            si move.is_out: saldo_qty -= qty; saldo_val -= val
            cu_mov = val / qty (guard: qty != 0)
            doc = factura venta [:1] o compra [:1] o l10n_latam_document_number del picking
            emitir línea 'move' con serie/folio (_get_serie_folio del wizard EE reutilizado
                        vía herencia o copia documentada)
            balance_unit_cost = saldo_val / saldo_qty (guard)
        emitir línea 'total' (sumas entradas/salidas + saldo final)
```

Notas: 12.1 = mismo recorrido sin columnas de costo. Cantidades siempre convertidas a `product.uom_id` (`uom._compute_quantity`). Redondeos con `float_round`/`float_is_zero` usando `Product Price`/`Product Unit`.

### 5.6 Salidas

- **XLSX** (`xlsxwriter` sobre `io.BytesIO`, nunca a disco): una hoja por almacén (o "CONSOLIDADO"); por producto: bloque cabecera formato 13.1 (período, RUC, razón social, establecimiento, código, Tabla 5, descripción, Tabla 6, método valuación) + tabla 14 columnas con merges ENTRADAS/SALIDAS/SALDO FINAL + fila TOTALES — réplica de `234_formato131.xls`.
- **PDF QWeb**: misma estructura, orientación horizontal, `t-out` (no `t-esc`), paperformat propio A4 landscape con márgenes reducidos.
- **Vista interactiva**: list view de `l10n_pe.kardex.line` con `group_by` producto, sumas en columnas de cantidades/valores.

### 5.7 Menús y accesos

- `Inventario ▸ Informes ▸ Kardex SUNAT (13.1/12.1)` — grupo `stock.group_stock_user`.
- Acceso también desde `Contabilidad ▸ Informes` (opcional, fase 2).
- `ir.model.access.csv`: wizard y línea para `stock.group_stock_user` (crud completo, son transient).

---

## 6. Decisiones abiertas / riesgos

| # | Tema | Riesgo/Decisión |
|---|---|---|
| D1 | **Costo por almacén**: Odoo valora por compañía, no por almacén. `avg_cost` con `warehouse_id` en contexto existe en v19, pero el costo de salidas en `move.value` es global. | Kardex **valorizado por almacén será aproximado** si hay multi-almacén con costos distintos. Default recomendado: 13.1 consolidado por compañía (igual que el TXT PLE) y por-almacén solo el 12.1 físico. Confirmar con contabilidad Inveragro. |
| D2 | Transferencias internas entre almacenes: el dominio EE las excluye (solo usages externos). Para kardex por almacén deben incluirse (op. Tabla 12: 21/11). | Incluirlas solo en modo `group_by_warehouse`, valoradas a costo promedio del momento. |
| D3 | `_append_historic_valuation_lines` del wizard EE tiene un bug aparente (`dictfetchall` sin query). | No heredar ese método; nuestro saldo inicial usa la API `to_date` nativa. Reportar upstream si se confirma. |
| D4 | Productos con tracking por lote/serie y costo por lote (`product.value` con `lot_id`). | Fase 1: kardex a nivel producto. Kardex por lote = fase 3 (SUNAT no lo exige en 13.1). |
| D5 | Multi-moneda: `move.value` está en moneda compañía (PEN esperado). | Sin conversión; validar que compañía use PEN. |
| D6 | Volumen: cliente con muchos moves (>100k) — recorrido Python puede ser lento. | Fase 1 Python puro con `read_group`/prefetch; si perf insuficiente, optimizar con `_read_group` por lotes (mantener API ORM, no SQL crudo). Meta: 10k moves < 10 s. |
| D7 | Devoluciones (`to_refund`), scrap, ajustes de inventario: dirección la dan `is_in/is_out` nativos. | Confiar en `is_in/is_out`; mapear op. Tabla 12 por defecto: scrap→13, ajuste inventario→28, devolución cliente→24, devolución proveedor→25 (extender el compute del picking EE con estos defaults — herencia de `_compute_l10n_pe_operation_type`). |

---

## 7. Fases de desarrollo

| Fase | Entregable | Estimación |
|---|---|---|
| **F1 — Esqueleto + motor** | Módulo instalable, wizard, motor de cálculo (líneas transient), vista interactiva list. Casos: compra, venta, ajuste, devolución. | 2–3 días |
| **F2 — XLSX 13.1/12.1** | Export xlsxwriter réplica de `234_formato131.xls`, multi-hoja por almacén, totales. | 1–2 días |
| **F3 — PDF QWeb** | Reporte PDF landscape 13.1/12.1 con paperformat propio. | 1 día |
| **F4 — Tabla 12 extendida + drill-down** | Herencia `_compute_l10n_pe_operation_type` (scrap/ajustes/devoluciones), botones de navegación al documento origen. | 1 día |
| **F5 — Tests + QA** | `TestKardex(TransactionCase)`: AVCO multi-precio, FIFO, saldo inicial, devolución, período vacío, cuadratura contra `total_value` a `date_to` y contra el TXT del wizard EE. Datos reales de Inveragro/chota. | 1–2 días |
| **F6 — Docs** | README, MIGRATION_CHANGELOG (mapa legado→nuevo), captura de pantallas. | 0.5 día |

**Total estimado: 6.5–9.5 días.**

### Criterios de aceptación

1. El XLSX 13.1 replica la plantilla SUNAT (`234_formato131.xls`) campo por campo, con Tablas 5/6/10/12 y método de valuación.
2. Saldo final del kardex a `date_to` == `product.with_context(to_date=date_to).qty_available` y `total_value` (cuadratura cantidad y valor, tolerancia redondeo de precio).
3. Las cifras del período coinciden con el TXT PLE 13.1 del wizard EE para el mismo rango (mismos moves, mismos costos).
4. Sin uso de APIs removidas: cero referencias a `stock.valuation.layer`, `price_unit` como fuente primaria, `type='product'`, `attrs`, `t-esc`.
5. XLSX generado 100% en memoria (`BytesIO`), sin escritura a disco.

---

## 8. Referencias

- Plantilla SUNAT: `ol_new_apps/docs/234_formato131.xls` (Formato 13.1, autor SUNAT, 2006).
- Doc localización: https://www.odoo.com/documentation/19.0/es_419/applications/finance/fiscal_localizations/peru.html (módulos `l10n_pe`, `l10n_pe_edi`, `l10n_pe_reports`, `l10n_pe_edi_stock`, `l10n_pe_reports_stock`).
- Módulo oficial EE: `ee19/l10n_pe_reports_stock` (wizard `l10n_pe.stock.ple.wizard`).
- Valorización v19: `addons/stock_account/models/stock_move.py` (`value`, `is_in/is_out`, `_get_price_unit`, `_get_valued_qty`), `product_value.py`, `product.py` (`avg_cost`, `total_value` con `to_date`/`warehouse_id`).
- Legado (solo referencia funcional): `apps/peru/l10n_pe_kardex` — **no migrar 1:1**.
- Benchmark comercial: https://apps.odoo.com/apps/modules/19.0/qt_stock_card_kardex (AVCO, stock card + summary, XLSX/PDF, drill-down).
