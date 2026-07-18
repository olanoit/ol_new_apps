[← Mapa de cobertura](README.md)

# Libro 9 — Registro de Consignaciones (PLE 9.1 / 9.2)

Generado por `al_l10n_pe_ple` desde **Perú ▸ Libros PLE ▸ Exportar PLE**.
Libro **mensual**: `090100` (9.1, rol **consignador**: bienes entregados en
consignación) y `090200` (9.2, rol **consignatario**: bienes recibidos).

## Fuente de datos

Los albaranes (`stock.picking`) se marcan con el campo **Consignación PLE
(Libro 9)** — visible en el formulario del albarán junto al tipo de
operación SUNAT — con seis clases:

| Valor | Libro | Efecto en cantidades |
|---|---|---|
| 9.1 Entrega en consignación | 9.1 | entregada (+) |
| 9.1 Devolución del consignatario | 9.1 | devuelta (−) |
| 9.1 Venta de bienes consignados | 9.1 | vendida (−) |
| 9.2 Recepción en consignación | 9.2 | recibida (+) |
| 9.2 Devolución al consignador | 9.2 | devuelta (−) |
| 9.2 Venta de bienes recibidos | 9.2 | vendida (−) |

El **contacto del albarán** es la contraparte (consignatario en 9.1,
consignador en 9.2). Solo se consideran movimientos en estado *hecho*
dentro del mes exportado.

## Estructura

**9.1 — 22 campos** / **9.2 — 21 campos** (espejo, con RUC del consignador
en lugar de tipo+nº de documento):

| # (9.1) | Campo SUNAT | Fuente Odoo |
|---|---|---|
| 1 | Periodo `AAAAMM00` | wizard |
| 2 | Cód. catálogo (T13) | `9` (catálogo propio) |
| 3 | Tipo de existencia (T5) | `product.l10n_pe_type_of_existence` (de `l10n_pe_reports_stock`; fallback `99`) |
| 4 | Código de existencia | `default_code` (fallback `P<id>`) |
| 5 | CUO | id del `stock.move` (`I<prod>-<partner>` en saldo inicial) |
| 6 | Nombre de la existencia | nombre del producto (80 car.) |
| 7 | Unidad de medida (T6) | `uom_id.l10n_pe_edi_measure_unit_code` (fallback `NIU`) |
| 8–10 | Fecha / serie / nº de guía de remisión | `l10n_latam_document_number` de la guía electrónica (`l10n_pe_edi_stock`); si no hay, dígitos del nombre del albarán; serie `0` si no aplica |
| 11–14 | Tipo / fecha / serie / nº del CdP | factura publicada de la venta ligada al albarán (solo clases «venta»); si no hay: `00`, vacío, `0`, `0` |
| 15 | Fecha de entrega/devolución | fecha efectiva del movimiento |
| 16–18 | Consignatario (T2 + nº doc + razón social) | contacto del albarán |
| 19–21 | Cant. entregada (+) / devuelta (−) / vendida (−) | cantidad hecha del movimiento según la clase (excluyentes) |
| 22 | Estado de operación | `1` |

En 9.2 los campos 16–17 son RUC (11 díg.) y razón social del consignador, y
las cantidades son recibida/devuelta/vendida.

## Saldo inicial

Según el Anexo 2, la primera tupla de cada existencia es el **saldo
inicial**. El módulo lo calcula como entregas − devoluciones − ventas de
todos los movimientos marcados **anteriores** al mes exportado, por par
(producto, contraparte), y lo emite como fila con guía `0/0`, CdP `00` y
fecha = primer día del mes.

## Limitaciones

- Requiere marcar manualmente cada albarán de consignación (Odoo no
  distingue la figura mercantil por sí solo; el campo `owner_id` puede
  ayudar como referencia visual pero no se usa automáticamente).
- El CdP de las clases «venta» se resuelve por mejor esfuerzo desde la
  orden de venta del albarán; verificar en operaciones facturadas por lote.
