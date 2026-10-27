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
    construction_damaged_location_name = fields.Char(
        related='company_id.construction_damaged_location_name', readonly=False)
    construction_code_from_name = fields.Boolean(
        related='company_id.construction_code_from_name', readonly=False)
    construction_pr_picking_type_id = fields.Many2one(
        related='company_id.construction_pr_picking_type_id', readonly=False)
    construction_stock_purchase_analytic = fields.Boolean(
        related='company_id.construction_stock_purchase_analytic', readonly=False)
    construction_area_plan_id = fields.Many2one(
        related='company_id.construction_area_plan_id', readonly=False)
    # Paquete 1.11, M111-19 B y C, M111-20 A.
    construction_slip_dispatch_label = fields.Char(
        related='company_id.construction_slip_dispatch_label', readonly=False)
    construction_slip_receive_site_label = fields.Char(
        related='company_id.construction_slip_receive_site_label', readonly=False)
    construction_slip_receive_internal_label = fields.Char(
        related='company_id.construction_slip_receive_internal_label', readonly=False)
    construction_slip_unvalidated_signer = fields.Selection(
        related='company_id.construction_slip_unvalidated_signer', readonly=False)
    construction_slip_show_previous = fields.Boolean(
        related='company_id.construction_slip_show_previous', readonly=False)
    construction_internal_fallback_group_id = fields.Many2one(
        related='company_id.construction_internal_fallback_group_id', readonly=False)
    construction_site_request_without_rule = fields.Selection(
        related='company_id.construction_site_request_without_rule', readonly=False)
    group_construction_internal_request_all = fields.Boolean(
        string='Todos los usuarios pueden hacer requerimientos internos',
        implied_group='al_construction_material_request.group_construction_internal_requester')

    def action_al_construction_setup(self):
        self.company_id._al_construction_ensure_setup()
        self.company_id._al_construction_default_area_plan()
        # Consumo interno en cada almacén de la compañía (M111-10).
        self.env['stock.warehouse'].search(
            [('company_id', '=', self.company_id.id)])._construction_ensure_internal_consumption()
