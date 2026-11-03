# -*- coding: utf-8 -*-
from odoo import models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _prepare_analytic_lines(self):
        # El gasto ya cargó el centro de costo en el comprobante de origen. La
        # línea de destino conserva la distribución para informar por centro,
        # pero otro apunte analítico lo cargaría dos veces.
        if self.move_id.l10n_pe_is_destiny_entry:
            return []
        return super()._prepare_analytic_lines()
