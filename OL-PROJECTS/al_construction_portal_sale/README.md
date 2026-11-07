# Portal de obra: cambios del cliente (AL)

Documentación funcional: [Aplicación de obra en el celular](../../mkdocs/content/applications/services/project/construction/planning/field_app.md)

Puente de `al_construction_portal` con `al_construction_planner_sale` (paquete 6,
CR-53). Se instala solo con los dos.

- Servicio `construction.portal.service.change_order` (ruta
  `/construction/api/v1/resident/change-order`): crea el cambio de obra en
  borrador pedido por el cliente, con las fotos, la firma en pantalla, el
  nombre y cargo de quien lo pidió, las partidas afectadas o la partida nueva
  y el metrado estimado.
- Constancia en PDF (`action_report_change_record`, formato común de
  `al_report_base`) enviada al «Contacto del cliente en obra» de la obra.
- Sin el puente, el portal responde que los cambios de obra piden el puente de
  Ventas.
