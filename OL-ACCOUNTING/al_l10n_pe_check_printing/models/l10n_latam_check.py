from odoo import _, fields, models
from odoo.exceptions import UserError


class L10nLatamCheck(models.Model):
    _inherit = 'l10n_latam.check'

    def _l10n_pe_check_layout(self):
        """Formato de cheque del diario de los cheques propios elegidos (uno solo)."""
        if any(check.payment_method_code != 'own_checks' for check in self):
            raise UserError(_('Solo se imprimen cheques propios (girados por la compañía).'))
        layouts = self.original_journal_id.l10n_pe_check_layout_id
        if not layouts:
            raise UserError(_('Elija el formato de cheque del diario %s (pestaña Configuración avanzada).',
                              ', '.join(self.original_journal_id.mapped('display_name'))))
        if len(layouts) > 1:
            raise UserError(_('Imprima juntos solo cheques del mismo formato.'))
        return layouts

    def _l10n_pe_print_values(self):
        self.ensure_one()
        layout = self.original_journal_id.l10n_pe_check_layout_id
        payment = self.payment_id
        return layout._l10n_pe_print_values(
            payment.date, self.payment_date, payment.partner_id.name, self.amount, self.currency_id)

    def action_l10n_pe_print_check(self):
        self._l10n_pe_check_layout()
        # Sin el asistente de diseño de documentos: el cheque no usa encabezado.
        return self.env.ref('al_l10n_pe_check_printing.action_report_check').report_action(self, config=False)


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def action_l10n_pe_print_checks(self):
        checks = self.l10n_latam_new_check_ids.filtered(lambda c: c.payment_method_code == 'own_checks')
        if not checks:
            raise UserError(_('El pago no tiene cheques propios.'))
        return checks.action_l10n_pe_print_check()


class ReportCheck(models.AbstractModel):
    _name = 'report.al_l10n_pe_check_printing.report_check'
    _description = 'Cheque impreso'

    def _get_report_values(self, docids, data=None):
        data = data or {}
        test_layout_id = data.get('l10n_pe_test_layout_id')
        if test_layout_id:
            layout = self.env['l10n_pe.check.layout'].browse(test_layout_id)
            currency = layout.company_id.currency_id or self.env.company.currency_id
            items = [layout._l10n_pe_print_values(
                fields.Date.context_today(self), False, _('BENEFICIARIO DE PRUEBA S.A.C.'), 12345.67, currency)]
        else:
            checks = self.env['l10n_latam.check'].browse(docids)
            checks._l10n_pe_check_layout()
            items = [check._l10n_pe_print_values() for check in checks]
        return {'doc_ids': docids, 'items': items}
