from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    l10n_pe_check_layout_id = fields.Many2one(
        'l10n_pe.check.layout', string='Formato de cheque', check_company=True,
        help='Formato de la chequera de este banco para imprimir los cheques propios.')
