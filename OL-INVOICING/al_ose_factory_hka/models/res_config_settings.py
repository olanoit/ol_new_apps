# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_edi_factory_hka_username = fields.Char(
        related='company_id.l10n_pe_edi_factory_hka_username', readonly=False,
        groups='base.group_system')
    l10n_pe_edi_factory_hka_password = fields.Char(
        related='company_id.l10n_pe_edi_factory_hka_password', readonly=False,
        groups='base.group_system')
    l10n_pe_edi_factory_hka_wsdl_demo = fields.Char(
        related='company_id.l10n_pe_edi_factory_hka_wsdl_demo', readonly=False)
    l10n_pe_edi_factory_hka_wsdl_prod = fields.Char(
        related='company_id.l10n_pe_edi_factory_hka_wsdl_prod', readonly=False)
    l10n_pe_edi_factory_hka_retention = fields.Boolean(
        related='company_id.l10n_pe_edi_factory_hka_retention', readonly=False)
    l10n_pe_edi_factory_hka_reversal = fields.Boolean(
        related='company_id.l10n_pe_edi_factory_hka_reversal', readonly=False)
