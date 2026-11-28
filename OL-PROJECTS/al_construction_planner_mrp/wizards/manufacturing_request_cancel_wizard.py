# -*- coding: utf-8 -*-
"""Cancelar el requerimiento de fabricación (paquete 1.25, M125-04, decisión
del 27-nov-2026): las órdenes que ya pasaron a producción no se cancelan; se
muestran y se pregunta si se cancelan las que siguen en borrador."""
from odoo import api, fields, models


class ConstructionManufacturingRequestCancelWizard(models.TransientModel):
    _name = 'construction.manufacturing.request.cancel.wizard'
    _description = 'Cancelar el requerimiento de fabricación'

    request_id = fields.Many2one(
        'construction.manufacturing.request', string='Requerimiento', required=True,
        readonly=True, ondelete='cascade')
    started_production_ids = fields.Many2many(
        'mrp.production', 'construction_mrp_request_cancel_started_rel', 'wizard_id',
        'production_id', string='Órdenes que ya pasaron a producción',
        compute='_compute_productions')
    draft_production_ids = fields.Many2many(
        'mrp.production', 'construction_mrp_request_cancel_draft_rel', 'wizard_id',
        'production_id', string='Órdenes en borrador', compute='_compute_productions')

    @api.depends('request_id')
    def _compute_productions(self):
        for wizard in self:
            productions = wizard.request_id.production_ids.filtered(
                lambda p: p.state != 'cancel')
            drafts = productions.filtered(lambda p: p.state == 'draft')
            wizard.draft_production_ids = drafts
            wizard.started_production_ids = productions - drafts

    def action_cancel_drafts(self):
        self.ensure_one()
        # Se vuelve a leer el estado de las órdenes al aceptar: pudieron
        # confirmarse mientras el diálogo estaba abierto.
        self.request_id._construction_cancel_drafts()
        return {'type': 'ir.actions.act_window_close'}
