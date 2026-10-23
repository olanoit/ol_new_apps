# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_retention_account_id = fields.Many2one(
        related='company_id.construction_retention_account_id', readonly=False)
    construction_discount_account_id = fields.Many2one(
        related='company_id.construction_discount_account_id', readonly=False)
    # Contratas con condiciones (CREVAL v1.0, 3.4 a 3.7).
    construction_default_condition_id = fields.Many2one(
        related='company_id.construction_default_condition_id', readonly=False)
    construction_advance_product_id = fields.Many2one(
        related='company_id.construction_advance_product_id', readonly=False)
    construction_deduction_account_id = fields.Many2one(
        related='company_id.construction_deduction_account_id', readonly=False)
    construction_deduction_journal_id = fields.Many2one(
        related='company_id.construction_deduction_journal_id', readonly=False)
    # Aprobación por niveles de la orden de contrata (3.4): el módulo de OCA;
    # sin reglas, rige la aprobación nativa de Compras.
    module_purchase_tier_validation = fields.Boolean(
        string='Aprobación por niveles de la orden de contrata')
