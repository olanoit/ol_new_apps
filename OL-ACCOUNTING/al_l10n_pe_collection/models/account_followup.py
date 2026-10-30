from odoo import _, models

#: Niveles de seguimiento en español: (días respecto al vencimiento, nombre,
#: plantilla de correo, programar actividad). En Odoo 20 el nivel no tiene
#: nombre propio (se muestra por sus días); el nombre queda como referencia.
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
            if delay in existing.mapped('delay'):
                continue
            created |= self.create({
                'delay': delay,
                'company_id': company.id,
                'send_email': True,
                'mail_template_id': self.env.ref('al_l10n_pe_collection.%s' % template).id,
                'create_activity': activity,
                'activity_type_id': activity and self.env.ref('mail.mail_activity_data_call').id,
                'activity_summary': activity and _('Llamar al cliente por la deuda vencida'),
                'activity_default_responsible_type': 'followup',
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


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _execute_followup_partner(self, options=None):
        """No envía a un consumidor los niveles previos al vencimiento sin su
        consentimiento (Indecopi sancionó en 2025 los recordatorios antes del
        vencimiento). El seguimiento manual queda a criterio del usuario."""
        if not (options or {}).get('manual_followup') and self._l10n_pe_collection_skip_preventive():
            return False
        return super()._execute_followup_partner(options=options)

    def _l10n_pe_collection_skip_preventive(self):
        self.ensure_one()
        # Odoo 20: el nivel que toca enviar lo da _query_followup_data.
        line_id = (self._query_followup_data().get(self.id) or {}).get('followup_line_id')
        followup_line = self.env['account_followup.followup.line'].browse(line_id)
        return bool(followup_line.delay < 0
                    and self.env.company.root_id.l10n_pe_collection_consumer_guard
                    and self._l10n_pe_collection_is_consumer()
                    and not self.commercial_partner_id.l10n_pe_collection_reminder_consent)
