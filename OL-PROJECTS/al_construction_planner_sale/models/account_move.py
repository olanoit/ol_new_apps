# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    construction_valuation_id = fields.Many2one(
        'construction.valuation', string='Valorización de obra', readonly=True, copy=False,
        index='btree_not_null', check_company=True,
        help='La valorización confirmada por el cliente de la que nace la factura.')

    def _post(self, soft=True):
        # Control de la valorización (gancho de la fase 7, §6.4): la factura
        # no puede superar lo confirmado por el cliente en cada partida.
        # sudo: lo publica contabilidad, que puede no ver el planificador.
        valuations_sudo = self.sudo().construction_valuation_id
        for valuation_sudo in valuations_sudo:
            valuation_sudo._construction_check_invoice_balance()
        posted = super()._post(soft=soft)
        posted.sudo().construction_valuation_id._construction_sync_invoiced()
        return posted

    def button_draft(self):
        res = super().button_draft()
        # sudo: la valorización vuelve a «Confirmada» aunque quien reabre la
        # factura no vea el planificador.
        self.sudo().construction_valuation_id._construction_sync_invoiced()
        return res

    def button_cancel(self):
        res = super().button_cancel()
        # sudo: ídem al anular la factura.
        self.sudo().construction_valuation_id._construction_sync_invoiced()
        return res
