# PE - Reporte de Guía de Remisión Electrónica (AL)

Representación impresa propia de la Guía de Remisión Electrónica
Remitente (SUNAT) para `stock.picking`, independiente del módulo de
reportes de factura.
**Guía funcional:** [`docs/guia_remision.md`](docs/guia_remision.md).

## Qué hace

- Botón **"Guía de remisión"** en el picking validado (junto al de entrega
  nativo): genera el PDF con datos del traslado, remitente/destinatario,
  detalle de bienes agrupado por producto (con series/lotes), datos del
  transportista/vehículo y el QR de SUNAT.
- Agrupa `move_ids` por producto/UdM (`_get_grouped_move_lines`) en vez de
  mostrar una línea por movimiento.
- Peso bruto con fallback: si la suma de pesos de línea es 0 (productos
  sin peso configurado), usa `shipping_weight` en vez de reportar 0 KGM.

## Qué NO hace (fuera de alcance a propósito)

Este módulo es solo el reporte impreso; el envío de la guía a SUNAT, la
gestión del vehículo/operador y el QR del CDR los resuelve
`l10n_pe_edi_stock` (core). El reporte de factura es un módulo
independiente: `al_l10n_pe_invoice`.

## Pruebas

```bash
./odoo-bin -c cfg/my/pe.cfg -d ol_pe_v19 -u al_l10n_pe_delivery_guide_report \
  --test-enable --test-tags /al_l10n_pe_delivery_guide_report --stop-after-init
```
