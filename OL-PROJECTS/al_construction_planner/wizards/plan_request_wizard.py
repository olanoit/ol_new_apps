# -*- coding: utf-8 -*-
"""W-03 «Requerimiento de obra» (P-11): un requerimiento de obra
(al_construction_material_request) con el saldo de los materiales de la
selección, agrupado por ambiente, departamento o piso. Cada línea lleva la
tarea del grupo y asignaciones a las líneas del plan de cada nivel."""
from collections import defaultdict

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

GROUP_FIELDS = {
    'space': 'space_task_id',
    'apartment': 'apartment_task_id',
    'floor': 'floor_task_id',
}


class ConstructionPlanRequestWizard(models.TransientModel):
    _name = 'construction.plan.request.wizard'
    _inherit = 'construction.plan.supply.mixin'
    _description = 'Requerimiento de obra desde el plan'

    group_by = fields.Selection(
        [('space', 'Ambiente'), ('apartment', 'Departamento'), ('floor', 'Piso')],
        string='Agrupar por', required=True, default='floor',
        help='Cada línea del requerimiento lleva la tarea del grupo; las asignaciones '
             'apuntan a las líneas del plan de cada ambiente o módulo.')
    location_src_id = fields.Many2one(
        'stock.location', string='Origen', check_company=True,
        domain="[('usage', '=', 'internal'), ('company_id', '=', company_id)]",
        default=lambda self: self.env.company.construction_src_location_id)
    date_required = fields.Date(
        string='Fecha requerida', help='Vacía: la fecha de necesidad más temprana.')
    line_ids = fields.One2many(
        'construction.plan.request.wizard.line', 'wizard_id', string='Vista previa',
        compute='_compute_line_ids', store=True, readonly=False)

    @api.depends('plan_id', 'task_ids', 'whole_project', 'group_by', 'location_src_id',
                 'stage_production', 'stage_assembly', 'stage_installation', 'stage_finishing')
    def _compute_line_ids(self):
        for wizard in self:
            commands = [Command.clear()]
            if wizard.plan_id:
                commands += [Command.create(vals) for vals in wizard._prepare_lines()]
            wizard.line_ids = commands

    def _prepare_lines(self):
        self.ensure_one()
        field = GROUP_FIELDS[self.group_by]
        groups = defaultdict(lambda: self.env['construction.resource.plan.line'])
        for line in self._get_selected_lines(
                [('resource_type', '=', 'material'), ('product_id', '!=', False)]):
            if line.product_id.type != 'consu':
                continue
            # Una línea por encima del nivel de agrupación (p. ej. del piso al
            # agrupar por ambiente) se agrupa en su propio nivel.
            groups[(line[field] or line.task_id, line.product_id)] |= line
        free = {}
        if self.location_src_id:
            products = self.env['product.product'].browse(
                {product.id for _task, product in groups}).with_context(
                location=self.location_src_id.id)
            free = {product.id: product.free_qty for product in products}
        result = []
        for (task, product), plan_lines in sorted(
                groups.items(),
                key=lambda kv: (kv[0][0].display_name or '', kv[0][1].display_name)):
            planned = sum(l._qty_to_product_uom(l.qty_planned) for l in plan_lines)
            requested = sum(l._qty_to_product_uom(l.qty_requested) for l in plan_lines)
            remaining = planned - requested
            if product.uom_id.compare(remaining, 0.0) <= 0:
                continue
            result.append({
                'group_task_id': task.id,
                'product_id': product.id,
                'product_uom_id': product.uom_id.id,
                'qty_planned': planned,
                'qty_requested': requested,
                'qty_remaining': remaining,
                'qty_available': free.get(product.id, 0.0),
                'qty_to_request': remaining,
                'date_needed': min(filter(None, plan_lines.mapped('date_needed')), default=False),
                'plan_line_ids': [Command.set(plan_lines.ids)],
            })
        return result

    def action_create(self):
        self.ensure_one()
        plan = self.plan_id
        plan._check_supply_wizard_state()
        lines = self.line_ids.filtered(
            lambda l: l.product_uom_id and l.product_uom_id.compare(l.qty_to_request, 0.0) > 0)
        if not lines:
            raise UserError(self.env._('No hay nada que pedir con esta selección y filtros.'))
        tasks = lines.group_task_id
        vals = {
            'project_id': plan.project_id.id,
            'task_id': tasks.id if len(tasks) == 1 else False,
            'date_required': self.date_required or min(
                filter(None, lines.mapped('date_needed')), default=False),
            'construction_plan_id': plan.id,
            'line_ids': [Command.create({
                'product_id': line.product_id.id,
                'product_qty': line.qty_to_request,
                'product_uom_id': line.product_uom_id.id,
                'task_id': line.group_task_id.id,
            }) for line in lines],
        }
        if self.location_src_id:
            vals['location_src_id'] = self.location_src_id.id
        request = self.env['construction.material.request'].create(vals)
        allocation_values = []
        for line, request_line in zip(lines, request.line_ids.sorted('id')):
            shares = line.plan_line_ids._supply_split(line.qty_to_request)
            allocation_values += [{
                'plan_line_id': plan_line.id,
                'kind': 'material_request',
                'material_request_line_id': request_line.id,
                'qty_allocated': share,
            } for plan_line, share in shares.items() if not plan_line.product_uom_id.is_zero(share)]
        self.env['construction.resource.plan.allocation'].create(allocation_values)
        plan._mark_in_progress()
        plan.message_post(body=self.env._(
            'Requerimiento de obra %(request)s: %(count)s materiales (%(selection)s).',
            request=request.name, count=len(lines), selection=self._get_selection_label()))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'construction.material.request',
            'res_id': request.id,
            'view_mode': 'form',
        }


class ConstructionPlanRequestWizardLine(models.TransientModel):
    _name = 'construction.plan.request.wizard.line'
    _description = 'Línea del requerimiento de obra desde el plan'

    wizard_id = fields.Many2one(
        'construction.plan.request.wizard', string='Asistente', required=True,
        ondelete='cascade')
    group_task_id = fields.Many2one('project.task', string='Nivel')
    product_id = fields.Many2one('product.product', string='Material', required=True)
    product_uom_id = fields.Many2one('uom.uom', string='Unidad')
    qty_planned = fields.Float(string='Planificado', digits='Product Unit')
    qty_requested = fields.Float(string='Pedido', digits='Product Unit')
    qty_remaining = fields.Float(string='Saldo', digits='Product Unit')
    qty_available = fields.Float(string='Disponible', digits='Product Unit')
    qty_to_request = fields.Float(string='A pedir', digits='Product Unit')
    date_needed = fields.Date(string='Necesidad')
    plan_line_ids = fields.Many2many(
        'construction.resource.plan.line', 'construction_plan_request_wiz_line_rel',
        'wizard_line_id', 'plan_line_id', string='Líneas del plan')
