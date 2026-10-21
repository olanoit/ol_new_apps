from odoo import _, api, fields, models

#: Prefijos de la serie: recibo de ingreso (cobros) y comprobante de egreso (pagos).
RECEIPT_PREFIXES = {'inbound': 'RI', 'outbound': 'RE'}


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    l10n_pe_receipt_enabled = fields.Boolean(
        string='Comprobante de pago numerado',
        help='Los pagos confirmados en este diario reciben un número de recibo de '
             'ingreso (cobros) o de comprobante de egreso (pagos) con serie propia.')
    l10n_pe_receipt_in_sequence_id = fields.Many2one(
        'ir.sequence', string='Serie de recibos de ingreso', copy=False, check_company=True)
    l10n_pe_receipt_out_sequence_id = fields.Many2one(
        'ir.sequence', string='Serie de comprobantes de egreso', copy=False, check_company=True)

    @api.model_create_multi
    def create(self, vals_list):
        journals = super().create(vals_list)
        journals.filtered('l10n_pe_receipt_enabled')._l10n_pe_receipt_ensure_sequences()
        return journals

    def write(self, vals):
        res = super().write(vals)
        if vals.get('l10n_pe_receipt_enabled'):
            self._l10n_pe_receipt_ensure_sequences()
        return res

    def _l10n_pe_receipt_ensure_sequences(self):
        """Crea las series que falten: una por sentido y por diario (``RI-<código>-``)."""
        for journal in self:
            for direction, prefix in RECEIPT_PREFIXES.items():
                field = 'l10n_pe_receipt_%s_sequence_id' % ('in' if direction == 'inbound' else 'out')
                if journal[field]:
                    continue
                label = _('Recibos de ingreso') if direction == 'inbound' else _('Comprobantes de egreso')
                # sudo: ir.sequence es de administración; la serie es del diario.
                sequence_sudo = self.env['ir.sequence'].sudo().create({
                    'name': '%s - %s' % (label, journal.name),
                    'implementation': 'no_gap',
                    'prefix': '%s-%s-' % (prefix, journal.code),
                    'padding': 6,
                    'company_id': journal.company_id.id,
                })
                journal[field] = sequence_sudo.id
