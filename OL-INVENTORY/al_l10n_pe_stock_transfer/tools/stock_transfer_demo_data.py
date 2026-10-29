# -*- coding: utf-8 -*-
"""Datos de traslados para las capturas de la ficha (se ejecuta con ``odoo shell``).

Crea, en la compañía activa:

* dos almacenes con dirección y código de establecimiento anexo distintos
  (Planta Ate, anexo 0001, y Obra Surco, anexo 0002);
* andamios propios y andamios alquilados a un tercero (Alquiler de Equipos,
  propietario: consignación nativa de Odoo);
* dos traslados internos hechos de la planta a la obra, uno con bienes propios
  y otro con los alquilados (motivo 04 propuesto);
* una compra recogida por la empresa en el local del proveedor (motivo 02);
* la devolución de los andamios de terceros a su propietario (motivo 06).

No envía nada a SUNAT: solo deja las transferencias hechas con la modalidad de
transporte elegida. Es idempotente (si existe el almacén demo, no hace nada).
"""


def ruc(base10):
    """RUC con su dígito verificador (módulo 11 de SUNAT)."""
    total = sum(int(d) * w for d, w in zip(base10, (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)))
    return base10 + str((11 - total % 11) % 10)


company = env.company
Warehouse = env['stock.warehouse']
if Warehouse.search([('code', '=', 'DTP'), ('company_id', '=', company.id)], limit=1):
    print('Los datos de traslados ya existen.')
else:
    # Consignación: el campo «Propietario» en recepciones y transferencias.
    env.ref('base.group_user').implied_ids |= env.ref('stock.group_tracking_owner')
    district = company.partner_id.l10n_pe_district or env['l10n_pe.res.city.district'].search([], limit=1)
    Partner = env['res.partner']
    addr_plant = Partner.create({
        'name': 'Planta Ate', 'parent_id': company.partner_id.id, 'type': 'other',
        'street': 'Av. Nicolás Ayllón 4200', 'l10n_pe_district': district.id, 'l10n_pe_annex_code': '0001',
        'country_id': env.ref('base.pe').id})
    addr_site = Partner.create({
        'name': 'Obra Surco', 'parent_id': company.partner_id.id, 'type': 'other',
        'street': 'Av. Primavera 1550', 'l10n_pe_district': district.id, 'l10n_pe_annex_code': '0002',
        'country_id': env.ref('base.pe').id})
    plant = Warehouse.create({'name': 'Planta Ate', 'code': 'DTP', 'partner_id': addr_plant.id,
                              'company_id': company.id})
    site = Warehouse.create({'name': 'Obra Surco', 'code': 'DTO', 'partner_id': addr_site.id,
                             'company_id': company.id})
    owner = Partner.create({
        'name': 'Alquiler de Equipos S.A.C.', 'vat': ruc('2061111111'), 'is_company': True, 'street': 'Jr. Los Andamios 300',
        'l10n_pe_district': district.id, 'country_id': env.ref('base.pe').id})
    supplier = Partner.create({
        'name': 'Aceros del Centro S.A.C.', 'vat': ruc('2062222222'), 'is_company': True, 'street': 'Av. Argentina 2100',
        'l10n_pe_district': district.id, 'country_id': env.ref('base.pe').id})
    carrier = Partner.create({
        'name': 'Transportes Rápidos S.A.C.', 'vat': ruc('2063333333'), 'is_company': True, 'l10n_pe_edi_mtc_number': '1512345CNG',
        'country_id': env.ref('base.pe').id})
    product = env['product.product'].create({
        'name': 'Andamio tubular 2 m', 'type': 'consu', 'is_storable': True, 'weight': 18.0})
    rented = env['product.product'].create({
        'name': 'Andamio multidireccional (alquilado)', 'type': 'consu', 'is_storable': True,
        'weight': 25.0})
    Quant = env['stock.quant']
    Quant._update_available_quantity(product, plant.lot_stock_id, 20.0)
    Quant._update_available_quantity(rented, plant.lot_stock_id, 12.0, owner_id=owner)

    def done(picking, qty):
        picking.action_confirm()
        picking.action_assign()
        picking.move_ids.write({'quantity': qty, 'picked': True})
        picking.button_validate()
        return picking

    def internal(prod, qty, line_owner=False):
        return done(env['stock.picking'].create({
            'picking_type_id': plant.int_type_id.id, 'location_id': plant.lot_stock_id.id,
            'location_dest_id': site.lot_stock_id.id, 'origin': 'Obra Surco',
            'owner_id': line_owner.id if line_owner else False,
            'move_ids': [(0, 0, {'product_id': prod.id, 'product_uom_qty': qty,
                                 'location_id': plant.lot_stock_id.id,
                                 'location_dest_id': site.lot_stock_id.id})],
        }), qty)

    # 1. Traslados de la planta a la obra (motivo 04): 10 andamios propios y,
    # aparte, 8 andamios alquilados (bienes de terceros, con su propietario).
    own_transfer = internal(product, 10.0)
    transfer = internal(rented, 8.0, owner)
    (own_transfer | transfer).write({'l10n_pe_edi_transport_type': '01', 'l10n_pe_edi_operator_id': carrier.id})

    # 2. Compra que la empresa recoge en el local del proveedor (motivo 02).
    supplier_loc = env.ref('stock.stock_location_suppliers')
    purchase = env['stock.picking'].create({
        'picking_type_id': plant.in_type_id.id, 'partner_id': supplier.id,
        'location_id': supplier_loc.id, 'location_dest_id': plant.lot_stock_id.id,
        'origin': 'Factura F001-00004521',
        'move_ids': [(0, 0, {'product_id': product.id, 'product_uom_qty': 15.0,
                             'location_id': supplier_loc.id, 'location_dest_id': plant.lot_stock_id.id})],
    })
    done(purchase, 15.0)
    purchase.write({'l10n_pe_edi_transport_type': '01', 'l10n_pe_edi_operator_id': carrier.id,
                    'l10n_pe_edi_related_document_type': '01', 'l10n_pe_edi_document_number': 'F001-00004521'})

    # 3. Devolución de los 4 andamios alquilados que quedan en la planta (motivo 06).
    customers = env.ref('stock.stock_location_customers')
    back = env['stock.picking'].create({
        'picking_type_id': plant.out_type_id.id, 'partner_id': owner.id, 'owner_id': owner.id,
        'location_id': plant.lot_stock_id.id, 'location_dest_id': customers.id,
        'move_ids': [(0, 0, {'product_id': rented.id, 'product_uom_qty': 4.0,
                             'location_id': plant.lot_stock_id.id, 'location_dest_id': customers.id})],
    })
    done(back, 4.0)
    back.write({'l10n_pe_edi_transport_type': '01', 'l10n_pe_edi_operator_id': carrier.id})

    env.cr.commit()
    for picking in own_transfer | transfer | purchase | back:
        print('Traslado:', picking.id, picking.name, picking.picking_type_code,
              picking.l10n_pe_edi_reason_for_transfer, picking.l10n_pe_edi_guide_allowed,
              picking.l10n_pe_third_party_owner_ids.mapped('name'))
    print('Traslados: almacenes', plant.id, site.id, 'tipo de entrega', plant.out_type_id.id,
          'producto', product.id)
