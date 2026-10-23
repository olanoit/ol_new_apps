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
    construction_code_from_name = fields.Boolean(
        related='company_id.construction_code_from_name', readonly=False)
    construction_pr_picking_type_id = fields.Many2one(
        related='company_id.construction_pr_picking_type_id', readonly=False)
    construction_area_plan_id = fields.Many2one(
        related='company_id.construction_area_plan_id', readonly=False)

    def action_al_construction_setup(self):
        self.company_id._al_construction_ensure_setup()
        self.company_id._al_construction_default_area_plan()
        # Consumo interno en cada almacén de la compañía (M111-10).
        self.env['stock.warehouse'].search(
            [('company_id', '=', self.company_id.id)])._construction_ensure_internal_consumption()
