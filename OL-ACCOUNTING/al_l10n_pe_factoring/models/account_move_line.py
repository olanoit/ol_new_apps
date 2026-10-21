# -*- coding: utf-8 -*-
from odoo import models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _l10n_pe_payment_block_reason(self):
        """Una factura cedida con recurso sigue abierta, pero la cobra el factor:
        si el cliente le pagó a la empresa se registra desde la operación de
        factoring, que además calcula lo que hay que transferir al factor. (Sin
        recurso la factura ya queda pagada al cederla.)"""
        move = self.move_id
        if (self.account_id.account_type == 'asset_receivable' and not self.reconciled
                and move.l10n_pe_factoring_state == 'assigned'
                and move.l10n_pe_factoring_modality == 'with_recourse'):
            return self.env._(
                'La factura %(invoice)s está cedida a %(factor)s (factoring con recurso): el cliente le '
                'paga al factor. Si le pagó a la empresa, regístrelo con «Cobro recibido por la '
                'empresa» en la operación %(operation)s.',
                invoice=move.name, factor=move.l10n_pe_factor_id.name, operation=move.l10n_pe_factoring_id.name)
        return super()._l10n_pe_payment_block_reason()
