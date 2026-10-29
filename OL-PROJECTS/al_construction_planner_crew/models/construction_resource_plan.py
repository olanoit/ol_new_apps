# -*- coding: utf-8 -*-
"""Personal propio en el plan (fase 7, en su puente desde la v1.7): el rol de
la cuadrilla, las horas de la hoja de horas como ejecutado y real, y los
turnos sin horas como comprometido."""
from collections import defaultdict

from odoo import api, fields, models


class ConstructionResourcePlanLine(models.Model):
    _inherit = 'construction.resource.plan.line'

    role_id = fields.Many2one('planning.role', string='Rol')

    def _get_role(self):
        self.ensure_one()
        return self.role_id or self.activity_id.role_id

    def _get_timesheet_by_employee(self):
        """{empleado: horas} de la hoja de horas del nivel de la línea y sus
        descendientes con empleados del rol de la línea (o de su actividad)."""
        self.ensure_one()
        if not self.task_id:
            return {}
        domain = [('task_id', 'child_of', self.task_id.id), ('project_id', '=', self.project_id.id),
                  ('employee_id', '!=', False)]
        # Hasta una fecha de corte: la entrega semanal (fase 10).
        if self.env.context.get('construction_date_to'):
            domain.append(('date', '<=', self.env.context['construction_date_to']))
        role = self._get_role()
        if role:
            domain.append(('employee_id.planning_role_ids', 'in', role.ids))
        # sudo: las horas de otros empleados se suman sin dar acceso a sus
        # registros; solo para el avance y el costo de la línea.
        lines_sudo = self.env['account.analytic.line'].sudo()
        return {employee: hours or 0.0 for employee, hours in lines_sudo._read_group(
            domain, ['employee_id'], ['unit_amount:sum'])}

    def _get_labor_amounts(self):
        """(comprometido, real) del personal propio: real = horas registradas
        por el costo hora de cada empleado; comprometido = horas de sus turnos
        de la línea aún no registradas, al mismo costo."""
        self.ensure_one()
        registered = self._get_timesheet_by_employee()
        # sudo: el costo hora y los turnos son de RR. HH. y Planificación; se
        # leen solo para valorizar la línea.
        actual = sum(employee.sudo().hourly_cost * hours for employee, hours in registered.items())
        planned = defaultdict(float)
        for allocation in self.allocation_ids.filtered(
                lambda a: a.kind == 'planning_slot' and a.state != 'cancel'):
            slot_sudo = allocation.sudo().slot_id
            employee = slot_sudo.resource_ids.employee_id[:1]
            if employee:
                planned[employee] += slot_sudo.allocated_hours
        committed = sum(
            max(hours - registered.get(employee, 0.0), 0.0) * employee.sudo().hourly_cost
            for employee, hours in planned.items())
        return committed, actual

    def _get_labor_actual(self, day):
        registered = self.with_context(construction_date_to=day)._get_timesheet_by_employee()
        # sudo: el costo hora es de RR. HH.; solo para valorizar la línea.
        return sum(employee.sudo().hourly_cost * hours for employee, hours in registered.items())

    @api.depends('role_id')
    def _compute_resource_name(self):
        return super()._compute_resource_name()

    def _get_resource_record(self):
        return super()._get_resource_record() or self.role_id

    @api.model
    def _weekly_load_groupby(self):
        return super()._weekly_load_groupby() + ['role_id']

    def write(self, vals):
        res = super().write(vals)
        if 'role_id' in vals:
            self._refresh_control()
        return res


class ConstructionLaborActivity(models.Model):
    _inherit = 'construction.labor.activity'

    role_id = fields.Many2one('planning.role', string='Rol', help='Personal propio.')


class ConstructionExecutionTemplateLine(models.Model):
    _inherit = 'construction.execution.template.line'

    role_id = fields.Many2one('planning.role', string='Rol de la cuadrilla',
                              help='Personal propio: operario, oficial, peón…')


class ConstructionPlanRecipeWizard(models.TransientModel):
    _inherit = 'construction.plan.recipe.wizard'

    def _prepare_line_vals(self, task, recipe_line, prices):
        vals = super()._prepare_line_vals(task, recipe_line, prices)
        vals['role_id'] = (recipe_line.role_id or recipe_line.activity_id.role_id).id
        return vals


class ConstructionSpaceStage(models.Model):
    _inherit = 'construction.space.stage'

    role_id = fields.Many2one(
        'planning.role', string='Cuadrilla', compute='_compute_resources',
        help='El rol de las líneas de personal propio de la etapa.')

    @api.model
    def _resources_by_stage_extra(self, result, base):
        super()._resources_by_stage_extra(result, base)
        for space, stage, role in self.env['construction.resource.plan.line']._read_group(
                base + [('resource_type', '=', 'labor'), ('role_id', '!=', False)],
                ['space_task_id', 'stage', 'role_id']):
            result.setdefault((space.id, stage), {}).setdefault('role', role)

    def _compute_resources(self):
        super()._compute_resources()
        resources = self._resources_by_stage(self.filtered('id'))
        for record in self:
            record.role_id = resources.get((record.space_task_id.id, record.stage), {}).get('role')
