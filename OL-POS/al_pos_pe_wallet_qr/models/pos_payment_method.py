# -*- coding: utf-8 -*-
from odoo import api, models


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    @api.model
    def _load_pos_data_fields(self, config):
        # El TPV distingue el QR de billetera (imagen fija) de un QR generado.
        fields = super()._load_pos_data_fields(config)
        return fields + ['qr_code_method'] if 'qr_code_method' not in fields else fields
