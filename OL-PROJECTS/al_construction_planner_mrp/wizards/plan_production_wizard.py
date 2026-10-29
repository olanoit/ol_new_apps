# -*- coding: utf-8 -*-
"""W-04 «Orden de fabricación» (en su puente desde la v1.7, M17-09): una OF por
agrupador (o por toda la selección) y producto, para los niveles con etapas
de la selección. El producto sale de la línea de producción del plan del
nivel (el spool con su lista de materiales) o, en mobiliario, de la
tipología del ambiente; los componentes de las etapas de fabricación suben
lo consumido de las líneas del plan."""
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
        help='Piso: una OF por agrupador (piso, línea) y producto. Selección: una OF por '
             'producto para todo lo seleccionado.')
    # Paquete 1.10, M110-03: la planta sale de la lista de materiales de cada
    # orden; el campo solo la fuerza.
    picking_type_id = fields.Many2one(
        'stock.picking.type', string='Forzar planta', check_company=True,
        domain="[('code', '=', 'mrp_operation'), ('company_id', '=', company_id)]",
        help='Vacío: cada orden se crea en la planta de su lista de materiales.')
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

    @api.depends('plan_id', 'task_ids', 'whole_project', 'group_by', 'picking_type_id')
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
        # Metrado con diferencia sin aprobar (v1.6, M16-04): la OF del
        # ambiente espera la aprobación de la jefatura.
        pending = self.env['construction.measurement']._construction_blocked_spaces(spaces - busy)
        groups = defaultdict(lambda: [self.env['project.task'], 0.0])
        no_bom = self.env['project.task']
        for space in (spaces - busy - pending).sorted(lambda t: (t.construction_floor_task_id.id, t.id)):
            source = self._production_source(space)
            if not source:
                no_bom |= space
                continue
            product, bom, qty, typology = source
            floor = space.construction_floor_task_id if self.group_by == 'floor' else False
            group = groups[(floor or self.env['project.task'], product, bom, typology)]
            group[0] |= space
            group[1] += qty
        notes = []
        if spaces & busy:
            notes.append(self.env._('Ya en una OF: %s.', ', '.join(
                self._space_label(space) for space in (spaces & busy))))
        if pending:
            notes.append(self.env._('Metrado con diferencia por aprobar: %s.', ', '.join(
                self._space_label(space) for space in pending)))
        if no_bom:
            notes.append(self.env._('Sin producto con lista de materiales: %s.', ', '.join(
                self._space_label(space) for space in no_bom)))
        values = [{
            'group_task_id': floor.id,
            'typology_id': typology.id if typology else False,
            'product_id': product.id,
            'bom_id': bom.id,
            'picking_type_id': self._production_picking_type(bom).id,
            'space_task_ids': [Command.set(group_spaces.ids)],
            'space_count': len(group_spaces),
            'qty': qty,
        } for (floor, product, bom, typology), (group_spaces, qty) in groups.items()]
        return values, notes

    def _space_label(self, space):
        """«Departamento / ambiente» en los avisos (paquete 1.7 parte 2,
        M17-25): «Cocina» sola no dice de qué departamento es."""
        apartment = space.construction_apartment_task_id
        return ' / '.join(filter(None, [apartment.name, space.name]))

    def _production_source(self, space):
        """(producto, BOM, cantidad, tipología) que fabrica el nivel: la línea de
        producción del plan del nivel con su lista de materiales. ``None`` si no
        fabrica nada."""
        lines = self.env['construction.resource.plan.line'].search([
            ('plan_id', '=', self.plan_id.id), ('space_task_id', '=', space.id),
            ('resource_type', '=', 'production'), ('product_id', '!=', False)])
        if not lines:
            return None
        product = lines[0].product_id
        bom = self.env['mrp.bom']._bom_find(product, company_id=self.company_id.id)[product]
        if not bom:
            return None
        qty = sum(line._qty_to_product_uom(line.qty_planned)
                  for line in lines.filtered(lambda l: l.product_id == product))
        return product, bom, qty, self.env['construction.typology']

    def _production_picking_type(self, bom):
        """Planta de la orden: la forzada, la de su lista de materiales o, si
        la lista no tiene, la operación de fabricación de la compañía."""
        self.ensure_one()
        return self.picking_type_id or bom.picking_type_id or self.env['stock.picking.type'].search([
            ('code', '=', 'mrp_operation'), ('company_id', '=', self.company_id.id)], limit=1)

    def _production_extra_values(self, line):
        """Valores propios de cada puente para la orden de la línea."""
        return {}

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
                'product_qty': line.qty,
                'uom_id': bom.uom_id.id,
                'picking_type_id': self._production_picking_type(bom).id,
                'date_start': self.date_start,
                'origin': ' · '.join(filter(None, [
                    plan.display_name, line.group_task_id.display_name,
                    line.typology_id.code or line.product_id.default_code])),
                'company_id': plan.company_id.id,
                'construction_plan_id': plan.id,
                'construction_space_task_ids': [Command.set(line.space_task_ids.ids)],
                'project_id': plan.project_id.id,
            }
            vals.update(self._production_extra_values(line))
            productions |= self.env['mrp.production'].create(vals)
        productions._construction_sync_allocations()
        # M17-18: el jefe de producción revisa y confirma la fecha de cada una.
        productions._construction_schedule_date_review()
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
    group_task_id = fields.Many2one('project.task', string='Agrupador')
    typology_id = fields.Many2one('construction.typology', string='Tipología')
    product_id = fields.Many2one('product.product', string='Producto')
    bom_id = fields.Many2one('mrp.bom', string='Lista de materiales')
    picking_type_id = fields.Many2one('stock.picking.type', string='Planta')
    space_task_ids = fields.Many2many(
        'project.task', 'construction_plan_prod_wiz_line_space_rel', 'wizard_line_id',
        'task_id', string='Ambientes')
    space_count = fields.Integer(string='Niveles')
    qty = fields.Float(string='Cantidad a fabricar', digits='Product Unit')
