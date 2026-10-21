from odoo import _, models

#: Niveles de seguimiento en español: (días respecto al vencimiento, nombre,
#: plantilla de correo, programar actividad).
PE_LEVELS = [
    (-3, 'Recordatorio de vencimiento', 'mail_template_followup_preventive', False),
    (1, 'Aviso de documento vencido', 'mail_template_followup_overdue', False),
    (15, 'Segundo aviso de deuda vencida', 'mail_template_followup_overdue', True),
    (30, 'Aviso de deuda vencida de 30 días', 'mail_template_followup_overdue', True),
    (60, 'Último aviso antes de acciones de cobranza', 'mail_template_followup_last', True),
]


class AccountFollowupLine(models.Model):
    _inherit = 'account_followup.followup.line'

    def _l10n_pe_load_levels(self, company):
        """Agrega los niveles en español que falten (por días); los existentes
        no se tocan."""
        existing = self.search([('company_id', '=', company.id)])
        created = self.browse()
        for delay, name, template, activity in PE_LEVELS:
            if delay in existing.mapped('delay') or name in existing.mapped('name'):
                continue
            created |= self.create({
                'name': name,
                'delay': delay,
                'company_id': company.id,
                'send_email': True,
                'join_invoices': delay > 0,
                'mail_template_id': self.env.ref('al_l10n_pe_collection.%s' % template).id,
                'create_activity': activity,
                'activity_type_id': activity and self.env.ref('mail.mail_activity_data_call').id,
                'activity_summary': activity and _('Llamar al cliente por la deuda vencida'),
                'activity_default_responsible_type': 'followup',
                'auto_execute': not activity,
            })
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': _('Niveles de seguimiento'),
                'message': _('Se agregaron %s niveles.', len(created)) if created
                else _('Ya estaban todos los niveles.'),
                'type': 'success', 'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
