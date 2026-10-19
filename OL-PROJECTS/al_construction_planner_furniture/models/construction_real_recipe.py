# -*- coding: utf-8 -*-
"""Metrado como receta real del mueble (v1.8, M17-15) y versus con
autorización en producción (M17-20).

El supervisor mide el espacio; el diseño y el despiece que resultan se cargan
como receta real del módulo (o del mueble): piezas y consumo de materiales,
accesorios y consumibles, a mano o con el formato del importador de la
proyección. La receta real queda ligada al módulo y a su receta planificada y
se ven lado a lado, material por material.

Al confirmarla:

* actualiza la lista de materiales del producto del módulo (M18-15): la
  orden de fabricación sale con sus componentes;
* registra cada diferencia (cantidad y soles) contra lo planificado, con suma
  hacia mueble, ambiente, piso y obra (``construction.recipe.versus``);
* si el costo real supera al planificado en más del umbral de Ajustes (10 %
  por defecto), la orden de fabricación del módulo espera la autorización de
  la jefatura de proyectos. Bajo el umbral, producción sigue sin esperar.

Reemplaza al metrado por metros lineales (v1.6) y al «metrado por cantidad»
(v1.7), que quedan como histórico.
"""
from markupsafe import Markup

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.al_construction_planner.models.common import PROJECT_HEAD_GROUPS, stage_selection


class ConstructionRealRecipe(models.Model):
    _name = 'construction.real.recipe'
    _description = 'Metrado: receta real del mueble'
    _inherit = ['mail.thread']
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(string='Metrado', compute='_compute_name', store=True)
    task_id = fields.Many2one(
        'project.task', string='Módulo o mueble', required=True, index=True, check_company=True,
        domain="[('construction_level', 'in', ('module', 'furniture'))]", tracking=True)
    project_id = fields.Many2one(related='task_id.project_id', string='Obra', store=True,
                                 index=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, index=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    space_task_id = fields.Many2one(related='task_id.construction_space_task_id', store=True,
                                    string='Ambiente')
    apartment_task_id = fields.Many2one(related='task_id.construction_apartment_task_id',
                                        store=True, string='Departamento')
    floor_task_id = fields.Many2one(related='task_id.construction_floor_task_id', store=True,
                                    string='Piso')
    template_id = fields.Many2one(
        'construction.typology.module', string='Receta planificada', compute='_compute_template_id',
        store=True, readonly=False,
        help='El módulo de la tipología del ambiente con el código del módulo.')
    user_id = fields.Many2one('res.users', string='Supervisor', default=lambda self: self.env.user)
    date = fields.Date(string='Fecha', default=fields.Date.context_today, required=True)
    state = fields.Selection([('draft', 'Borrador'), ('confirmed', 'Confirmado')],
                             string='Estado', default='draft', required=True, tracking=True)
    line_ids = fields.One2many('construction.real.recipe.line', 'recipe_id', string='Materiales',
                               copy=True)
    piece_ids = fields.One2many('construction.real.recipe.piece', 'recipe_id', string='Piezas',
                                copy=True)
    versus_ids = fields.One2many('construction.recipe.versus', 'recipe_id', string='Versus')
    amount_planned = fields.Monetary(string='Planificado', compute='_compute_amounts',
                                     currency_field='currency_id')
    amount_real = fields.Monetary(string='Real', compute='_compute_amounts',
                                  currency_field='currency_id')
    difference_pct = fields.Float(string='Diferencia %', compute='_compute_amounts')
    needs_authorization = fields.Boolean(
        string='Espera a la jefatura', compute='_compute_amounts',
        help='El costo real supera al planificado en más del umbral de Ajustes.')
    authorized_by = fields.Many2one('res.users', string='Autorizado por', readonly=True,
                                    tracking=True)
    authorized_on = fields.Datetime(string='Autorizado el', readonly=True)
    comparison_html = fields.Html(string='Planificado y real', compute='_compute_comparison_html',
                                  sanitize=False)

    @api.depends('task_id.display_name')
    def _compute_name(self):
        for recipe in self:
            recipe.name = self.env._('Metrado · %s', recipe.task_id.display_name or '')

    @api.depends('task_id')
    def _compute_template_id(self):
        for recipe in self:
            task = recipe.task_id
            typology = task.construction_space_task_id.construction_typology_id
            recipe.template_id = typology.module_line_ids.filtered(
                lambda m: m.code == task.construction_module_code)[:1] or recipe.template_id

    # ------------------------------------------------------------------
    # Planificado frente a real
    # ------------------------------------------------------------------
    def _planned_materials(self):
        """{producto: cantidad} de la receta planificada del módulo."""
        self.ensure_one()
        planned = {}
        for material in self.template_id.material_ids:
            planned[material.product_id] = planned.get(material.product_id, 0.0) + material.qty
        if not planned and self.template_id.bom_id:
            for line in self.template_id.bom_id.bom_line_ids:
                planned[line.product_id] = planned.get(line.product_id, 0.0) + line.product_qty
        return planned

    def _real_materials(self):
        self.ensure_one()
        real = {}
        for line in self.line_ids:
            real[line.product_id] = real.get(line.product_id, 0.0) + line.qty
        return real

    def _comparison(self):
        """[(producto, planificado, real, costo unitario)] material por material."""
        self.ensure_one()
        planned, real = self._planned_materials(), self._real_materials()
        rows = []
        for product in sorted(set(planned) | set(real), key=lambda p: p.display_name or ''):
            rows.append((product, planned.get(product, 0.0), real.get(product, 0.0),
                         product.standard_price))
        return rows

    @api.depends('line_ids.qty', 'line_ids.product_id', 'template_id', 'authorized_by')
    def _compute_amounts(self):
        for recipe in self:
            rows = recipe._comparison() if recipe.task_id else []
            planned = sum(p * cost for _prod, p, _r, cost in rows)
            real = sum(r * cost for _prod, _p, r, cost in rows)
            recipe.amount_planned = planned
            recipe.amount_real = real
            recipe.difference_pct = (real - planned) / planned * 100.0 if planned else 0.0
            threshold = (recipe.company_id or self.env.company).construction_real_recipe_threshold
            recipe.needs_authorization = bool(planned) and recipe.difference_pct > threshold \
                and not recipe.authorized_by

    @api.depends('line_ids.qty', 'line_ids.product_id', 'template_id')
    def _compute_comparison_html(self):
        for recipe in self:
            rows = recipe._comparison() if recipe.task_id else []
            if not rows:
                recipe.comparison_html = False
                continue
            currency = recipe.currency_id or self.env.company.currency_id
            body = Markup('').join(Markup(
                '<tr class="%s"><td>%s</td><td class="text-end">%s</td><td class="text-end">%s</td>'
                '<td class="text-end">%s</td><td class="text-end">%s</td></tr>') % (
                'table-warning' if round(real - planned, 4) else '', product.display_name,
                round(planned, 4), round(real, 4), round(real - planned, 4),
                currency.format((real - planned) * cost))
                for product, planned, real, cost in rows)
            recipe.comparison_html = Markup(
                '<table class="table table-sm o_construction_real_recipe"><thead><tr><th>%s</th>'
                '<th class="text-end">%s</th><th class="text-end">%s</th><th class="text-end">%s'
                '</th><th class="text-end">%s</th></tr></thead><tbody>%s</tbody></table>') % (
                self.env._('Material'), self.env._('Planificado'), self.env._('Real'),
                self.env._('Diferencia'), self.env._('Diferencia S/'), body)

    # ------------------------------------------------------------------
    # Flujo
    # ------------------------------------------------------------------
    def action_confirm(self):
        """Confirma la receta real: actualiza la lista de materiales del
        producto del módulo y registra las diferencias."""
        for recipe in self:
            if not recipe.line_ids:
                raise UserError(self.env._('El metrado %s no tiene materiales.', recipe.name))
            recipe.state = 'confirmed'
            recipe._register_versus()
            recipe._update_module_bom()
            if recipe.needs_authorization:
                recipe.message_post(body=self.env._(
                    'El costo real supera al planificado en %s %%: la orden de fabricación espera '
                    'la autorización de la jefatura de proyectos.', round(recipe.difference_pct, 2)))
        return True

    def action_draft(self):
        self.filtered(lambda r: r.state == 'confirmed').write(
            {'state': 'draft', 'authorized_by': False, 'authorized_on': False})

    def action_authorize(self):
        if not self.env.user.has_groups(PROJECT_HEAD_GROUPS):
            raise UserError(self.env._('Autoriza la jefatura de proyectos.'))
        self.write({'authorized_by': self.env.user.id, 'authorized_on': fields.Datetime.now()})
        for recipe in self:
            recipe.message_post(body=self.env._(
                'Autorizado: la orden de fabricación puede seguir con %s %% sobre lo '
                'planificado.', round(recipe.difference_pct, 2)))

    def _register_versus(self):
        """Toda diferencia queda registrada, haya pedido autorización o no."""
        self.ensure_one()
        self.versus_ids.unlink()
        self.env['construction.recipe.versus'].sudo().create([{
            'recipe_id': self.id, 'product_id': product.id, 'qty_planned': planned,
            'qty_real': real, 'cost_unit': cost,
        } for product, planned, real, cost in self._comparison()])

    def _update_module_bom(self):
        """La receta real pasa a la lista de materiales del producto del módulo."""
        self.ensure_one()
        product = self.template_id.product_id
        if not product:
            return
        Bom = self.env['mrp.bom'].sudo()
        bom = Bom.search([('product_id', '=', product.id)], limit=1)
        # Paquete 1.10, M110-02: como la lista del producto de módulo, solo las
        # etapas que consume la orden; la planta de la lista se conserva.
        company = self.template_id.typology_id.company_id or self.env.company
        codes, picking_type = self.env['construction.typology.module'] \
            ._construction_module_bom_values(company)
        lines = [Command.clear()] + [Command.create({
            'product_id': line.product_id.id, 'product_qty': line.qty,
            'product_uom_id': (line.uom_id or line.product_id.uom_id).id,
            'construction_consumption_stage': line.stage or False}) for line in self.line_ids
            if not line.stage or line.stage in codes]
        if bom:
            bom.bom_line_ids = lines
        else:
            Bom.create({'product_tmpl_id': product.product_tmpl_id.id, 'product_id': product.id,
                        'product_qty': 1.0, 'bom_line_ids': lines[1:],
                        'picking_type_id': picking_type.id or False})

    @api.model
    def _blocking_for(self, tasks):
        """Metrados confirmados de esas tareas que esperan a la jefatura."""
        return self.search([('task_id', 'in', tasks.ids), ('state', '=', 'confirmed')]).filtered(
            'needs_authorization')


class ConstructionRealRecipeLine(models.Model):
    _name = 'construction.real.recipe.line'
    _description = 'Material de la receta real'
    _order = 'recipe_id, sequence, id'

    recipe_id = fields.Many2one('construction.real.recipe', required=True, ondelete='cascade',
                                index=True)
    company_id = fields.Many2one(related='recipe_id.company_id', store=True, index=True)
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    qty = fields.Float(string='Cantidad', digits=(16, 6), required=True)
    uom_id = fields.Many2one('uom.uom', string='Unidad')
    stage = fields.Selection(stage_selection, string='Sub etapa')


class ConstructionRealRecipePiece(models.Model):
    _name = 'construction.real.recipe.piece'
    _description = 'Pieza de la receta real'
    _order = 'recipe_id, sequence, id'

    recipe_id = fields.Many2one('construction.real.recipe', required=True, ondelete='cascade',
                                index=True)
    sequence = fields.Integer(default=10)
    qty = fields.Float(string='Cantidad', digits=(16, 2), default=1.0)
    length_mm = fields.Float(string='Largo (mm)')
    width_mm = fields.Float(string='Ancho (mm)')
    piece_type = fields.Char(string='Tipo de pieza')
    color = fields.Char(string='Color o descripción')


class ConstructionRecipeVersus(models.Model):
    """Presupuestado frente a real por módulo y material (M17-20), con suma
    hacia mueble, ambiente, piso y obra en el pivote."""
    _name = 'construction.recipe.versus'
    _description = 'Versus del metrado'
    _order = 'recipe_id, product_id'

    recipe_id = fields.Many2one('construction.real.recipe', required=True, ondelete='cascade',
                                index=True)
    company_id = fields.Many2one(related='recipe_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='recipe_id.currency_id')
    project_id = fields.Many2one(related='recipe_id.project_id', store=True, string='Obra')
    floor_task_id = fields.Many2one(related='recipe_id.floor_task_id', store=True, string='Piso')
    apartment_task_id = fields.Many2one(related='recipe_id.apartment_task_id', store=True,
                                        string='Departamento')
    space_task_id = fields.Many2one(related='recipe_id.space_task_id', store=True,
                                    string='Ambiente')
    task_id = fields.Many2one(related='recipe_id.task_id', store=True, string='Módulo o mueble')
    product_id = fields.Many2one('product.product', string='Material')
    qty_planned = fields.Float(string='Presupuestado', digits=(16, 4))
    qty_real = fields.Float(string='Real', digits=(16, 4))
    qty_difference = fields.Float(string='Diferencia', digits=(16, 4),
                                  compute='_compute_difference', store=True)
    cost_unit = fields.Float(string='Costo unitario', digits='Product Price')
    amount_planned = fields.Monetary(string='Presupuestado S/', compute='_compute_difference',
                                     store=True)
    amount_real = fields.Monetary(string='Real S/', compute='_compute_difference', store=True)
    amount_difference = fields.Monetary(string='Diferencia S/', compute='_compute_difference',
                                        store=True)

    @api.depends('qty_planned', 'qty_real', 'cost_unit')
    def _compute_difference(self):
        for row in self:
            row.qty_difference = row.qty_real - row.qty_planned
            row.amount_planned = row.qty_planned * row.cost_unit
            row.amount_real = row.qty_real * row.cost_unit
            row.amount_difference = row.amount_real - row.amount_planned


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_real_recipe_threshold = fields.Float(
        string='Umbral del metrado (%)', default=10.0,
        help='Si el costo real del mueble supera al planificado en más de este porcentaje, la '
             'orden de fabricación espera la autorización de la jefatura de proyectos.')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_real_recipe_threshold = fields.Float(
        related='company_id.construction_real_recipe_threshold', readonly=False)


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def action_confirm(self):
        """La OF de un módulo con metrado sobre el umbral espera a la jefatura.
        Con el exceso en la orden (paquete 1.9, M19-04) lo controla la orden
        misma y este bloqueo no aplica."""
        if self.env.context.get('construction_skip_recipe_authorization'):
            return super().action_confirm()
        recipes = self.env['construction.real.recipe'].sudo()._blocking_for(
            self.construction_module_task_ids)
        if recipes:
            # Paquete 1.10, M110-03: la orden del asistente lleva todos los
            # módulos de la tipología y el piso; el mensaje nombra el módulo y
            # su departamento para que la jefatura lo autorice sin rehacerla.
            raise UserError(self.env._(
                'La orden de fabricación espera la autorización de la jefatura de proyectos: el '
                'costo real de %s supera al planificado en más del umbral.',
                ', '.join('%s (%s)' % (recipe.task_id.name, recipe.apartment_task_id.name)
                          if recipe.apartment_task_id else recipe.name
                          for recipe in recipes)))
        return super().action_confirm()
