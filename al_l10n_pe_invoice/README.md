# PE - Comprobantes Electrónicos (AL)

Campos y detalle tributario del comprobante electrónico (IGV/ISC/IVAP/
ICBPER, exoneradas/inafectas, vínculo con la orden de venta) y su
representación impresa (A4 y ticket 80mm) reutilizando el core
`l10n_pe_edi` para el QR oficial y el monto en letras.
**Guía funcional:** [`docs/reportes_factura.md`](docs/reportes_factura.md).

## Qué hace

- **Reporte A4** (acción `report_cpe_invoice_a4`, template
  `report_cpe_invoice_a4_main`): recuadro SUNAT (RUC/tipo/número),
  cliente y fechas, detalle de líneas, totales con desglose tributario,
  monto en letras (core `_l10n_pe_edi_amount_to_text`), detracción
  (`al_l10n_pe_detraction`), cuotas de crédito, QR oficial del XML
  firmado y bloques opcionales de firmas / cuentas bancarias.
- **Ticket 80mm** (acción `report_cpe_ticket`): lo mismo condensado.
- Estilo en `static/src/css/report_cpe.css` (bundles
  `web.report_assets_common` / `_pdf`) — sin `<style>` inline.
- Ajustes ▸ Perú ▸ **Comprobantes electrónicos**: firmas, representante
  y eslogan de la compañía.

## Qué NO hace (fuera de alcance a propósito)

No toca el envío EDI (XML UBL, SUNAT, Banco de la Nación): eso lo
resuelve `l10n_pe_edi`. No duplica el QR ni el monto en letras del core.
La guía de remisión es un módulo independiente:
`al_l10n_pe_delivery_guide_report`.

## Pruebas

```bash
./odoo-bin -c cfg/my/pe.cfg -d ol_pe_v19 -u al_l10n_pe_invoice \
  --test-enable --test-tags /al_l10n_pe_invoice --stop-after-init
```
