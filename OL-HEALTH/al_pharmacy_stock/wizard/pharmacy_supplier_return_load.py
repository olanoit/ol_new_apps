# -*- coding: utf-8 -*-
"""Asistente que carga en el canje los lotes por vencer o vencidos del local
que vienen del proveedor."""
from datetime import timedelta

from odoo import Command, api, fields, models
from odoo.fields import Domain


class PharmacySupplierReturnLoad(models.TransientModel):
    _name = 'pharmacy.supplier.return.load'
    _description = 'Cargar lotes en el canje con la droguería'

    return_id = fields.Many2one('pharmacy.supplier.return', required=True, ondelete='cascade')
    include_near_expiry = fields.Boolean(string='Por vencer', default=True)
    days = fields.Integer(string='Vencen en los próximos días',
                          default=lambda self: self.env.company.pharmacy_expiry_alert_days)
    include_expired = fields.Boolean(string='Vencidos', default=True)
    source = fields.Selection([
        ('purchase', 'Lotes recibidos del proveedor'),
        ('seller', 'Productos que vende el proveedor'),
    ], string='Lotes del proveedor', required=True, default='purchase',
        help='Recibidos: lotes que entraron en una recepción del proveedor. Productos: los '
             'productos donde el proveedor figura en la pestaña Compra, sin importar a quién '
             'se compró el lote.')

    def _candidate_quants(self):
        self.ensure_one()
        supplier_return = self.return_id
        now = fields.Datetime.now()
        expiry = Domain.FALSE
        if self.include_expired:
            expiry |= Domain('lot_id.expiration_date', '<', now)
        if self.include_near_expiry:
            expiry |= (Domain('lot_id.expiration_date', '>=', now)
                       & Domain('lot_id.expiration_date', '<=', now + timedelta(days=self.days)))
        return self.env['stock.quant'].search(
            Domain('location_id', 'child_of', supplier_return.warehouse_id.view_location_id.id)
            & Domain('location_id.usage', '=', 'internal')
            & Domain('company_id', '=', supplier_return.company_id.id)
            & Domain('lot_id', '!=', False)
            & Domain('quantity', '>', 0)
            & Domain('product_id.pharmacy_ok', '=', True)
            & expiry)

    def _received_from_supplier(self, lots):
        """Movimientos de recepción hechos de esos lotes desde el proveedor
        (con su costo unitario)."""
        partner = self.return_id.partner_id.commercial_partner_id
        move_lines = self.env['stock.move.line'].search([
            ('lot_id', 'in', lots.ids), ('state', '=', 'done'),
            ('location_id.usage', '=', 'supplier'),
            ('move_id.partner_id.commercial_partner_id', '=', partner.id),
        ]) | self.env['stock.move.line'].search([
            ('lot_id', 'in', lots.ids), ('state', '=', 'done'),
            ('location_id.usage', '=', 'supplier'),
            ('picking_id.partner_id.commercial_partner_id', '=', partner.id),
        ])
        return {move_line.lot_id: move_line.move_id for move_line in move_lines.sorted('id')}

    def action_load(self):
        self.ensure_one()
        supplier_return = self.return_id
        partner = supplier_return.partner_id.commercial_partner_id
        quants = self._candidate_quants()
        received = self._received_from_supplier(quants.lot_id)
        if self.source == 'purchase':
            quants = quants.filtered(lambda q: q.lot_id in received)
        else:
            quants = quants.filtered(
                lambda q: partner in q.product_id.seller_ids.partner_id.commercial_partner_id)
        loaded = {(line.lot_id, line.location_id) for line in supplier_return.line_ids}
        now = fields.Datetime.now()
        commands = []
        for quant in quants:
            if (quant.lot_id, quant.location_id) in loaded:
                continue
            available = quant.quantity - quant.reserved_quantity
            if available <= 0:
                continue
            move = received.get(quant.lot_id)
            commands.append(Command.create({
                'product_id': quant.product_id.id,
                'lot_id': quant.lot_id.id,
                'location_id': quant.location_id.id,
                'quantity': available,
                'reason': 'expired' if quant.lot_id.expiration_date < now else 'near_expiry',
                'price_unit': move.price_unit if move and move.price_unit else
                quant.product_id.standard_price,
            }))
        supplier_return.line_ids = commands
        return {'type': 'ir.actions.act_window_close'}
