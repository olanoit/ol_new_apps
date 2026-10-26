# -*- coding: utf-8 -*-
"""Preparar valorización en las obras que valorizan por avance de la partida
(requerimiento CREVAL v1.0, CR-01)."""
from odoo import Command, api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _construction_budget_groups(self):
        """Los gastos generales, la utilidad y el descuento no son partidas:
        no se crean como niveles de la obra (CR-12)."""
        return [group for group in super()._construction_budget_groups()
                if group[2].construction_line_role == 'partida']


class ConstructionValuationPrepareWizard(models.TransientModel):
    _inherit = 'construction.valuation.prepare.wizard'

    valuation_basis = fields.Selection(related='project_id.construction_valuation_basis')

    @api.depends('project_id', 'cutoff_date')
    def _compute_preview(self):
        by_progress = self.filtered(
            lambda w: w.project_id.construction_valuation_basis == 'progress' and w.cutoff_date)
        super(ConstructionValuationPrepareWizard, self - by_progress)._compute_preview()
        Valuation = self.env['construction.valuation']
        for wizard in by_progress:
            wizard.currency_id = (wizard.company_id or self.env.company).currency_id
            values = Valuation._get_progress_line_values(wizard.project_id, wizard.cutoff_date)
            wizard.delivery_ids = False
            wizard.line_ids = [Command.clear()] + [Command.create({
                'sale_line_id': vals['sale_line_id'],
                'progress_delivered': vals['progress_delivered'],
                'progress_period': vals['amount_delivered'] / vals['price'] if vals['price']
                else 0.0,
                'amount_delivered': vals['amount_delivered'],
            }) for vals in values if vals['amount_delivered']]
            wizard.amount_delivered = sum(v['amount_delivered'] for v in values)

    def action_create(self):
        self.ensure_one()
        if self.project_id.construction_valuation_basis != 'progress':
            return super().action_create()
        valuation = self.env['construction.valuation']._create_from_progress(
            self.project_id, self.cutoff_date)
        return {
            'type': 'ir.actions.act_window', 'res_model': 'construction.valuation',
            'res_id': valuation.id, 'view_mode': 'form', 'target': 'current',
        }
