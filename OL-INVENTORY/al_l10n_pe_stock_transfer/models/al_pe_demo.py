# -*- coding: utf-8 -*-
from odoo import Command, api, models


class AlPeDemo(models.AbstractModel):
    _inherit = 'al.pe.demo'

    @api.model
    def _load_demo_stock_transfer(self):
        """Dos almacenes con su establecimiento anexo (planta 0001 y obra
        0002), andamios propios y alquilados a un tercero, y cuatro
        transferencias hechas: dos traslados de la planta a la obra (motivo
        04, propios y de terceros), una compra recogida en el local del
        proveedor (motivo 02) y la devolución al propietario (motivo 06)."""
        company = self._demo_company()
        if not company or self._demo_ref('al_l10n_pe_stock_transfer.demo_picking_return'):
            return
        env = self._demo_env(company)
        # Consignación: el campo «Propietario» en recepciones y transferencias.
        env.ref('base.group_user').implied_ids |= env.ref('stock.group_tracking_owner')
        district = company.partner_id.l10n_pe_district or env.ref('l10n_pe.district_pe_150101')
        pe = env.ref('base.pe')
        address = {'l10n_pe_district': district.id, 'country_id': pe.id}
        Partner = env['res.partner']
        addr_plant = self._demo_record('al_l10n_pe_stock_transfer.demo_address_plant', Partner, dict(
            address, name='DEMO TRAS Planta Ate', parent_id=company.partner_id.id, type='other',
            street='Av. Nicolás Ayllón 4200', l10n_pe_annex_code='0001'))
        addr_site = self._demo_record('al_l10n_pe_stock_transfer.demo_address_site', Partner, dict(
            address, name='DEMO TRAS Obra Surco', parent_id=company.partner_id.id, type='other',
            street='Av. Primavera 1550', l10n_pe_annex_code='0002'))
        Warehouse = env['stock.warehouse']
        plant = self._demo_record('al_l10n_pe_stock_transfer.demo_warehouse_plant', Warehouse, {
            'name': 'DEMO TRAS Planta Ate', 'code': 'DTP', 'partner_id': addr_plant.id, 'company_id': company.id})
        site = self._demo_record('al_l10n_pe_stock_transfer.demo_warehouse_site', Warehouse, {
            'name': 'DEMO TRAS Obra Surco', 'code': 'DTO', 'partner_id': addr_site.id, 'company_id': company.id})
        owner = self._demo_partner(env, 'al_l10n_pe_stock_transfer.demo_owner', 'DEMO TRAS Alquiler de Equipos S.A.C.',
                                   self._demo_ruc('2061111111'), street='Jr. Los Andamios 300', **address)
        supplier = self._demo_partner(env, 'al_l10n_pe_stock_transfer.demo_supplier',
                                      'DEMO TRAS Aceros del Centro S.A.C.', self._demo_ruc('2062222222'),
                                      street='Av. Argentina 2100', **address)
        carrier = self._demo_partner(env, 'al_l10n_pe_stock_transfer.demo_carrier',
                                     'DEMO TRAS Transportes Rápidos S.A.C.', self._demo_ruc('2063333333'),
                                     l10n_pe_edi_mtc_number='1512345CNG')
        Product = env['product.product']
        product = self._demo_record('al_l10n_pe_stock_transfer.demo_product_own', Product, {
            'name': 'DEMO TRAS Andamio tubular 2 m', 'type': 'consu', 'is_storable': True, 'weight': 18.0})
        rented = self._demo_record('al_l10n_pe_stock_transfer.demo_product_rented', Product, {
            'name': 'DEMO TRAS Andamio multidireccional (alquilado)', 'type': 'consu', 'is_storable': True,
            'weight': 25.0})
        Quant = env['stock.quant']
        Quant._update_available_quantity(product, plant.lot_stock_id, 20.0)
        Quant._update_available_quantity(rented, plant.lot_stock_id, 12.0, owner_id=owner)
        transport = {'l10n_pe_edi_transport_type': '01', 'l10n_pe_edi_operator_id': carrier.id}

        def done(key, picking_type, source, destination, prod, qty, **vals):
            picking = self._demo_record('al_l10n_pe_stock_transfer.demo_picking_%s' % key, env['stock.picking'], dict({
                'picking_type_id': picking_type.id, 'location_id': source.id, 'location_dest_id': destination.id,
                'move_ids': [Command.create({'product_id': prod.id, 'product_uom_qty': qty,
                                             'location_id': source.id, 'location_dest_id': destination.id})],
            }, **vals))
            picking.action_confirm()
            picking.action_assign()
            picking.move_ids.write({'quantity': qty, 'picked': True})
            picking.button_validate()
            picking.write(transport)
            return picking

        done('own', plant.int_type_id, plant.lot_stock_id, site.lot_stock_id, product, 10.0,
             origin='DEMO TRAS Obra Surco')
        done('rented', plant.int_type_id, plant.lot_stock_id, site.lot_stock_id, rented, 8.0,
             origin='DEMO TRAS Obra Surco', owner_id=owner.id)
        done('purchase', plant.in_type_id, env.ref('stock.stock_location_suppliers'), plant.lot_stock_id, product,
             15.0, partner_id=supplier.id, origin='Factura F001-00004521').write({
                 'l10n_pe_edi_related_document_type': '01', 'l10n_pe_edi_document_number': 'F001-00004521'})
        done('return', plant.out_type_id, plant.lot_stock_id, env.ref('stock.stock_location_customers'), rented, 4.0,
             partner_id=owner.id, owner_id=owner.id)
