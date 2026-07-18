# PE - Kardex SUNAT (Formato 13.1 / 12.1)

Módulo para Odoo 19 Enterprise que genera el **Registro de Inventario
Permanente** de la localización peruana en formato imprimible SUNAT:

- **Formato 13.1** — Registro de Inventario Permanente **Valorizado**.
- **Formato 12.1** — Registro de Inventario Permanente en **Unidades Físicas**.

Complementa al módulo oficial EE `l10n_pe_reports_stock` (que genera el TXT
PLE): reutiliza sus campos SUNAT y añade la capa visual que falta.

## Funcionalidades

- **Integrado a la aplicación única «Perú»**: además de Inventario ▸
  Informes, el menú **Perú ▸ Kardex (12.1/13.1)** (vía `al_account_base`)
  ofrece «Generar Kardex» y «Kardex generados» junto al resto de libros
  PLE (`al_l10n_pe_ple`).
- **Kardex interactivo en pantalla**: líneas con saldo corrido (cantidad,
  costo unitario y costo total), agrupables por producto/almacén, con sumas
  por columna y botón para abrir el documento origen (comprobante,
  transferencia o movimiento).
- **Exportación XLSX**: réplica de la plantilla oficial `234_formato131.xls`
  de SUNAT — bloque de cabecera por producto (período, RUC, razón social,
  establecimiento, código de existencia, Tabla 5, descripción, Tabla 6,
  método de valuación) + tabla ENTRADAS/SALIDAS/SALDO FINAL con fila de
  TOTALES. Generado 100 % en memoria.
- **PDF QWeb**: mismo formato, A4 horizontal, una página por producto.
- **Modo consolidado** (por compañía, cuadra con el TXT PLE) o **por almacén**
  (una hoja/sección por almacén, incluye traslados internos con operaciones
  11/21 de la Tabla 12).

## Fuentes de datos (arquitectura Odoo 19)

En v19 ya no existe `stock.valuation.layer`; el módulo se apoya en:

- `stock.move`: `value`, `is_in`, `is_out`, `_get_valued_qty()`.
- `product.product`: `qty_available` y `total_value` con contexto
  `to_date`/`warehouse_id` para el saldo inicial histórico.
- Campos SUNAT de `l10n_pe_reports_stock`: `l10n_pe_type_of_existence`
  (Tabla 5, producto), `l10n_pe_operation_type` (Tabla 12, picking),
  `l10n_pe_anexo_establishment_code` (almacén).
- Tabla 6: `uom.uom.l10n_pe_edi_measure_unit_code` (de `l10n_pe_edi`).
- Tabla 10: `l10n_latam_document_type_id` de la factura/boleta vinculada al
  movimiento (`sale_line_id`/`purchase_line_id` → `invoice_lines`).

## Arquitectura (rendimiento)

El kardex **no puebla ningún registro**: `l10n_pe.kardex.line` es un modelo
respaldado por una **vista SQL** (`_auto = False`) sobre `stock.move`. El saldo
corrido (cantidad, valor y costo unitario) se calcula con *window functions* de
PostgreSQL, tanto consolidado (`PARTITION BY producto, compañía`) como por
almacén (`PARTITION BY producto, almacén`). Ventajas frente a poblar un modelo
transient en cada corrida:

- Cero `INSERT`s: la base de datos hace la agregación en C, no Python.
- Escala a miles de movimientos/año (índice `stock_move(product_id, date)`).
- Los campos de documento (Tabla 10/serie/folio) y operación (Tabla 12) son
  calculados **no almacenados**, resueltos por lote solo para las filas leídas.

El saldo inicial de un período se obtiene con un único `DISTINCT ON` sobre la
vista (el último saldo antes de `date_from`), sin recorrer toda la historia.

Para volúmenes muy grandes existe **generación en segundo plano**: el botón
correspondiente crea un registro `l10n_pe.kardex.report`, un `ir.cron` lo
procesa (despertado al instante con `_trigger()`) y el usuario descarga el
archivo desde *Inventario ▸ Informes ▸ Kardex SUNAT · Generados*.

Ver análisis detallado en `docs/kardex/ANALISIS_RENDIMIENTO.md`.

## Uso

`Inventario ▸ Informes ▸ Kardex SUNAT (13.1 / 12.1)`

1. Elegir formato (13.1 valorizado / 12.1 físico) y período. El **período** se
   selecciona **Por mes** (opción por defecto — el kardex SUNAT se declara
   mensualmente, calcula automáticamente desde/hasta) o como **Rango de
   fechas** libre.
2. Filtrar opcionalmente por almacén, productos o categorías.
3. **Ver en pantalla** (abre la vista SQL filtrada, instantáneo),
   **Exportar Excel**, **PDF** o **Generar en segundo plano**.

### Acceso directo desde un producto o categoría

El botón **Ver Kardex** aparece en la cabecera del formulario de un producto
(plantilla o variante almacenable) y de una categoría de producto. Abre el
asistente con ese producto/categoría ya precargado en los filtros, listo para
elegir período y generar.

## Notas / limitaciones conocidas

- Odoo valoriza el inventario **por compañía**, no por almacén: en modo "por
  almacén" el 13.1 usa la aproximación nativa (`total_value` con
  `warehouse_id` en contexto) y valúa los traslados internos al costo
  promedio corriente del kardex. Para valores contablemente exactos usar el
  modo consolidado.
- La fecha de la columna FECHA es la del movimiento de stock; el tipo, serie
  y número provienen del comprobante vinculado (o del documento interno si no
  hay comprobante, con tipo `00`).
- Tipo de operación (Tabla 12): se usa `l10n_pe_operation_type` del picking;
  si falta, se deduce de las ubicaciones (compra 02, venta 01, devoluciones
  24/25, producción 10/19, ajuste 28, merma 13, traslados 11/21, otros 99).
