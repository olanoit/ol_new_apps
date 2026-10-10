# -*- coding: utf-8 -*-
"""Base de los asistentes de abastecimiento (W-02 a W-04): reciben la
selección del árbol (P-02) en el contexto, la expanden a sus descendientes y
filtran las líneas del plan vigente."""
from odoo import Command, api, fields, models

from .plan_generate_wizard import STAGE_FIELDS

# Unidades «de medida»: se compran con decimales (m de tapacanto). Las demás
# (planchas, juegos, unidades) se redondean a entero hacia arriba (P-10).
MEASURE_UOMS = (
    'uom.product_uom_meter', 'uom.product_uom_kgm', 'uom.product_uom_litre',
    'uom.product_uom_square_meter', 'uom.product_uom_cubic_meter', 'uom.product_uom_hour',
)


class ConstructionPlanSupplyMixin(models.AbstractModel):
    _name = 'construction.plan.supply.mixin'
    _description = 'Selección del plan para los asistentes de abastecimiento'
    _check_company_auto = True

    plan_id = fields.Many2one(
        'construction.resource.plan', string='Plan', required=True, check_company=True,
        domain="[('state', 'in', ('approved', 'in_progress'))]")
    company_id = fields.Many2one(related='plan_id.company_id', string='Compañía')
    project_id = fields.Many2one(related='plan_id.project_id', string='Obra')
    currency_id = fields.Many2one(related='plan_id.currency_id', string='Moneda')
    task_ids = fields.Many2many(
        'project.task', string='Selección', check_company=True,
        domain="[('project_id', '=', project_id), ('construction_level', '!=', False)]",
        help='Niveles marcados en el árbol; incluyen todo lo que cuelga de ellos.')
    whole_project = fields.Boolean(string='Toda la obra')
    stage_production = fields.Boolean(string='Producción', default=True)
    stage_assembly = fields.Boolean(string='Armado', default=True)
    stage_installation = fields.Boolean(string='Instalación', default=True)
    stage_finishing = fields.Boolean(string='Acabado y entrega', default=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context
        plan_id = ctx.get('default_plan_id') or (
            ctx.get('active_model') == 'construction.resource.plan' and ctx.get('active_id'))
        if plan_id and 'plan_id' in fields_list:
            res['plan_id'] = plan_id
            self.env['construction.resource.plan'].browse(plan_id)._check_supply_wizard_state()
        task_ids = [i for i in ctx.get('construction_selection_task_ids') or [] if i]
        if 'task_ids' in fields_list and task_ids:
            res['task_ids'] = [Command.set(task_ids)]
        if 'whole_project' in fields_list:
            res['whole_project'] = bool(ctx.get('construction_selection_project')) or not task_ids
        return res

    def _get_stages(self):
        self.ensure_one()
        return [stage for stage, field in STAGE_FIELDS.items() if self[field]]

    def _get_selected_tasks(self):
        """Tareas de la selección con sus descendientes; ``None`` = toda la obra."""
        self.ensure_one()
        if self.whole_project or not self.task_ids:
            return None
        return self.env['project.task'].search([
            ('id', 'child_of', self.task_ids.ids),
            ('project_id', '=', self.plan_id.project_id.id)])

    def _get_selected_lines(self, domain=None):
        self.ensure_one()
        PlanLine = self.env['construction.resource.plan.line']
        if not self.plan_id:
            return PlanLine
        domain = [('plan_id', '=', self.plan_id.id),
                  ('stage', 'in', self._get_stages())] + (domain or [])
        tasks = self._get_selected_tasks()
        if tasks is not None:
            domain.append(('task_id', 'in', tasks.ids))
        return PlanLine.search(domain)

    @api.model
    def _is_whole_uom(self, uom):
        for xmlid in MEASURE_UOMS:
            measure = self.env.ref(xmlid, raise_if_not_found=False)
            if measure and uom._has_common_reference(measure):
                return False
        return True

    def _get_selection_label(self):
        self.ensure_one()
        if self.whole_project or not self.task_ids:
            return self.env._('Toda la obra')
        names = self.task_ids.mapped('display_name')
        return ', '.join(names[:5]) + (' …' if len(names) > 5 else '')
