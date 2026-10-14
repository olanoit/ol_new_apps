# PE - Tienda en línea peruana (AL)

Documentación funcional: [Checkout peruano](../../mkdocs/content/applications/sales/ecommerce/peruvian_checkout.md)

Módulo técnico `al_website_sale_pe`. En la dirección de facturación del
portal y del checkout, el cliente elige **boleta o factura** y su **RUC o
DNI** se consulta en SUNAT.

## Lo que ya trae Odoo 19

- `l10n_latam_base`: tipo y número de documento obligatorios en la dirección
  de facturación (`L10nLatamBasePortalAccount`).
- `l10n_pe`: departamento, provincia y distrito (`L10nPEPortalAccount`).
- `l10n_pe` decide el comprobante: con RUC (código 6), factura; con otro
  documento, boleta (`_get_l10n_latam_documents_domain`).

## Lo que agrega

- `WebsiteSalePeAddress` (hereda de `L10nPEPortalAccount`) pasa a la plantilla
  `l10n_pe_receipt` y los tipos RUC y DNI.
- La plantilla extiende `l10n_latam_base.address_form_fields` con:
  - el selector «Boleta | Factura» antes del tipo de documento;
  - el botón «Consultar en SUNAT» junto al número.
- Ruta `/shop/l10n_pe/document_lookup`:
  - es JSON y pública;
  - acepta 10 consultas por sesión;
  - usa `sudo()` justificado y `_l10n_pe_lookup_document` de
    `l10n_pe_vat_sunat`.
- Parche de la interacción `CustomerAddress`:
  - el comprobante ajusta el tipo de documento;
  - un RUC o DNI completo dispara la consulta;
  - el departamento, la provincia y el distrito se cargan en cascada.

## Pruebas

- `tests/`: consulta con datos, sin datos, solo RUC/DNI, límite por sesión y
  formulario con el selector.
- Validado en `ol_pe_v19` con una consulta real a SUNAT (RUC 20131312955).

## Licencia

OPL-1.
