# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_pe_is_company_partner = fields.Boolean(
        string='Es una compañía propia', compute='_compute_l10n_pe_is_company_partner',
        search='_search_l10n_pe_is_company_partner',
        help='El contacto es el de una compañía de la base: sus bienes no son de terceros.')

    def _l10n_pe_company_partner_ids(self):
        # sudo(): solo se leen los contactos de las compañías, para separar los
        # bienes propios de los de terceros aunque el usuario no vea todas.
        companies_sudo = self.env['res.company'].sudo().search([])
        return set(companies_sudo.partner_id.ids)

    def _compute_l10n_pe_is_company_partner(self):
        own = self._l10n_pe_company_partner_ids()
        for partner in self:
            partner.l10n_pe_is_company_partner = partner.id in own

    def _search_l10n_pe_is_company_partner(self, operator, value):
        if operator not in ('=', '!='):
            return NotImplemented
        positive = (operator == '=') == bool(value)
        return [('id', 'in' if positive else 'not in', list(self._l10n_pe_company_partner_ids()))]
