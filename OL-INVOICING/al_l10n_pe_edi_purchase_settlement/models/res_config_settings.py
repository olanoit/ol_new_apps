# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_lce_igv_tax_id = fields.Many2one(
        related='company_id.l10n_pe_lce_igv_tax_id', readonly=False)
    l10n_pe_lce_ir_tax_id = fields.Many2one(
        related='company_id.l10n_pe_lce_ir_tax_id', readonly=False)
    l10n_pe_lce_ir_gold_tax_id = fields.Many2one(
        related='company_id.l10n_pe_lce_ir_gold_tax_id', readonly=False)
    l10n_pe_lce_ir_min_amount = fields.Float(
        related='company_id.l10n_pe_lce_ir_min_amount', readonly=False)
    l10n_pe_lce_uit_amount = fields.Float(
        related='company_id.l10n_pe_lce_uit_amount', readonly=False)
    l10n_pe_lce_send_on_post = fields.Boolean(
        related='company_id.l10n_pe_lce_send_on_post', readonly=False)
