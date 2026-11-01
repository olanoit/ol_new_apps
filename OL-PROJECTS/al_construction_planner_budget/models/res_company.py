# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Paquete 1.16, D3: el control de compras compara solo en estos planes.
    construction_budget_control_plan_ids = fields.Many2many(
        'account.analytic.plan', 'construction_budget_control_plan_rel', 'company_id', 'plan_id',
        string='Planes que controla el presupuesto',
        help='La compra se compara con la suma de las líneas del presupuesto que coinciden en '
             'estos planes (por ejemplo obra, etapa y tipo de costo). Las cuentas de nivel y de '
             'rubro quedan para el análisis. Vacío: se comparan todas las cuentas.')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_budget_control_plan_ids = fields.Many2many(
        related='company_id.construction_budget_control_plan_ids', readonly=False)
