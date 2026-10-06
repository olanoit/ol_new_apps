# -*- coding: utf-8 -*-

from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    authorized_seller = fields.Boolean(string='Vendedor autorizado')
    # Nota: los nombres de columna están invertidos respecto a su contenido
    # (`empleado_id` guarda el pos.config y `pos_id` el hr.employee). Se
    # conservan para no migrar la tabla de relación existente.
    seller_ids = fields.Many2many(
        'hr.employee',
        'al_pos_vendedor_employee_rel',
        'empleado_id',
        'pos_id',
        string="Vendedores permitidos",
        check_company=True,
    )
    # Ya NO se amplía `_employee_domain`: ese dominio decide quién puede
    # iniciar sesión como cajero en pos_hr. Los vendedores se cargan aparte
    # (ver hr_employee.py) sin PIN ni código de barras y sin poder iniciar
    # sesión.
