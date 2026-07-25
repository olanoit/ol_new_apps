# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models
from odoo.fields import Domain

_logger = logging.getLogger(__name__)


class PosConfig(models.Model):
    _inherit = "pos.config"

    authorized_seller = fields.Boolean(string='Vendedor autorizado')
    seller_ids = fields.Many2many(
        'hr.employee',
        'al_pos_vendedor_employee_rel',
        'empleado_id',
        'pos_id',
        string="Vendedores permitidos",
    )

    def _employee_domain(self, user_id):
        domain = super()._employee_domain(user_id)
        if self.authorized_seller and self.seller_ids:
            # Incluir todos los vendedores configurados aunque no estén en los
            # grupos de acceso de pos_hr, para que aparezcan en el selector del POS.
            domain = Domain.OR([domain, [('id', 'in', self.seller_ids.ids)]])
        return domain
