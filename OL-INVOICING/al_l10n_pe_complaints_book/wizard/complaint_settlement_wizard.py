from odoo import _, fields, models
from odoo.exceptions import UserError


class L10nPeComplaintSettlementWizard(models.TransientModel):
    """Oferta de solución (Reglamento, art. 6-A, D.S. 101-2022-PCM)."""
    _name = 'l10n_pe.complaint.settlement.wizard'
    _description = 'Oferta de solución de un reclamo'

    complaint_id = fields.Many2one('l10n_pe.complaint', string='Hoja', required=True)
    mode = fields.Selection(
        selection=[('remote', 'A distancia'), ('in_person', 'Presencial')],
        string='Modalidad', required=True, default='remote',
        help='A distancia: el plazo se suspende hasta 5 días hábiles mientras el consumidor '
             'decide. Presencial: se anota en la hoja y el consumidor la acepta firmando.')
    offer = fields.Text(string='Oferta de solución', required=True)
    accepted = fields.Boolean(
        string='El consumidor la aceptó y firmó «ACUERDO ACEPTADO PARA SOLUCIONAR EL RECLAMO»')

    def action_confirm(self):
        self.ensure_one()
        if not (self.offer or '').strip():
            raise UserError(_('Describa la oferta de solución.'))
        self.complaint_id._register_settlement_offer(self.offer, self.mode, self.accepted)
        return {'type': 'ir.actions.act_window_close'}
