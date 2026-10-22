from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_pe_bank_collection_code = fields.Char(
        string='Código de recaudación', copy=False, index='btree_not_null',
        help='Código con el que el cliente paga en el banco, si el convenio no usa su RUC o DNI.')

    _l10n_pe_bank_collection_code_uniq = models.Constraint(
        'unique(l10n_pe_bank_collection_code)', 'Ese código de recaudación ya lo tiene otro cliente.')
