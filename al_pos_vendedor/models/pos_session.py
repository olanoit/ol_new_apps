# -*- coding: utf-8 -*-

from odoo import api, models


class PosSession(models.Model):
    _inherit = "pos.session"

    @api.model
    def _load_pos_data_models(self, config):
        # pos_hr solo carga hr.employee en el POS cuando module_pos_hr está
        # activo. La asignación de vendedor necesita los registros de empleado
        # (para resolver seller_ids a nombres en el frontend) aunque esa opción
        # esté desactivada, por lo que se incluye hr.employee cuando el PdV usa
        # vendedores autorizados.
        data = super()._load_pos_data_models(config)
        if config.authorized_seller and "hr.employee" not in data:
            data.append("hr.employee")
        return data
