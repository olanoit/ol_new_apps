from odoo import _, fields, models
from odoo.exceptions import UserError


class L10nPeCollectionStatementSend(models.TransientModel):
    """Envía el estado de cuenta en PDF a uno o varios clientes."""
    _name = 'l10n_pe.collection.statement.send'
    _description = 'Enviar estado de cuenta'

    partner_ids = fields.Many2many('res.partner', string='Clientes', required=True)
    template_id = fields.Many2one(
        'mail.template', string='Plantilla', required=True,
        domain="[('model', '=', 'res.partner')]",
        default=lambda self: self.env.ref('al_l10n_pe_collection.mail_template_statement', raise_if_not_found=False))
    without_email = fields.Char(string='Sin correo', compute='_compute_without_email')

    def _compute_without_email(self):
        for wizard in self:
            names = wizard.partner_ids.filtered(lambda p: not p.email).mapped('name')
            wizard.without_email = ', '.join(names)

    def action_send(self):
        partners = self.partner_ids.filtered('email')
        if not partners:
            raise UserError(_('Ninguno de los clientes tiene correo.'))
        for partner in partners:
            self.template_id.send_mail(partner.id)
            partner.message_post(body=_('Estado de cuenta enviado a %s.', partner.email))
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'title': _('Estado de cuenta'), 'type': 'success', 'sticky': False,
                       'message': _('Enviado a %s clientes.', len(partners)),
                       'next': {'type': 'ir.actions.act_window_close'}},
        }
