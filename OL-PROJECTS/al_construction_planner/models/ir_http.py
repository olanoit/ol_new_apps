# -*- coding: utf-8 -*-
"""Datos de la sesión que usa la interfaz del planificador."""
from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        """Ancho máximo de los nombres de la compañía activa (paquete 1.16,
        M116-08): la interfaz lo pone en la variable CSS
        ``--o-cp-name-max-width``."""
        result = super().session_info()
        if self.env.user._is_internal():
            result['construction_name_max_width'] = self.env.company.construction_name_max_width
        return result
