# -*- coding: utf-8 -*-
"""W-04 «Orden de fabricación»: una OF por piso (o por toda la selección) y
tipología, con el producto de la tipología por la cantidad de ambientes y los
componentes de su BOM."""
from collections import defaultdict

from odoo import Command, api, fields, models
from odoo.exceptions import UserError


class ConstructionPlanProductionWizard(models.TransientModel):
    _name = 'construction.plan.production.wizard'
    _inherit = 'construction.plan.supply.mixin'
    _description = 'Orden de fabricación desde el plan'

    group_by = fields.Selection(
        [('floor', 'Piso'), ('selection', 'Selección')], string='Una OF por',
        required=True, default='floor',
        help='Piso: una OF por piso y tipología. Selección: una OF por tipología para todo '
             'lo seleccionado.')
    picking_type_id = fields.Many2one(
        'stock.picking.type', string='Planta', required=True, check_company=True,
        domain="[('code', '=', 'mrp_operation'), ('company_id', '=', company_id)]",
        default=lambda self: self.env['stock.picking.type'].search([
            ('code', '=', 'mrp_operation'), ('company_id', '=', self.env.company.id)], limit=1))
    date_start = fields.Datetime(string='Fecha', required=True, default=fields.Datetime.now)
    line_ids = fields.One2many(
        'construction.plan.production.wizard.line', 'wizard_id', string='Vista previa',
        compute='_compute_line_ids', store=True, readonly=False)
    note = fields.Text(string='Avisos', compute='_compute_line_ids', store=True)

    def _get_spaces(self):
        """Ambientes de la selección (los de los módulos marcados, también)."""
        self.ensure_one()
        tasks = self._get_selected_tasks()
        if tasks is None:
            return self.env['project.task'].search([
                ('project_id', '=', self.plan_id.project_id.id),
                ('construction_level', '=', 'space')])
        return tasks.filtered(lambda t: t.construction_level == 'space') \
            | tasks.construction_space_task_id

    @api.depends('plan_id', 'task_ids', 'whole_project', 'group_by')
    def _compute_line_ids(self):
        for wizard in self:
            commands = [Command.clear()]
            notes = []
            if wizard.plan_id:
                values, notes = wizard._prepare_lines()
                commands += [Command.create(vals) for vals in values]
            wizard.line_ids = commands
            wizard.note = '\n'.join(notes) or False

    def _prepare_lines(self):
        self.ensure_one()
        spaces = self._get_spaces()
        busy = self.env['mrp.production'].search([
            ('construction_plan_id.project_id', '=', self.plan_id.project_id.id),
            ('state', '!=', 'cancel'),
            ('construction_space_task_ids', 'in', spaces.ids),
        ]).construction_space_task_ids
        groups = defaultdict(lambda: self.env['project.task'])
        no_bom = self.env['project.task']
        for space in (spaces - busy).sorted(lambda t: (t.construction_floor_task_id.id, t.id)):
            typology = space.construction_typology_id
            if not (typology.bom_id and typology.product_tmpl_id.product_variant_id):
                no_bom |= space
                continue
            floor = space.construction_floor_task_id if self.group_by == 'floor' else False
            groups[(floor or self.env['project.task'], typology)] |= space
        notes = []
        if spaces & busy:
            notes.append(self.env._('Ya en una OF: %s.', ', '.join(
                (spaces & busy).mapped('display_name'))))
        if no_bom:
            notes.append(self.env._('Sin tipología con producto y BOM: %s.', ', '.join(
                no_bom.mapped('display_name'))))
        values = [{
            'group_task_id': floor.id,
            'typology_id': typology.id,
            'product_id': typology.product_tmpl_id.product_variant_id.id,
            'bom_id': typology.bom_id.id,
            'space_task_ids': [Command.set(group_spaces.ids)],
            'space_count': len(group_spaces),
        } for (floor, typology), group_spaces in groups.items()]
        return values, notes

    def action_create(self):
        self.ensure_one()
        plan = self.plan_id
        plan._check_supply_wizard_state()
        lines = self.line_ids.filtered(lambda l: l.space_count)
        if not lines:
            raise UserError(self.env._('No hay ambientes por fabricar en esta selección.'))
        productions = self.env['mrp.production']
        for line in lines:
            bom = line.bom_id
            vals = {
                'product_id': line.product_id.id,
                'bom_id': bom.id,
                'product_qty': line.space_count,
                'product_uom_id': bom.product_uom_id.id,
                'picking_type_id': self.picking_type_id.id,
                'date_start': self.date_start,
                'origin': ' · '.join(filter(None, [
                    plan.display_name, line.group_task_id.display_name, line.typology_id.code])),
                'company_id': plan.company_id.id,
                'construction_plan_id': plan.id,
                'construction_space_task_ids': [Command.set(line.space_task_ids.ids)],
                'project_id': plan.project_id.id,
            }
            productions |= self.env['mrp.production'].create(vals)
        productions._construction_sync_allocations()
        plan._mark_in_progress()
        plan.message_post(body=self.env._(
            'Órdenes de fabricación: %s.', ', '.join(productions.mapped('name'))))
        action = {
            'type': 'ir.actions.act_window',
            'name': self.env._('Órdenes de fabricación'),
            'res_model': 'mrp.production',
        }
        if len(productions) == 1:
            action.update(view_mode='form', res_id=productions.id)
        else:
            action.update(view_mode='list,form', domain=[('id', 'in', productions.ids)])
        return action


class ConstructionPlanProductionWizardLine(models.TransientModel):
    _name = 'construction.plan.production.wizard.line'
    _description = 'OF propuesta desde el plan'

    wizard_id = fields.Many2one(
        'construction.plan.production.wizard', string='Asistente', required=True,
        ondelete='cascade')
    group_task_id = fields.Many2one('project.task', string='Piso')
    typology_id = fields.Many2one('construction.typology', string='Tipología')
    product_id = fields.Many2one('product.product', string='Producto de la tipología')
    bom_id = fields.Many2one('mrp.bom', string='Lista de materiales')
    space_task_ids = fields.Many2many(
        'project.task', 'construction_plan_prod_wiz_line_space_rel', 'wizard_line_id',
        'task_id', string='Ambientes')
    space_count = fields.Integer(string='Cantidad de ambientes')
