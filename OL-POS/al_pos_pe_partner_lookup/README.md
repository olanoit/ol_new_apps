# PE - Cliente por RUC/DNI en el TPV (AL)

Documentación funcional: [Cliente por RUC o DNI](../../mkdocs/content/applications/sales/point_of_sale/customer_lookup.md)

Módulo técnico `al_pos_pe_partner_lookup`. En la lista de clientes del TPV,
si la búsqueda es un RUC (11 dígitos) o un DNI (8) que no está registrado,
el botón **Crear cliente … desde SUNAT** lo crea con los datos de la consulta
y lo elige en la orden.

## Cómo funciona

- `res.partner.l10n_pe_pos_create_from_document(number)`:
  - si el documento ya existe, devuelve ese cliente;
  - si no, consulta con `_l10n_pe_lookup_document` de `l10n_pe_vat_sunat` y
    crea el cliente.

  Exige permiso de creación de contactos.
- Parche OWL de `PartnerList`: el getter `l10nPeDocument` y el botón en el
  estado «sin resultados».
- El formulario completo de cliente del TPV (`base.view_partner_form`) ya
  consulta SUNAT por el onchange de `l10n_pe_vat_sunat`. Este módulo agrega el
  atajo desde la búsqueda.

## Pruebas

- `tests/`: creación desde RUC y DNI, cliente existente, número no válido,
  consulta sin datos y permisos.
- Validado en `ol_pe_v19` con una consulta real a SUNAT (RUC 20100130204).

## Licencia

OPL-1.
