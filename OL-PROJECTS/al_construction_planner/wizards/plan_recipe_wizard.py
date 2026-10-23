# -*- coding: utf-8 -*-
"""«Generar plan desde la receta» (v1.7, M17-04): una línea del plan por cada
recurso de la receta de cada tarea, con la cantidad por unidad multiplicada
por el metrado planificado de la tarea. Sirve a cualquier rubro; la
tipología de mueble sigue con «Generar plan»."""
from collections import defaultdict

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang


class ConstructionPlanRecipeWizard(models.TransientModel):
    _name = 'construction.plan.recipe.wizard'
    _description = 'Generar plan desde la receta'
    _check_company_auto = True

    plan_id = fields.Many2one(
        'construction.resource.plan', string='Plan', required=True, check_company=True)
    company_id = fields.Many2one(related='plan_id.company_id', string='Compañía')
    project_id = fields.Many2one(related='plan_id.project_id', string='Obra')
    currency_id = fields.Many2one(related='plan_id.currency_id', string='Moneda')
    task_ids = fields.Many2many(
        'project.task', string='Niveles', check_company=True,
        domain="[('project_id', '=', project_id), "
               "('construction_execution_template_id', '!=', False)]",
        help='Vacío: todas las tareas de la obra con receta.')
    stage_ids = fields.Many2many(
        'construction.stage', string='Etapas',
        default=lambda self: self.env['construction.stage'].search([]),
        help='Los recursos sin etapa entran siempre.')
    mode = fields.Selection(
        [('replace', 'Reemplazar lo generado'), ('add', 'Agregar')], string='Si ya hay líneas',
        default='replace', required=True,
        help='Reemplazar borra antes las líneas generadas desde la receta en esas tareas '
             '(conserva las manuales); agregar las suma.')
    preview_html = fields.Html(string='Se creará', compute='_compute_preview', sanitize=False)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context
        if 'plan_id' in fields_list and not res.get('plan_id') \
                and ctx.get('active_model') == 'construction.resource.plan':
            res['plan_id'] = ctx.get('active_id')
        return res

    def _get_tasks(self):
        self.ensure_one()
        if self.task_ids:
            return self.task_ids.filtered('construction_execution_template_id')
        return self.env['project.task'].search([
            ('project_id', '=', self.plan_id.project_id.id),
            ('construction_execution_template_id', '!=', False)],
            order='construction_path, id')

    def _price(self, recipe_line, prices):
        if recipe_line.price_unit:
            return recipe_line.price_unit
        if recipe_line.resource_type in ('contract', 'labor') and recipe_line.activity_id:
            key = ('activity', recipe_line.activity_id.id)
            if key not in prices:
                prices[key] = recipe_line.activity_id._get_rate(self.plan_id.project_id)[0]
            return prices[key]
        return recipe_line.product_id.standard_price

    def _collect(self):
        """Valores de las líneas por crear y avisos (tareas sin metrado)."""
        self.ensure_one()
        plan = self.plan_id
        project = plan.project_id
        codes = set(self.stage_ids.mapped('code'))
        analytic = {str(project.account_id.id): 100.0} if project.account_id else False
        prices = {}
        vals_list, warnings = [], defaultdict(list)
        for task in self._get_tasks():
            recipe = task.construction_execution_template_id
            if not task.construction_qty:
                warnings['no_qty'].append(task.display_name)
                continue
            for recipe_line in recipe.line_ids:
                if recipe_line.stage and recipe_line.stage not in codes:
                    continue
                vals = self._prepare_line_vals(task, recipe_line, prices)
                vals['analytic_distribution'] = analytic
                vals_list.append(vals)
        return vals_list, warnings

    def _prepare_line_vals(self, task, recipe_line, prices):
        """Línea del plan de un recurso de la receta en ``task``."""
        activity = recipe_line.activity_id
        return {
            'plan_id': self.plan_id.id,
            'task_id': task.id,
            'resource_type': recipe_line.resource_type,
            'resource_type_id': recipe_line.resource_type_id.id,
            'stage': recipe_line.stage or activity.stage or False,
            'product_id': (recipe_line.product_id or activity.product_id).id,
            'activity_id': activity.id,
            'product_uom_id': recipe_line.product_uom_id.id,
            'qty_planned': recipe_line.qty * task.construction_qty,
            'price_unit_planned': self._price(recipe_line, prices),
            'source': 'recipe',
            'source_ref': recipe_line.template_id.code,
        }

    @api.depends('plan_id', 'task_ids', 'stage_ids', 'mode')
    def _compute_preview(self):
        for wizard in self:
            if not wizard.plan_id:
                wizard.preview_html = False
                continue
            vals_list, warnings = wizard._collect()
            total = sum(v['qty_planned'] * v['price_unit_planned'] for v in vals_list)
            body = Markup('<p>%s</p>') % self.env._(
                '%(lines)s líneas en %(tasks)s niveles por %(amount)s.',
                lines=len(vals_list), tasks=len({v['task_id'] for v in vals_list}),
                amount=formatLang(self.env, total, currency_obj=wizard.currency_id))
            if warnings['no_qty']:
                body += Markup('<p class="text-warning">%s</p>') % self.env._(
                    'Sin cantidad presupuestada (no generan): %s',
                    ', '.join(warnings['no_qty'][:10]))
            wizard.preview_html = body

    def action_generate(self):
        self.ensure_one()
        plan = self.plan_id
        plan._check_draft()
        tasks = self._get_tasks()
        if not tasks:
            raise UserError(self.env._(
                'No hay tareas con receta en la selección. Asigne la receta y la cantidad '
                'planificado a las partidas.'))
        if self.mode == 'replace':
            plan.line_ids.filtered(
                lambda l: l.source == 'recipe' and l.task_id in tasks).unlink()
        vals_list, _warnings = self._collect()
        lines = self.env['construction.resource.plan.line'].with_context(
            construction_plan_generating=True).create(vals_list)
        lines._apply_analytic_rules()
        stages = self.env['construction.space.stage']._sync_from_plan(plan)
        plan.message_post(body=self.env._(
            'Plan generado desde la receta: %(lines)s líneas en %(tasks)s niveles y %(stages)s '
            'etapas en el cronograma.', lines=len(lines), tasks=len(lines.task_id),
            stages=len(stages)))
        return plan.action_view_lines()


class ConstructionPlanRecipeWizardCalc(models.TransientModel):
    """Forma de cálculo, moneda y fuente del APU (CREVAL v1.0, 6.1, 6.2 y 6.5)."""
    _inherit = 'construction.plan.recipe.wizard'

    def _prepare_line_vals(self, task, recipe_line, prices):
        vals = super()._prepare_line_vals(task, recipe_line, prices)
        vals.update(calc_method=recipe_line.calc_method, calc_pct=recipe_line.calc_pct,
                    calc_scope=recipe_line.calc_scope)
        company = self.plan_id.company_id or self.env.company
        if recipe_line.line_currency_id and recipe_line.line_currency_id != company.currency_id:
            vals.update(price_currency_id=recipe_line.line_currency_id.id,
                        price_unit_currency=recipe_line.price_unit)
        return vals

    def action_generate(self):
        """Con la fuente «Work Items de la venta» (6.2), las recetas enlazadas a
        un Work Item de la obra se toman de él antes de generar."""
        self.ensure_one()
        project = self.plan_id.project_id
        if project.construction_apu_source == 'work_item' and 'x_work_item' in self.env:
            recipes = self._get_tasks().construction_execution_template_id.filtered(
                'work_item_id')
            items = recipes._work_item_read(recipes.mapped('work_item_id'))
            recipes._check_work_item_sync(items)
            # Solo lo que cambió en la cotización; un cambio hecho en la receta
            # se resuelve antes con «Sincronizar con el Work Item».
            for recipe in recipes.filtered(lambda r: r.sync_state == 'work_item'):
                item = items[recipe.work_item_id]
                recipe._apply_work_item_to_template(item)
                recipe._mark_synced(item)
        return super().action_generate()
