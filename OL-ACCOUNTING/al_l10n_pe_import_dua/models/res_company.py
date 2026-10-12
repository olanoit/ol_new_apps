# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_dua_partner_id = fields.Many2one(
        'res.partner', string='Aduana',
        help='Contacto a nombre del que se registran las DUA (SUNAT, R.U.C. 20131312955).')
    l10n_pe_dua_journal_id = fields.Many2one(
        'account.journal', string='Diario de las DUA', domain="[('type', '=', 'purchase')]",
        check_company=True)
    l10n_pe_dua_offset_account_id = fields.Many2one(
        'account.account', string='Cuenta puente del valor en aduana', check_company=True,
        help='La base imponible del IGV y su compensación van a esta cuenta y se anulan: la '
             'DUA suma solo los derechos y el IGV que se pagan a la Aduana.')
