# -*- coding: utf-8 -*-
"""«Cerrar con lo recibido» (paquete 1.17, M117-11)."""
from odoo import fields, models


class ConstructionRequestCloseWizard(models.TransientModel):
    _name = 'construction.request.close.wizard'
    _description = 'Cerrar el requerimiento con lo recibido'

    request_id = fields.Many2one('construction.material.request', required=True, ondelete='cascade')
    line_ids = fields.One2many('construction.request.close.wizard.line', 'wizard_id',
                               string='Líneas')

    def action_confirm(self):
        self.ensure_one()
        self.line_ids.filtered('selected').line_id._construction_close_with_received()
        self.request_id.activity_ids.filtered(
            lambda a: a.summary == self.env._('Devolución desde la obra: cierre con lo recibido')
        ).action_done()
        return {'type': 'ir.actions.act_window_close'}


class ConstructionRequestCloseWizardLine(models.TransientModel):
    _name = 'construction.request.close.wizard.line'
    _description = 'Línea para cerrar con lo recibido'

    wizard_id = fields.Many2one('construction.request.close.wizard', required=True,
                                ondelete='cascade')
    line_id = fields.Many2one('construction.material.request.line', string='Línea', required=True,
                              ondelete='cascade')
    selected = fields.Boolean(string='Cerrar', default=True)
    product_id = fields.Many2one(related='line_id.product_id', string='Material')
    product_uom_id = fields.Many2one(related='line_id.product_uom_id', string='Unidad')
    qty_ordered = fields.Float(related='line_id.product_qty', string='Pedido')
    qty_received = fields.Float(related='line_id.qty_received_on_site', string='Recibido neto')
    qty_difference = fields.Float(string='Diferencia', compute='_compute_qty_difference',
                                  digits='Product Unit')

    def _compute_qty_difference(self):
        for line in self:
            line.qty_difference = line.qty_ordered - line.qty_received
