# -*- coding: utf-8 -*-
"""Receta y plan (requerimiento CREVAL v1.0, capítulo 6).

* 6.1 Forma de cálculo de la línea de receta y del plan: cantidad por unidad
  (como siempre), cuadrilla ÷ rendimiento, porcentaje de la mano de obra de la
  partida (las herramientas manuales «%MO» del análisis de precio unitario) o
  porcentaje del costo directo de un grupo de partidas. Las líneas por
  porcentaje se recalculan cuando cambia su base y no se compran.
* 6.2 Fuente del análisis de precio unitario de la obra: Work Items de la venta
  o libro Excel.
* 6.4 Tabla de equivalencias de unidades para las importaciones.
* 6.5 Partidas en otra moneda: precio en dólares (por ejemplo) con su
  conversión a la moneda de la obra al tipo de cambio de la fecha del plan."""
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .common import DRIVER_TYPES, norm

CALC_METHODS = [
    ('qty', 'Cantidad por unidad'),
    ('crew', 'Cuadrilla ÷ rendimiento'),
    ('pct_labor', '% de la mano de obra'),
    ('pct_group', '% del costo directo de un grupo de partidas'),
]
PCT_METHODS = ('pct_labor', 'pct_group')
CALC_SCOPES = [
    ('parent', 'Partidas del mismo nivel superior'),
    ('level_1', 'Partidas del mismo nivel 1'),
    ('project', 'Toda la obra'),
]
APU_SOURCES = [
    ('work_item', 'Work Items de la venta de la obra'),
    ('excel', 'Libro Excel'),
]


class ConstructionUomAlias(models.Model):
    """Cómo escribe un presupuesto o un APU cada unidad: «UND», «Und», «und»;
    «GLB», «glb»; «M» y «ML» (6.4)."""
    _name = 'construction.uom.alias'
    _description = 'Equivalencia de unidad en las importaciones'
    _order = 'name'

    name = fields.Char(string='Escrito como', required=True)
    uom_id = fields.Many2one('uom.uom', string='Unidad', required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Compañía',
                                 help='Vacía: vale para todas las compañías.')

    _name_company_unique = models.UniqueIndex(
        '(lower(name), COALESCE(company_id, 0))',
        'Esa forma de escribir la unidad ya tiene su equivalencia.')

    @api.model
    def _find(self, text, company=None):
        """Unidad equivalente a ``text`` (sin mayúsculas, tildes ni espacios
        de más), primero en la tabla y luego por nombre."""
        key = norm(text)
        if not key:
            return self.env['uom.uom']
        company = company or self.env.company
        for alias in self.search(['|', ('company_id', '=', False),
                                  ('company_id', '=', company.id)], order='company_id'):
            if norm(alias.name) == key:
                return alias.uom_id
        return self.env['uom.uom']


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_workday_hours = fields.Float(
        string='Horas de la jornada', default=8.0,
        help='Para «cuadrilla ÷ rendimiento» en horas: personas × horas ÷ rendimiento.')


class ProjectProject(models.Model):
    _inherit = 'project.project'

    construction_apu_source = fields.Selection(
        APU_SOURCES, string='Fuente del análisis de precio unitario', default='work_item',
        help='Work Items de la venta: el APU vive en la cotización y llega al plan con una nueva '
             'versión. Libro Excel: el plan se genera desde las recetas importadas del libro.')


class ConstructionExecutionTemplateLine(models.Model):
    _inherit = 'construction.execution.template.line'

    calc_method = fields.Selection(
        CALC_METHODS, string='Forma de cálculo', required=True, default='qty',
        help='Cantidad por unidad: la cantidad escrita. Cuadrilla ÷ rendimiento: personas × '
             'horas de la jornada (si la unidad es la hora) ÷ rendimiento. % de la mano de obra: '
             'el porcentaje del costo de la mano de obra de la receta (herramientas «%MO»). % del '
             'costo directo: el porcentaje del costo de las partidas del grupo.')
    calc_pct = fields.Float(string='Porcentaje', digits=(16, 4))
    calc_scope = fields.Selection(
        CALC_SCOPES, string='Grupo de partidas', default='parent',
        help='Solo con «% del costo directo de un grupo de partidas».')
    line_currency_id = fields.Many2one(
        'res.currency', string='Moneda del costo',
        help='Vacía: la de la compañía. Un costo en dólares se convierte al tipo de cambio de la '
             'fecha del plan.')

    def _construction_calc_qty(self, vals):
        """Cantidad por unidad según la forma de cálculo (cuadrilla ÷
        rendimiento o el porcentaje como fracción)."""
        method = vals.get('calc_method', self.calc_method if self else 'qty')
        if method == 'crew':
            productivity = vals.get('productivity', self.productivity if self else 0.0)
            if not productivity:
                return vals
            crew = vals.get('crew_size', self.crew_size if self else 1.0)
            uom_id = vals.get('product_uom_id', self.product_uom_id.id if self else False)
            hour = self.env.ref('uom.product_uom_hour', raise_if_not_found=False)
            company = self.env['construction.execution.template'].browse(
                vals.get('template_id')).company_id if vals.get('template_id') else \
                self.company_id
            hours = (company or self.env.company).construction_workday_hours or 8.0 \
                if hour and uom_id == hour.id else 1.0
            return dict(vals, qty=crew * hours / productivity)
        if method in PCT_METHODS:
            pct = vals.get('calc_pct', self.calc_pct if self else 0.0)
            return dict(vals, qty=pct / 100.0)
        return vals

    @api.onchange('calc_method', 'crew_size', 'productivity', 'product_uom_id', 'calc_pct')
    def _onchange_calc_method(self):
        values = self._construction_calc_qty({})
        if 'qty' in values:
            self.qty = values['qty']

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self.browse()._construction_calc_qty(vals) for vals in vals_list])

    def write(self, vals):
        if {'calc_method', 'crew_size', 'productivity', 'product_uom_id', 'calc_pct'} & set(vals):
            for line in self:
                super(ConstructionExecutionTemplateLine, line).write(
                    line._construction_calc_qty(vals))
            return True
        return super().write(vals)

    amount_unit = fields.Float(recursive=True)

    @api.depends('qty', 'price_unit', 'product_id.standard_price', 'calc_method', 'calc_pct',
                 'line_currency_id', 'template_id.line_ids.amount_unit')
    def _compute_amount_unit(self):
        pct_lines = self.filtered(lambda l: l.calc_method == 'pct_labor')
        for line in self - pct_lines:
            price = line.price_unit or line.product_id.standard_price
            line.amount_unit = line.qty * line._construction_to_company(price)
        for line in pct_lines:
            line.amount_unit = line.calc_pct / 100.0 * line._construction_labor_base()

    def _construction_to_company(self, amount, date=None):
        """``amount`` en la moneda del costo → moneda de la compañía."""
        self.ensure_one()
        company = self.company_id or self.env.company
        currency = self.line_currency_id
        if not currency or currency == company.currency_id or not amount:
            return amount
        return currency._convert(amount, company.currency_id, company,
                                 date or fields.Date.context_today(self))

    def _construction_labor_base(self):
        """Costo por unidad de la mano de obra (personal propio y contrata) de
        la receta, sin las líneas por porcentaje."""
        self.ensure_one()
        labor = self.template_id.line_ids.filtered(
            lambda l: l.resource_type in DRIVER_TYPES and l.calc_method not in PCT_METHODS)
        return sum(l.qty * l._construction_to_company(
            l.price_unit or l.product_id.standard_price) for l in labor)

    @api.constrains('calc_method', 'calc_pct', 'productivity')
    def _check_calc(self):
        for line in self:
            if line.calc_method in PCT_METHODS and line.calc_pct <= 0:
                raise ValidationError(self.env._(
                    'La línea por porcentaje de la receta %s necesita su porcentaje.',
                    line.template_id.display_name))
            if line.calc_method == 'crew' and line.productivity <= 0:
                raise ValidationError(self.env._(
                    '«Cuadrilla ÷ rendimiento» en la receta %s necesita el rendimiento.',
                    line.template_id.display_name))


class ConstructionResourcePlanLine(models.Model):
    _inherit = 'construction.resource.plan.line'

    calc_method = fields.Selection(CALC_METHODS, string='Forma de cálculo', default='qty',
                                   copy=True)
    calc_pct = fields.Float(string='Porcentaje', digits=(16, 4), copy=True)
    calc_scope = fields.Selection(CALC_SCOPES, string='Grupo de partidas', copy=True)
    price_currency_id = fields.Many2one(
        'res.currency', string='Moneda del costo', copy=True,
        help='Vacía: la de la obra. El control se lleva en la moneda de la obra.')
    price_unit_currency = fields.Float(
        string='Costo en su moneda', digits='Product Price', copy=True,
        help='Costo unitario en la moneda del costo; el costo planificado es su conversión al '
             'tipo de cambio de la fecha del plan.')
    is_foreign_currency = fields.Boolean(compute='_compute_is_foreign_currency', store=True)

    @api.depends('price_currency_id', 'currency_id')
    def _compute_is_foreign_currency(self):
        for line in self:
            line.is_foreign_currency = bool(line.price_currency_id) \
                and line.price_currency_id != line.currency_id

    def _construction_plan_rate_date(self):
        self.ensure_one()
        return self.plan_id.date_start or fields.Date.context_today(self)

    def _construction_convert_price(self, vals):
        """Con un costo en otra moneda, el costo planificado es su conversión
        a la moneda de la obra (fecha del plan)."""
        currency = self.env['res.currency'].browse(vals.get('price_currency_id')) \
            if 'price_currency_id' in vals else self.price_currency_id
        price = vals.get('price_unit_currency', self.price_unit_currency if self else 0.0)
        plan = self.env['construction.resource.plan'].browse(vals.get('plan_id')) \
            if vals.get('plan_id') else self.plan_id
        company = plan.company_id or self.env.company
        if not currency or currency == company.currency_id or not price:
            return vals
        date = plan.date_start or fields.Date.context_today(self)
        return dict(vals, price_unit_planned=currency._convert(
            price, company.currency_id, company, date))

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self.browse()._construction_convert_price(vals) for vals in vals_list]
        lines = super().create(vals_list)
        if not self.env.context.get('construction_pct_sync'):
            lines._construction_recompute_pct()
        return lines

    def write(self, vals):
        if {'price_currency_id', 'price_unit_currency'} & set(vals):
            for line in self:
                super(ConstructionResourcePlanLine, line).write(
                    line._construction_convert_price(vals))
            res = True
        else:
            res = super().write(vals)
        if not self.env.context.get('construction_pct_sync') and \
                {'qty_planned', 'price_unit_planned', 'calc_pct', 'calc_method',
                 'price_unit_currency'} & set(vals):
            self._construction_recompute_pct()
        return res

    def _construction_recompute_pct(self):
        """Las líneas por porcentaje toman su base: la mano de obra de la misma
        partida o el costo directo del grupo de partidas."""
        plans = self.plan_id
        if not plans:
            return
        Line = self.env['construction.resource.plan.line']
        pct_lines = Line.search([('plan_id', 'in', plans.ids),
                                 ('calc_method', 'in', PCT_METHODS)])
        for line in pct_lines:
            base_domain = [('plan_id', '=', line.plan_id.id),
                           ('calc_method', 'not in', PCT_METHODS)]
            task = line.task_id
            if line.calc_method == 'pct_labor':
                base_domain += [('task_id', '=', task.id), ('resource_type', 'in', DRIVER_TYPES)]
            elif line.calc_scope == 'parent':
                base_domain += [('task_id.parent_id', '=', task.parent_id.id)]
            elif line.calc_scope == 'level_1':
                base_domain += [('level_1_id', '=', line.level_1_id.id)]
            # Cantidad = el porcentaje como fracción; costo = la base: el monto
            # es exactamente el porcentaje de la base («%MO» del APU).
            base = sum(Line.search(base_domain).mapped('amount_planned'))
            values = {'qty_planned': line.calc_pct / 100.0, 'price_unit_planned': base}
            if line.product_uom_id.compare(values['qty_planned'], line.qty_planned) or \
                    line.currency_id.compare_amounts(values['price_unit_planned'],
                                                     line.price_unit_planned):
                line.with_context(construction_plan_force=True,
                                  construction_pct_sync=True).write(values)

