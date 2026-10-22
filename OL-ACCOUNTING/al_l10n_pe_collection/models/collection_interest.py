from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_collection_interest_line_id = fields.Many2one(
        'account.move.line', string='Cuota que genera los intereses', readonly=True, copy=False, index='btree_not_null',
        help='Nota de débito por intereses moratorios de esta cuota.')
    l10n_pe_collection_interest_to = fields.Date(
        string='Intereses hasta', readonly=True, copy=False,
        help='Fecha hasta la que la nota de débito liquida intereses moratorios.')


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    l10n_pe_collection_interest_date = fields.Date(
        string='Intereses facturados hasta', compute='_compute_l10n_pe_collection_interest_date',
        help='Fecha hasta la que ya se emitieron notas de débito por intereses moratorios de esta '
             'cuota (en borrador o publicadas).')

    def _compute_l10n_pe_collection_interest_date(self):
        groups = self.env['account.move']._read_group(
            [('l10n_pe_collection_interest_line_id', 'in', self.ids), ('state', '!=', 'cancel')],
            ['l10n_pe_collection_interest_line_id'], ['l10n_pe_collection_interest_to:max'])
        dates = {line.id: date for line, date in groups}
        for line in self:
            line.l10n_pe_collection_interest_date = dates.get(line.id, False)
