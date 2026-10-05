# -*- coding: utf-8 -*-
from odoo import api, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    @api.model
    def default_get(self, fields):
        """Con la detracción separada, el pago al tercero no la incluye.

        La factura tiene dos líneas de plazo con el mismo vencimiento y
        Odoo 19 las trata como cuotas: si vencen, el asistente propone
        pagar ambas y la detracción acabaría en la cuenta del proveedor (o
        cobrada al cliente) en vez de en el Banco de la Nación. Se quitan
        de la propuesta; la detracción se registra con «Registrar depósito»
        (que abre este asistente sobre la línea de detracción). Si solo
        queda la detracción por pagar, se deja.
        """
        res = super().default_get(fields)
        if (self.env.context.get('active_model') != 'account.move'
                or not res.get('line_ids')):
            return res
        line_ids = res['line_ids'][0][2]
        lines = self.env['account.move.line'].browse(line_ids)
        companies = lines.company_id
        det_accounts = (companies.l10n_pe_detraction_receivable_account_id
                        | companies.l10n_pe_detraction_payable_account_id)
        det_lines = lines.filtered(lambda l: l.account_id in det_accounts)
        if det_lines and lines - det_lines:
            res['line_ids'] = [(6, 0, (lines - det_lines).ids)]
        return res
