Historial de cambios — PE - Kardex SUNAT (Formato 13.1 / 12.1)
==============================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/ol_stock_kardex_pe.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 12.20261009 — 09/10/2026

- Kardex generado con chatter: historial del estado de cada corrida.
- Etiquetas más cortas en los asistentes: «Incluir sin movimientos» y «Reemplazar corregidos a mano».

## 11.20261008 — 08/10/2026

- Etiquetas en español: los campos sin etiqueta propia (Activo, Nombre, Compañía, contadores…) y los heredados de Odoo (Creado por, Mensajes, Actividades…) ya no se muestran en inglés.

## 10.20261008 — 08/10/2026

- Los asistentes validan en el servidor que lo que reciben sea de su compañía (_check_company_auto y check_company).

## 9.20261008 — 08/10/2026

- Ícono nativo de la app de Odoo a la que pertenece (sin imágenes propias ni el logo de la Marca Perú).
- La compañía es de solo lectura en los formularios y listas: se toma de la compañía activa.

## 8.20261007 — 07/10/2026

- PLE 13.1, campo 17 (método de valuación, tabla 14 del Anexo 3): el costo estándar se informa como «9 - Otros»; Enterprise ponía «3», que es el método de existencias básicas.
- PLE 13.1 y costos en destino: cada costo va en el periodo de su fecha (fila con operación 26). Antes uno validado en febrero para una compra de enero salía en el TXT de enero y en febrero quedaba escondido en el saldo inicial; ahora el saldo inicial no lo incluye y el saldo acumulado se rehace.

## 7.20261007 — 07/10/2026

- TXT del PLE (12.1 y 13.1): el periodo y los saldos iniciales se cortan en hora de Lima; antes un movimiento del 31 por la noche caía en el mes siguiente y el último día del mes quedaba fuera. Incluye las sucursales con el RUC de la compañía principal.
- TXT del PLE: la unidad de medida es la del producto (la misma de la cantidad), el producto sin código interno lleva uno estable, el nombre no lleva «|», «/» ni «\», el saldo inicial lleva el tipo de existencia real y la fecha del documento nunca queda después del periodo.
- Documento por movimiento: si el comprobante pasa a borrador o se anula, el movimiento deja de citarlo; una factura revertida por nota de crédito ya no se toma; en almacenes de 2 o 3 pasos el emparejamiento ya no confunde el traslado interno con una devolución.

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
