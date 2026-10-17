# -*- coding: utf-8 -*-
from odoo.exceptions import UserError

# Los módulos de obras MRP heredados costean las mismas piezas por otro
# mecanismo: no conviven con este (decisión de Allcenter del 16-set-2026).
INCOMPATIBLE_MODULES = ('allcenter_obras_mrp', 'allcenter_obras_mrp_integration')


def pre_init_hook(env):
    installed = env['ir.module.module'].search([
        ('name', 'in', INCOMPATIBLE_MODULES), ('state', '=', 'installed')])
    if installed:
        raise UserError(env._(
            'El costeo de piezas por medida no se instala junto a %s: los dos costean '
            'las mismas piezas por mecanismos distintos.', ', '.join(installed.mapped('name'))))
