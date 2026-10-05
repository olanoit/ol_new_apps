# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_src_location_id = fields.Many2one(
        related='company_id.construction_src_location_id', readonly=False)
    construction_sites_location_id = fields.Many2one(
        related='company_id.construction_sites_location_id', readonly=False)
    construction_dispatch_type_id = fields.Many2one(
        related='company_id.construction_dispatch_type_id', readonly=False)
    construction_pr_picking_type_id = fields.Many2one(
        related='company_id.construction_pr_picking_type_id', readonly=False)

    def action_al_construction_setup(self):
        self.company_id._al_construction_ensure_setup()
