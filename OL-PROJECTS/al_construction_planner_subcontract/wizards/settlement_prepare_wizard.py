# -*- coding: utf-8 -*-
"""Preparar las valorizaciones de una obra al corte (CREVAL v1.0, 3.5)."""
from odoo import fields, models


class ConstructionSettlementPrepareWizard(models.TransientModel):
    _name = 'construction.settlement.prepare.wizard'
    _description = 'Preparar valorizaciones de contrata'

    project_id = fields.Many2one(
        'project.project', string='Obra', domain=[('is_construction_site', '=', True)],
        help='Vacía: todas las obras.')
    date = fields.Date(string='Corte hasta', required=True, default=fields.Date.context_today)

    def action_prepare(self):
        self.ensure_one()
        return self.env['construction.contract.settlement'].action_prepare_project_settlements(
            project_id=self.project_id.id or None, date=self.date)
