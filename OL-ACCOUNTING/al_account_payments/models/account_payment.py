# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    pe_payment_method_id = fields.Many2one(
        comodel_name='pe.catalog.payment', string='Medio pago')
    # Odoo 20: el número de operación es la referencia nativa del pago
    # (payment_reference), la que ven el extracto y la conciliación.
    bank_operation_number = fields.Char(
        string='Número de operación banco', related='payment_reference', readonly=False)
    l10n_pe_future_date = fields.Boolean(
        string='Fecha futura', compute='_compute_l10n_pe_future_date',
        help='La fecha del pago es posterior a hoy: suele ser un error de digitación.')

    @api.depends('date')
    def _compute_l10n_pe_future_date(self):
        today = fields.Date.context_today(self)
        for payment in self:
            payment.l10n_pe_future_date = bool(payment.date and payment.date > today)

    def action_post(self):
        missing = self.filtered(
            lambda p: p.journal_id.l10n_pe_require_operation_number and not p.bank_operation_number)
        if missing:
            raise UserError(self.env._(
                'Indique el número de operación del banco en: %s.',
                ', '.join(missing.mapped(lambda p: p.display_name or p.journal_id.name))))
        res = super().action_post()
        # Aviso, no bloqueo: un pago con fecha futura se publica, pero queda
        # anotado en su historial (suele ser un error de digitación).
        for payment in self.filtered('l10n_pe_future_date'):
            payment.message_post(body=self.env._(
                'Pago publicado con fecha futura (%s).', payment.date.strftime('%d/%m/%Y')))
        return res
