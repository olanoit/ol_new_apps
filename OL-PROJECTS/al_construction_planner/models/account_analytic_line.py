# -*- coding: utf-8 -*-
from odoo import api, models

from .construction_resource_plan import OPEN_STATES


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    # Las horas de la hoja de horas son el ejecutado y el real del personal
    # propio (fase 7).
    _CONSTRUCTION_FIELDS = {'unit_amount', 'task_id', 'employee_id', 'project_id', 'amount'}

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._construction_complete_plans()
        lines._construction_refresh_plan()
        return lines

    def _construction_complete_plans(self):
        """Apuntes de una obra sin etapa o sin partida (v1.5, M15-15): Odoo
        pone solo la cuenta de la obra en el consumo de la OF y en el consumo
        en obra. La regla analítica del planificador completa las columnas
        vacías: la etapa de fabricación en la OF, la primera de campo que no
        consume en la OF en el consumo en obra (producción e instalación en
        mobiliario), la de la actividad en la factura de una contrata y la
        partida según la categoría del producto."""
        lines = self.filtered(lambda l: l.account_id and l.product_id)
        if not lines:
            return
        sites = self.env['project.project'].search([
            ('is_construction_site', '=', True), ('account_id', 'in', lines.account_id.ids)])
        site_accounts = set(sites.account_id.ids)
        lines = lines.filtered(lambda l: l.account_id.id in site_accounts)
        if not lines:
            return
        Rule = self.env['construction.analytic.rule']
        Activity = self.env['construction.labor.activity']
        Stage = self.env['construction.stage']
        activities = {a.product_id.id: a for a in Activity.search(
            [('product_id', 'in', lines.product_id.ids)])}
        for line in lines:
            product = line.product_id
            activity = activities.get(product.id)
            if activity:
                resource_type, stage = 'contract', activity.stage
            else:
                resource_type = 'material' if product.type == 'consu' else 'service'
                stock_move = line.move_line_id.move_id.stock_move_id \
                    if 'stock_move_id' in line.move_line_id.move_id._fields else False
                if line.category == 'manufacturing_order' or (
                        stock_move and stock_move.raw_material_production_id):
                    stage = Stage._consumption_code('production')
                elif stock_move:
                    stage = Stage._consumption_code('site')
                else:
                    stage = False
            accounts = Rule._accounts_for(line.company_id, resource_type, stage, product.categ_id)
            vals = {}
            for account in accounts:
                column = account.root_plan_id._column_name()
                if column in line._fields and not line[column]:
                    vals[column] = account.id
            if vals:
                line.write(vals)

    def write(self, vals):
        before = self.task_id
        res = super().write(vals)
        if self._CONSTRUCTION_FIELDS & set(vals):
            self._construction_refresh_plan(before)
        return res

    def unlink(self):
        tasks = self.task_id
        res = super().unlink()
        self.env['account.analytic.line']._construction_refresh_plan(tasks)
        return res

    def _construction_refresh_plan(self, extra_tasks=None):
        tasks = self.task_id | (extra_tasks or self.env['project.task'])
        if not tasks:
            return
        # Quien registra horas (el capataz) no ve el plan: solo se actualiza
        # el control de las líneas de personal propio de esos niveles.
        lines_sudo = self.env['construction.resource.plan.line'].sudo().search([
            ('resource_type', '=', 'labor'), ('plan_id.state', 'in', OPEN_STATES),
            ('project_id', 'in', tasks.project_id.ids),
            ('task_id', 'parent_of', tasks.ids)])
        lines_sudo._refresh_control()
