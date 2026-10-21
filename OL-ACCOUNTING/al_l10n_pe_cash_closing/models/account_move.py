from odoo import _, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_cash_closing_id = fields.Many2one(
        'l10n_pe.cash.closing', string='Cierre de caja', readonly=True, copy=False, index='btree_not_null',
        check_company=True, help='Cierre de caja cuyo faltante o sobrante registra este asiento.')

    def _l10n_pe_check_cash_closed(self):
        """Una caja cerrada no admite asientos nuevos ni cambios hasta la fecha de
        su último cierre: el saldo arqueado ya no coincidiría con los libros."""
        cash_moves = self.filtered(lambda m: m.journal_id.type == 'cash')
        if not cash_moves:
            return
        # sudo: el bloqueo vale también para quien no puede leer los cierres.
        closings_sudo = self.env['l10n_pe.cash.closing'].sudo().search([
            ('journal_id', 'in', cash_moves.journal_id.ids), ('state', '=', 'closed'),
            ('date', '>=', min(cash_moves.mapped('date'))),
        ])
        for move in cash_moves:
            closing = closings_sudo.filtered(lambda c: c.journal_id == move.journal_id and c.date >= move.date)[:1]
            if closing:
                raise UserError(_(
                    'La caja %(journal)s está cerrada hasta el %(date)s (%(closing)s): no se pueden '
                    'registrar ni modificar movimientos de esa fecha o anteriores.',
                    journal=move.journal_id.display_name, date=closing.date.strftime('%d/%m/%Y'),
                    closing=closing.name))

    def _post(self, soft=True):
        self._l10n_pe_check_cash_closed()
        return super()._post(soft=soft)

    def button_draft(self):
        self._l10n_pe_check_cash_closed()
        return super().button_draft()
