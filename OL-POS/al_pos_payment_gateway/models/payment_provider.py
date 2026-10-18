# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.fields import Command


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    al_pos_payment_method_ids = fields.Many2many(
        'pos.payment.method', string='Métodos de pago del TPV', compute='_compute_al_pos_payment_method_ids')

    def _compute_al_pos_payment_method_ids(self):
        Method = self.env['pos.payment.method']
        for provider in self:
            provider.al_pos_payment_method_ids = Method.search([
                ('is_online_payment', '=', True), ('online_payment_provider_ids', 'in', provider.ids)])

    def action_al_pos_payment_method(self):
        """Abre el método de pago del TPV de la pasarela; si no hay, lo crea."""
        self.ensure_one()
        method = self.al_pos_payment_method_ids[:1]
        if not method:
            method = self.env['pos.payment.method'].create({
                'name': self.name,
                'is_online_payment': True,
                'online_payment_provider_ids': [Command.set(self.ids)],
                'company_id': self.company_id.id,
            })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Método de pago del TPV'),
            'res_model': 'pos.payment.method',
            'res_id': method.id,
            'view_mode': 'form',
        }
