# Portal de obra: caja chica y entrega a rendir (AL)

Documentación funcional: [Aplicación de obra en el celular](../../mkdocs/content/applications/services/project/construction/planning/field_app.md)

Puente de `al_construction_portal` con `al_l10n_pe_cash_fund` (paquete 6, CR-55).
Se instala solo con los dos.

- Servicios `expense` y `settle` de `construction.portal.service` (rutas
  `/construction/api/v1/resident/expense` y `/resident/settle`).
- El comprobante es una factura de proveedor en borrador (`account.move`,
  `in_invoice`) con el fondo, la obra, la partida y quién la registró; el
  proveedor se busca o se crea por su RUC. En una factura (tipo 01) el monto
  incluye el IGV de compra por defecto de la compañía.
- La rendición (`l10n_pe.cash.settlement`) queda en borrador con esos
  comprobantes; Contabilidad los publica y la confirma.
- El fondo es del contacto del residente (`partner_id`): no exige ficha de
  empleado ni la aplicación Gastos.
