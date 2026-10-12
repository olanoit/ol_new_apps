# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_pe_fourth_category_suspension_ids = fields.One2many(
        'l10n_pe.fourth.category.suspension', 'partner_id',
        string='Suspensiones de retención de 4.ª')
    l10n_pe_fourth_category_suspended = fields.Boolean(
        string='Retención de 4.ª suspendida', compute='_compute_fourth_category_suspended',
        help='Tiene una constancia de suspensión vigente hoy en la compañía activa.')

    @api.depends_context('company')
    @api.depends('l10n_pe_fourth_category_suspension_ids.date_from',
                 'l10n_pe_fourth_category_suspension_ids.date_to',
                 'l10n_pe_fourth_category_suspension_ids.active')
    def _compute_fourth_category_suspended(self):
        Suspension = self.env['l10n_pe.fourth.category.suspension']
        today = fields.Date.context_today(self)
        for partner in self:
            partner.l10n_pe_fourth_category_suspended = bool(
                Suspension._l10n_pe_find(partner, today, self.env.company))
