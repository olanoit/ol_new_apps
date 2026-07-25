# Comprobantes electrónicos (SUNAT Perú)

## Origen

Migración y refactor de la parte de reportes de factura del módulo v18
`al_l10n_pe_edi` (`ce18/al/montegrande/alta/al_accounting/al_l10n_pe_edi`).
Del módulo original **no** se migró:

- `account_edi_format.py` / `account_edi_xml_ubl_pe.py`: lógica de EDI/XML,
  no es un reporte — queda pendiente en otra tarea.
- La guía de remisión: es ahora `al_l10n_pe_delivery_guide_report`, un
  módulo independiente.
- Código muerto: `_l10n_pe_edi_get_serie_folio` y `get_rpt_totals` (el core
  v19 ya trae una mejor versión del primero; el segundo no se usaba y
  apuntaba a campos inexistentes), `btn_debug`, el CSS huérfano de
  `static/src/css/style.css` y el `security/ir.model.access.csv` que daba
  acceso a un modelo de otro módulo.

## Refactor v19: reusar el core en vez de duplicarlo

| v18 (duplicado propio) | v19 (core `l10n_pe_edi`) |
|---|---|
| `l10n_pe_dte_qrcode` + `l10n_pe_dte_qr_image` (compute + librería `qrcode`, QR **sin** hash de firma → no conforme) | `_l10n_pe_edi_get_extra_report_values()['qr_str']`: QR oficial extraído del XML firmado (incluye `ds:DigestValue`), renderizado con `/report/barcode` |
| `amount_total_words` + `_convert_number_to_spanish_words_sunat` (~120 líneas) | `_l10n_pe_edi_amount_to_text()` (num2words) |
| `<style>` inline en cada plantilla (~200 líneas duplicadas) | `static/src/css/report_cpe.css` en `web.report_assets_common` / `_pdf` (patrón de `account`) |
| Plantilla monolítica | Contenedor + `_document` por registro (patrón `account.report_invoice`) |

Antes del envío a SUNAT no existe XML firmado, así que
`_l10n_pe_edi_get_extra_report_values()` devuelve `{}` y el reporte
muestra un placeholder «Pendiente de envío a SUNAT» en lugar del QR
(mismo criterio que la guía de remisión del core).

## Qué sí aporta este módulo (no existe en el core)

- **Detalle tributario como campos almacenados** (`l10n_pe_edi_amount_igv`,
  `_base`, `_exonerated`, `_unaffected`, `_isc`, `_icbper`, `_ivap`,
  `_others` + `_retention` no almacenado): clasifica los impuestos por
  código SUNAT vía `_prepare_edi_tax_details()` con el split
  stored/non-stored obligatorio desde Odoo 18.
- `is_credit`, `sale_id`, `external_purchase` (orden de venta) y las
  cuotas de crédito (`get_data_dues`, sobre `payment_term_details` nativo).
- Bloque de detracción sobre los campos de `al_l10n_pe_detraction`
  (`l10n_pe_detraction_applies` / `_type_id` / `_percent` / `_amount`) —
  en v18 el A4 y el ticket usaban dos fuentes de datos distintas y ambas
  rotas (campos inexistentes o claves que nunca existieron en
  `_l10n_pe_edi_get_spot()`).
- Firmas / eslogan / representante por compañía y cuentas bancarias.

## Diseño de los PDF

Todo el estilo vive en `static/src/css/report_cpe.css`, con prefijo
`.cpe-` y solo propiedades compatibles con wkhtmltopdf (tablas, sin
grid/flex). Secciones del A4: encabezado con recuadro SUNAT
(RUC/tipo/número), tarjeta de cliente y fechas, detalle de líneas,
totales con el desglose tributario (solo filas con monto), monto en
letras + glosa + leyenda EDI, detracción, cuotas, información legal + QR,
firmas opcionales, cuentas bancarias y pie de contacto. El ticket 80mm
presenta lo mismo condensado.
