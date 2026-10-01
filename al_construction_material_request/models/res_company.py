# -*- coding: utf-8 -*-
from odoo import _, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_src_location_id = fields.Many2one(
        'stock.location', string='Origen de los despachos a obra',
        domain="[('usage', '=', 'internal'), ('company_id', 'in', [id, False])]",
        help='Existencias del almacén central. La disponibilidad incluye sus '
             'sububicaciones por familia (child_of).')
    construction_sites_location_id = fields.Many2one(
        'stock.location', string='Ubicación padre de las obras',
        domain="[('company_id', 'in', [id, False])]",
        help='Rama OBRAS: cada obra tiene una sububicación debajo.')
    construction_dispatch_type_id = fields.Many2one(
        'stock.picking.type', string='Tipo de operación del despacho a obra',
        domain="[('code', '=', 'internal'), ('company_id', '=', id)]")
    construction_pr_picking_type_id = fields.Many2one(
        'stock.picking.type', string='Recepción de los requerimientos de compra',
        domain="[('code', '=', 'incoming'), ('company_id', '=', id)]")

    def _al_construction_ensure_setup(self):
        """Completa, sin pisar lo configurado, la ubicación ``OBRAS``, el tipo
        «Despacho a obra» y los valores por defecto a partir del primer
        almacén de la compañía."""
        Location = self.env['stock.location']
        PickingType = self.env['stock.picking.type']
        for company in self:
            warehouse = self.env['stock.warehouse'].search(
                [('company_id', '=', company.id)], limit=1)
            if not warehouse:
                continue
            vals = {}
            if not company.construction_src_location_id:
                vals['construction_src_location_id'] = warehouse.lot_stock_id.id
            sites = company.construction_sites_location_id
            if not sites:
                sites = Location.search([
                    ('location_id', '=', warehouse.view_location_id.id),
                    ('name', '=', 'OBRAS'),
                    ('company_id', '=', company.id),
                ], limit=1) or Location.create({
                    # Interna (no «vista») para que se lea ALM/OBRAS/<obra>.
                    'name': 'OBRAS',
                    'usage': 'internal',
                    'location_id': warehouse.view_location_id.id,
                    'company_id': company.id,
                })
                vals['construction_sites_location_id'] = sites.id
            if not company.construction_dispatch_type_id:
                vals['construction_dispatch_type_id'] = PickingType.create({
                    'name': _('Despacho a obra'),
                    'code': 'internal',
                    'sequence_code': 'OBRA',
                    'warehouse_id': warehouse.id,
                    'company_id': company.id,
                    'default_location_src_id': (
                        vals.get('construction_src_location_id')
                        or company.construction_src_location_id.id),
                    'default_location_dest_id': sites.id,
                }).id
            if not company.construction_pr_picking_type_id:
                vals['construction_pr_picking_type_id'] = warehouse.in_type_id.id
            if vals:
                company.write(vals)
