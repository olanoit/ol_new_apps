# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    construction_settlement_ids = fields.One2many(
        'construction.contract.settlement', 'invoice_id', string='Liquidaciones de contrata')

    def _compute_payment_state(self):
        super()._compute_payment_state()
        # La liquidación pasa a «Pagada» cuando su factura queda pagada. La
        # escribe el sistema: quien concilia el pago (tesorería) no tiene por
        # qué tener acceso al planificador.
        settlements_sudo = self.sudo().construction_settlement_ids.filtered(
            lambda s: s.state in ('approved', 'paid'))
        if settlements_sudo:
            settlements_sudo._sync_paid()
