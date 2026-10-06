Historial de cambios — PE - Kardex SUNAT (Formato 13.1 / 12.1)
==============================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/ol_stock_kardex_pe.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 6.20261006 — 06/10/2026

- El TXT del PLE de inventarios de Enterprise (12.1 y 13.1) usa el documento guardado en cada movimiento: corrige la serie duplicada de las facturas (FF001 en vez de F001) y las ventas del punto de venta informadas como guía con la serie WHPOS.

## 5.20261006 — 06/10/2026

- Sin datos no se descarga nada: el Excel, el PDF, la vista en pantalla y la generación en segundo plano muestran un mensaje en vez de un archivo vacío; los generados sin datos quedan en «Sin datos».
- El comprobante se guarda en cada movimiento: entregas facturadas en partes, devoluciones con su nota de crédito y ventas del punto de venta con su factura o boleta (antes salían con el nombre interno de la transferencia).
- Corrección manual del documento por movimiento o por transferencia, protegida del llenado automático, y acciones masivas para completar o recalcular.
- Validación del formato SUNAT del documento; el historial se completa al actualizar el módulo.

## 4.20260718 — 27/09/2026

- Las cantidades son las recibidas o entregadas de verdad, no las pedidas: una recepción parcial cerrada sin pendiente ya no infla el kardex.
- Los periodos se cortan en hora de Lima: un movimiento del último día a las 20:00 ya no se va al mes siguiente, y la fecha del Excel coincide con la del PDF.
- Los ajustes de inventario y las mermas salen en el kardex por almacén, y los traslados entre almacenes aparecen con las operaciones 11 y 21.
- Si elige almacenes, el kardex sale por almacén con el saldo de cada uno.
- Un usuario solo de Inventario puede sacar el kardex aunque no tenga permisos de ventas o facturación.
- Cada compañía ve solo sus kardex generados, y no se puede pedir el kardex de una compañía no activa.
- Ventas y compras sin comprobante salen con tipo 09 (guía de remisión), como en el TXT del PLE.
- Un error al generar en segundo plano queda como «Error» en vez de bloquear la cola, y un reporte colgado en «Generando» se vuelve a tomar.
- Kardex más rápido con muchos productos.

## 14/09/2026

- Menú Kardex ordenado junto al resto de libros en la app Perú.

## 2.20260718 — 19/07/2026

- Periodo por mes o por rango de fechas, también en Excel, PDF y segundo plano.
- Botón Ver Kardex en el producto y la categoría con los filtros precargados.
- Menú en la app Perú: Generar Kardex y Kardex generados.

## 0.2026071602 — 16/07/2026

- Kardex en pantalla sobre una vista de base de datos, sin poblar registros.
- Generación en segundo plano y lista de kardex generados.

## 0.2026071601 — 16/07/2026

- Formatos 13.1 y 12.1 en Excel y PDF, y kardex interactivo en pantalla.
