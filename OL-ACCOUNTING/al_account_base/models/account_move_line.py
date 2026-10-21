# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # Glosa peruana por línea.
    l10n_pe_gloss = fields.Char(string='Glosa', copy=False)

    def _l10n_pe_payment_block_reason(self):
        """Motivo por el que este saldo no se cancela con un pago o una
        aplicación directos, o ``False``.

        Gancho para los documentos que están en manos de un tercero: una letra
        enviada al banco (la cancela el abono del banco) o una factura cedida
        con recurso (la cobra el factor). Lo consultan el asistente de pago, el
        pago múltiple y la aplicación de documentos.
        """
        self.ensure_one()
        return False

    def _l10n_pe_payment_block_reasons(self):
        """Mensajes de bloqueo de estos apuntes, sin repetir."""
        reasons = []
        for line in self:
            reason = line._l10n_pe_payment_block_reason()
            if reason and reason not in reasons:
                reasons.append(reason)
        return reasons
