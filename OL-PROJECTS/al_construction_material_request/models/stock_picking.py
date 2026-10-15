# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # Se copia: las entregas parciales (backorders) siguen vinculadas.
    construction_request_id = fields.Many2one(
        'construction.material.request', string='Requerimiento de obra',
        index='btree_not_null', readonly=True)

    def _sanity_check(self):
        """El despacho a obra de un requerimiento lo valida el almacén
        (Logística), no quien lo pidió (v1.6, M16-10)."""
        dispatches = self.filtered(
            lambda p: p.construction_request_id
            and p.picking_type_id == p.company_id.construction_dispatch_type_id)
        if dispatches and not self.env.su and not self.env.user.has_group(
                'al_construction_material_request.group_construction_logistics'):
            raise UserError(_(
                'El despacho a obra %s lo valida el almacén (grupo Logística de '
                'requerimientos de obra).', ', '.join(dispatches.mapped('name'))))
        return super()._sanity_check()
