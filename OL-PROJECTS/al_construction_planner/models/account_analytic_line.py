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
        lines._construction_refresh_plan()
        return lines

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
