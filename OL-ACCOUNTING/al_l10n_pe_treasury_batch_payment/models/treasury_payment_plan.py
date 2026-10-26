# -*- coding: utf-8 -*-
from odoo import fields, models


class L10nPeTreasuryPaymentPlan(models.Model):
    _inherit = 'l10n_pe.treasury.payment.plan'

    batch_payment_id = fields.Many2one('account.batch.payment', string='Lote bancario', readonly=True, copy=False,
                                       check_company=True)

    def _l10n_pe_after_pay(self, payments):
        # Con un método de pago por lotes (p. ej. el TXT del banco), los pagos de
        # la programación forman un lote listo para generar el archivo.
        payments = super()._l10n_pe_after_pay(payments)
        method = self.payment_method_line_id.payment_method_id
        if payments and method and method._get_payment_method_information().get(method.code, {}).get('mode') == 'multi':
            batch = self.env['account.batch.payment'].create({
                'journal_id': self.journal_id.id,
                'payment_ids': [fields.Command.set(payments.ids)],
                'payment_method_id': method.id,
                'batch_type': 'outbound',
            })
            self.batch_payment_id = batch
            self.message_post(body=self.env._('Lote bancario: %s.', batch._get_html_link()))
        return payments

    def action_open_batch_payment(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.batch.payment',
            'res_id': self.batch_payment_id.id,
            'view_mode': 'form',
        }
