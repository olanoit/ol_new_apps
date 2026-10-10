# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_lease_id = fields.Many2one('l10n_pe.lease', string='Arrendamiento', copy=False, readonly=True,
                                       index='btree_not_null', check_company=True)
    l10n_pe_lease_period = fields.Integer(string='Cuota del arrendamiento', copy=False, readonly=True)
