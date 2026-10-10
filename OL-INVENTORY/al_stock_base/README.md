# PE - Base Inventario (AL) — Odoo 19

Guía funcional: [GUIA_FUNCIONAL.md](GUIA_FUNCIONAL.md)

Módulo **base y liviano** para las transferencias de inventario de la
localización peruana. Añade al formulario de la transferencia la página
**Logística PE**, el único lugar donde la suite muestra los datos peruanos,
agrupados por tema (como «Facturación PE» en la factura).

## Contenido

- Página **Logística PE** (`l10n_pe_stock`), visible en compañías peruanas.
- Dos contenedores donde cuelgan los módulos de la suite:
  - `l10n_pe_stock_guide_groups`: guía de remisión y transporte
    (`al_l10n_pe_delivery_guide_report`, con los campos de `l10n_pe_edi_stock`;
    su página «EDI PE» queda oculta);
  - `l10n_pe_stock_groups`: libros electrónicos (`al_l10n_pe_ple`: tipo de
    operación de la tabla 12 y consignación) y requerimiento de obra
    (`al_construction_material_request`).

La vista tiene prioridad 1 para existir antes que las demás herencias; cada
módulo hereda la vista que crea sus campos y los mueve a su grupo.

## Depende de

`stock_account` (aporta `stock.picking.country_code`).
