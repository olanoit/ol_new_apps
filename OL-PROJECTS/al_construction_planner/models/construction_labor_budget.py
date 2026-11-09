# -*- coding: utf-8 -*-
"""Presupuesto de mano de obra por sub etapa (paquete 1.19, M119-01).

El rendimiento de una actividad es cuántas unidades del driver hace una
persona en un día completo del horario de obra (persona-día). Con él, la
cantidad y el plazo de cada sub etapa salen:

* persona-días necesarios = Σ cantidad ÷ rendimiento;
* personas exactas = persona-días necesarios ÷ días equivalentes del plazo;
* personas = el menor entero con el que el rendimiento exigido no pasa el
  rendimiento + banda: ⌈personas exactas ÷ (1 + banda)⌉;
* rendimiento exigido = rendimiento × personas exactas ÷ personas; por debajo
  de rendimiento − banda, «Capacidad ociosa»;
* persona-días presupuestados = personas × días equivalentes;
* soles: personal propio, persona-días presupuestados × jornal; contrata,
  cantidad × tarifa (se le paga por avance);
* metas: por día completo, cantidad ÷ días equivalentes; por semana, la meta
  del día × los días equivalentes de la semana.

Cada obra tiene su tabla de rendimientos, que nace con el rendimiento inicial
del catálogo. Las sub etapas que llevan presupuesto las marca el catálogo de
etapas (no el código).
"""
import math
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_round


PRODUCTIVITY_ORIGINS = [
    ('initial', 'Inicial'),
    ('adjusted', 'Ajustado'),
    ('measured', 'Medido'),
]
BUDGET_MODES = [('own', 'Personal propio'), ('contract', 'Contrata')]
DEFAULT_BAND = 10.0
# Precisión del cálculo (las metas se muestran con 2 decimales).
PRECISION = 6


def budget_mode(mode):
    """Personal propio o contrata (la de solo mano de obra y la a todo costo
    se controlan igual: por avance)."""
    return 'own' if mode in (False, None, 'own') else 'contract'


def compute_budget(lines, equivalent_days, band_pct, daily_wage=0.0, mode='own'):
    """Presupuesto de una sub etapa.

    :param lines: ``[{'key', 'qty', 'productivity', 'rate'}]`` por actividad.
    :param band_pct: banda del rendimiento en % (10 = ±10 %).
    :return: diccionario con las cifras de la sub etapa y ``lines`` con el
        rendimiento exigido, las persona-días y el costo de cada actividad.
    """
    band = (band_pct or 0.0) / 100.0
    needed = sum(line['qty'] / line['productivity'] for line in lines
                 if line['productivity'] > 0 and line['qty'])
    missing = [line['key'] for line in lines if line['qty'] and line['productivity'] <= 0]
    result = {
        'person_days_needed': float_round(needed, precision_digits=PRECISION),
        'persons_exact': 0.0, 'persons': 0, 'factor': 0.0, 'deviation_pct': 0.0,
        'person_days_budget': 0.0, 'amount': 0.0, 'idle': False, 'load_pct': 0.0,
        'missing': missing, 'lines': [],
    }
    exact = needed / equivalent_days if equivalent_days > 0 else 0.0
    persons = 0
    if exact > 0:
        # Tolerancia: 4.4 ÷ 1.1 no debe dar 5 por el redondeo binario.
        persons = max(1, math.ceil(float_round(exact / (1 + band), precision_digits=9)))
    factor = exact / persons if persons else 0.0
    result.update({
        'persons_exact': float_round(exact, precision_digits=PRECISION),
        'persons': persons,
        'factor': factor,
        'deviation_pct': float_round((factor - 1) * 100, precision_digits=4) if persons else 0.0,
        'person_days_budget': float_round(persons * equivalent_days, precision_digits=PRECISION),
        'idle': bool(persons) and float_compare(factor, 1 - band, precision_digits=6) < 0,
        'load_pct': float_round(factor * 100, precision_digits=2) if persons else 0.0,
    })
    amount = 0.0
    for line in lines:
        productivity = line['productivity']
        required = productivity * factor if productivity > 0 and factor else 0.0
        person_days = line['qty'] / required if required else 0.0
        if mode == 'own':
            unit_cost = daily_wage / required if required else 0.0
        else:
            unit_cost = line.get('rate') or 0.0
        line_amount = line['qty'] * unit_cost
        amount += line_amount
        result['lines'].append(dict(
            line, required_productivity=float_round(required, precision_digits=PRECISION),
            person_days=float_round(person_days, precision_digits=PRECISION),
            unit_cost=float_round(unit_cost, precision_digits=PRECISION),
            amount=line_amount))
    result['amount'] = amount
    return result


def monday(day):
    return day - timedelta(days=day.weekday())


class ConstructionStage(models.Model):
    _inherit = 'construction.stage'

    labor_budget = fields.Boolean(
        string='Lleva presupuesto de mano de obra', compute='_compute_labor_budget',
        store=True, readonly=False,
        help='La sub etapa tiene presupuesto de personas y soles con el rendimiento de sus '
             'actividades y su plazo. Por defecto, las de ejecución en campo que no consumen en la '
             'producción en taller (la instalación, no el armado).')

    @api.depends('kind', 'production_consumption')
    def _compute_labor_budget(self):
        for stage in self:
            stage.labor_budget = stage.kind == 'field' and not stage.production_consumption


class ConstructionProjectProductivity(models.Model):
    """Rendimientos de la obra: uno por actividad, para contrata y para
    personal propio (decisión del 08-nov)."""
    _name = 'construction.project.productivity'
    _description = 'Rendimiento de la obra'
    _order = 'project_id, stage, activity_id'
    _check_company_auto = True

    project_id = fields.Many2one('project.project', string='Obra', required=True, index=True,
                                 ondelete='cascade', check_company=True)
    company_id = fields.Many2one(related='project_id.company_id', store=True, index=True)
    # La actividad puede ser compartida entre compañías.
    activity_id = fields.Many2one('construction.labor.activity', string='Actividad',
                                  required=True, ondelete='cascade')
    stage = fields.Selection(related='activity_id.stage', store=True, string='Sub etapa')
    uom_id = fields.Many2one(related='activity_id.uom_id', string='Unidad')
    productivity = fields.Float(string='Rendimiento', digits=(16, 4),
                                help='Unidades del driver por persona-día.')
    initial_productivity = fields.Float(string='Valor inicial', digits=(16, 4), readonly=True)
    origin = fields.Selection(PRODUCTIVITY_ORIGINS, string='Origen', default='initial',
                              required=True)
    reason = fields.Char(string='Motivo del cambio')
    date = fields.Date(string='Fecha', default=fields.Date.context_today)
    user_id = fields.Many2one('res.users', string='Usuario', default=lambda self: self.env.user)

    _activity_unique = models.Constraint(
        'unique(project_id, activity_id)', 'La obra ya tiene el rendimiento de esa actividad.')

    def write(self, vals):
        """Cambiar el rendimiento pide el motivo y deja el origen «Ajustado»
        (salvo el rendimiento medido, que trae su origen)."""
        if 'productivity' in vals and not self.env.context.get('construction_productivity_sync'):
            changed = self.filtered(lambda rec: float_compare(
                rec.productivity, vals['productivity'] or 0.0, precision_digits=4))
            if changed and not vals.get('reason'):
                raise UserError(self.env._('Escriba el motivo del cambio del rendimiento.'))
            if changed:
                vals = dict(vals, date=fields.Date.context_today(self), user_id=self.env.uid)
                vals.setdefault('origin', 'adjusted')
        return super().write(vals)


class ConstructionLaborBudget(models.Model):
    _name = 'construction.labor.budget'
    _description = 'Presupuesto de mano de obra de la sub etapa'
    _order = 'project_id, sequence, id'
    _check_company_auto = True

    project_id = fields.Many2one('project.project', string='Obra', required=True, index=True,
                                 ondelete='cascade', check_company=True)
    company_id = fields.Many2one(related='project_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='project_id.company_id.currency_id', string='Moneda')
    sequence = fields.Integer(string='Orden', default=10)
    stage_id = fields.Many2one('construction.stage', string='Sub etapa', required=True,
                               ondelete='restrict')
    stage = fields.Char(related='stage_id.code', store=True, string='Código de la sub etapa')
    mode = fields.Selection(BUDGET_MODES, string='Modalidad', required=True, default='own')
    date_start = fields.Date(string='Inicio', help='Del programa por piso (PROGRAMA).')
    date_end = fields.Date(string='Fin', help='Del programa por piso (PROGRAMA).')
    date_start_adjusted = fields.Date(string='Inicio ajustado')
    date_end_adjusted = fields.Date(string='Fin ajustado')
    adjust_reason = fields.Char(string='Motivo del ajuste')
    date_from = fields.Date(string='Desde', compute='_compute_budget', store=True)
    date_to = fields.Date(string='Hasta', compute='_compute_budget', store=True)
    band = fields.Float(string='Banda del rendimiento (%)', default=DEFAULT_BAND)
    daily_wage = fields.Monetary(string='Jornal', currency_field='currency_id',
                                 help='Del rol de la sub etapa en MO PROPIA.')
    line_ids = fields.One2many('construction.labor.budget.line', 'budget_id',
                               string='Actividades', copy=True)
    week_ids = fields.One2many('construction.labor.budget.week', 'budget_id',
                               string='Metas por semana')
    equivalent_days = fields.Float(string='Días equivalentes', digits=(16, 4),
                                   compute='_compute_budget', store=True)
    quantity = fields.Float(string='Cantidad', digits=(16, 2), compute='_compute_budget',
                            store=True)
    person_days_needed = fields.Float(string='Persona-días necesarios', digits=(16, 2),
                                      compute='_compute_budget', store=True)
    persons_exact = fields.Float(string='Personas exactas', digits=(16, 2),
                                 compute='_compute_budget', store=True)
    persons = fields.Integer(string='Personas', compute='_compute_budget', store=True)
    deviation_pct = fields.Float(string='Desviación del rendimiento (%)', digits=(16, 1),
                                 compute='_compute_budget', store=True)
    person_days_budget = fields.Float(string='Persona-días presupuestados', digits=(16, 2),
                                      compute='_compute_budget', store=True)
    amount = fields.Monetary(string='Presupuesto', currency_field='currency_id',
                             compute='_compute_budget', store=True)
    warning = fields.Char(string='Aviso', compute='_compute_budget', store=True)

    _stage_mode_unique = models.Constraint(
        'unique(project_id, stage_id, mode)',
        'La obra ya tiene el presupuesto de esa sub etapa y modalidad.')

    @api.constrains('date_start_adjusted', 'date_end_adjusted', 'adjust_reason')
    def _check_adjust_reason(self):
        for budget in self:
            if (budget.date_start_adjusted or budget.date_end_adjusted) \
                    and not budget.adjust_reason:
                raise ValidationError(self.env._(
                    'Escriba el motivo del ajuste del plazo de %s.', budget.stage_id.display_name))
            if budget.date_from and budget.date_to and budget.date_to < budget.date_from:
                raise ValidationError(self.env._('El fin del plazo es anterior a su inicio.'))

    @api.depends('date_start', 'date_end', 'date_start_adjusted', 'date_end_adjusted', 'band',
                 'daily_wage', 'mode', 'line_ids.quantity', 'line_ids.productivity',
                 'line_ids.rate', 'project_id.company_id.construction_site_calendar_id')
    def _compute_budget(self):
        for budget in self:
            budget.date_from = budget.date_start_adjusted or budget.date_start
            budget.date_to = budget.date_end_adjusted or budget.date_end
            company = budget.project_id.company_id or self.env.company
            days = company._construction_equivalent_days(budget.date_from, budget.date_to) \
                if budget.date_from and budget.date_to else 0.0
            result = compute_budget(budget._calc_lines(), days, budget.band, budget.daily_wage,
                                    budget.mode)
            budget.equivalent_days = days
            budget.quantity = sum(budget.line_ids.mapped('quantity'))
            budget.person_days_needed = result['person_days_needed']
            budget.persons_exact = result['persons_exact']
            budget.persons = result['persons']
            budget.deviation_pct = result['deviation_pct']
            budget.person_days_budget = result['person_days_budget']
            budget.amount = result['amount']
            budget.warning = budget._warning_text(result)

    def _calc_lines(self):
        self.ensure_one()
        return [{'key': line, 'qty': line.quantity, 'productivity': line.productivity,
                 'rate': line.rate} for line in self.line_ids]

    def _result(self):
        """Cálculo completo (con el rendimiento exigido de cada actividad)."""
        self.ensure_one()
        return compute_budget(self._calc_lines(), self.equivalent_days, self.band,
                              self.daily_wage, self.mode)

    def _warning_text(self, result):
        messages = []
        if result['idle']:
            messages.append(self.env._(
                'Capacidad ociosa: %(persons)s persona(s) al %(load)s %%',
                persons=result['persons'], load=round(result['load_pct'])))
        if result['missing']:
            messages.append(self.env._(
                'Sin rendimiento: %s',
                ', '.join(line.activity_id.display_name for line in result['missing'])))
        return ' · '.join(messages) or False

    def _construction_rebuild_weeks(self):
        """Metas por semana (de lunes a domingo): días equivalentes de la
        semana dentro del plazo, persona-días y soles con su acumulado."""
        Week = self.env['construction.labor.budget.week']
        for budget in self:
            budget.week_ids.unlink()
            if not budget.date_from or not budget.date_to or not budget.equivalent_days:
                continue
            company = budget.project_id.company_id or self.env.company
            values, start, number = [], monday(budget.date_from), 1
            cumulative_days = 0.0
            while start <= budget.date_to:
                first = max(start, budget.date_from)
                last = min(start + timedelta(days=6), budget.date_to)
                days = company._construction_equivalent_days(first, last)
                cumulative_days += days
                share = days / budget.equivalent_days
                values.append({
                    'budget_id': budget.id, 'number': number, 'week_start': start,
                    'equivalent_days': days, 'share': share,
                    'cumulative_share': cumulative_days / budget.equivalent_days,
                })
                start += timedelta(days=7)
                number += 1
            Week.create(values)

    @api.model_create_multi
    def create(self, vals_list):
        budgets = super().create(vals_list)
        budgets._construction_rebuild_weeks()
        return budgets

    def write(self, vals):
        result = super().write(vals)
        if {'date_start', 'date_end', 'date_start_adjusted', 'date_end_adjusted'} & set(vals):
            self._construction_rebuild_weeks()
        return result

    def _target(self, line, week):
        """Meta de avance de ``line`` en ``week``: su cantidad por la parte
        de la semana en el plazo."""
        return line.quantity * week.share

    def _required_productivity(self, activity):
        """Rendimiento exigido de ``activity`` en el presupuesto (0 sin
        rendimiento)."""
        self.ensure_one()
        result = self._result()
        for item in result['lines']:
            if item['key'].activity_id == activity:
                return item['required_productivity']
        return 0.0


class ConstructionLaborBudgetLine(models.Model):
    _name = 'construction.labor.budget.line'
    _description = 'Actividad del presupuesto de mano de obra'
    _order = 'budget_id, id'

    budget_id = fields.Many2one('construction.labor.budget', string='Presupuesto',
                                required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one(related='budget_id.company_id', store=True)
    currency_id = fields.Many2one(related='budget_id.currency_id')
    activity_id = fields.Many2one('construction.labor.activity', string='Actividad',
                                  required=True, ondelete='restrict')
    uom_id = fields.Many2one(related='activity_id.uom_id', string='Unidad')
    quantity = fields.Float(string='Cantidad', digits=(16, 4))
    productivity = fields.Float(string='Rendimiento', digits=(16, 4),
                                help='El de la tabla de la obra cuando se armó el presupuesto.')
    rate = fields.Float(string='Tarifa', digits='Product Price',
                        help='Contrata: se le paga por avance.')
    required_productivity = fields.Float(string='Rendimiento exigido', digits=(16, 4),
                                         compute='_compute_figures')
    person_days = fields.Float(string='Persona-días', digits=(16, 2),
                               compute='_compute_figures')
    unit_cost = fields.Float(string='Costo unitario', digits='Product Price',
                             compute='_compute_figures')
    amount = fields.Monetary(string='Presupuesto', currency_field='currency_id',
                             compute='_compute_figures')

    @api.depends('quantity', 'productivity', 'rate', 'budget_id.equivalent_days',
                 'budget_id.band', 'budget_id.daily_wage', 'budget_id.mode')
    def _compute_figures(self):
        results = {budget: budget._result() for budget in self.budget_id}
        for line in self:
            item = next((item for item in results[line.budget_id]['lines']
                         if item['key'] == line), None) if line.budget_id in results else None
            line.required_productivity = item['required_productivity'] if item else 0.0
            line.person_days = item['person_days'] if item else 0.0
            line.unit_cost = item['unit_cost'] if item else 0.0
            line.amount = item['amount'] if item else 0.0


class ConstructionLaborBudgetWeek(models.Model):
    _name = 'construction.labor.budget.week'
    _description = 'Semana del presupuesto de mano de obra'
    _order = 'budget_id, week_start'

    budget_id = fields.Many2one('construction.labor.budget', string='Presupuesto',
                                required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one(related='budget_id.company_id', store=True)
    currency_id = fields.Many2one(related='budget_id.currency_id')
    project_id = fields.Many2one(related='budget_id.project_id', store=True)
    stage_id = fields.Many2one(related='budget_id.stage_id', store=True)
    mode = fields.Selection(related='budget_id.mode', store=True)
    number = fields.Integer(string='Semana')
    week_start = fields.Date(string='Lunes', required=True)
    equivalent_days = fields.Float(string='Días equivalentes', digits=(16, 4))
    # Sin redondeo: las metas de las semanas suman la cantidad.
    share = fields.Float(string='Parte del plazo')
    cumulative_share = fields.Float(string='Parte acumulada')
    person_days = fields.Float(string='Persona-días', digits=(16, 2),
                               compute='_compute_amounts')
    amount = fields.Monetary(string='Soles', currency_field='currency_id',
                             compute='_compute_amounts')
    person_days_cumulative = fields.Float(string='Persona-días acumulados', digits=(16, 2),
                                          compute='_compute_amounts')
    amount_cumulative = fields.Monetary(string='Soles acumulados', currency_field='currency_id',
                                        compute='_compute_amounts')

    @api.depends('share', 'cumulative_share', 'budget_id.person_days_budget',
                 'budget_id.amount')
    def _compute_amounts(self):
        for week in self:
            budget = week.budget_id
            week.person_days = budget.person_days_budget * week.share
            week.amount = budget.amount * week.share
            week.person_days_cumulative = budget.person_days_budget * week.cumulative_share
            week.amount_cumulative = budget.amount * week.cumulative_share


class ConstructionResourcePlanLine(models.Model):
    _inherit = 'construction.resource.plan.line'

    construction_person_days = fields.Float(
        string='Persona-días', digits=(16, 2),
        help='Cantidad ÷ rendimiento exigido del presupuesto de mano de obra de la obra.')


class ProjectProject(models.Model):
    _inherit = 'project.project'

    construction_productivity_ids = fields.One2many(
        'construction.project.productivity', 'project_id', string='Rendimientos')
    construction_labor_budget_ids = fields.One2many(
        'construction.labor.budget', 'project_id', string='Presupuesto de mano de obra')
    construction_productivity_count = fields.Integer(
        compute='_compute_construction_labor_counts')
    construction_labor_budget_count = fields.Integer(
        compute='_compute_construction_labor_counts')

    def _compute_construction_labor_counts(self):
        for project in self:
            project.construction_productivity_count = len(project.construction_productivity_ids)
            project.construction_labor_budget_count = len(project.construction_labor_budget_ids)

    def _construction_productivity_ensure(self, activities):
        """Filas de la tabla de rendimientos para las actividades de la obra
        que aún no la tienen, con el rendimiento inicial del catálogo."""
        self.ensure_one()
        existing = self.construction_productivity_ids.activity_id
        values = [{'project_id': self.id, 'activity_id': activity.id,
                   'productivity': activity.productivity,
                   'initial_productivity': activity.productivity, 'origin': 'initial'}
                  for activity in activities - existing]
        return self.env['construction.project.productivity'].create(values)

    def _construction_productivity_map(self):
        """{actividad: rendimiento de la obra}."""
        self.ensure_one()
        return {row.activity_id: row.productivity for row in self.construction_productivity_ids}

    def _construction_productivity_write(self, values, origin='adjusted'):
        """Escribe en la tabla de la obra ``{actividad: (rendimiento,
        motivo)}``: el envío de la hoja (con su motivo) o el rendimiento
        medido del control semanal."""
        self.ensure_one()
        self._construction_productivity_ensure(
            self.env['construction.labor.activity'].union(*values.keys()))
        rows = {row.activity_id: row for row in self.construction_productivity_ids}
        for activity, (productivity, reason) in values.items():
            row = rows[activity]
            if not float_compare(row.productivity, productivity or 0.0, precision_digits=4):
                continue
            row.write({'productivity': productivity, 'reason': reason or row.reason,
                       'origin': origin})

    def _construction_labor_budget_apply(self, payload):
        """Escribe lo que trae el envío de la hoja: la tabla de rendimientos
        (con su motivo) y un presupuesto por sub etapa y modalidad, con sus
        actividades. Un plazo ajustado en la obra se conserva si la hoja no
        trae otro.

        :param payload: ``{'productivity': [{'code', 'value', 'reason'}],
            'band', 'activities': [{'code', 'stage', 'qty', 'productivity',
            'rate', 'mode'}], 'blocks': [{'stage_code', 'stage_label', 'mode',
            'start', 'end', 'start_adjusted', 'end_adjusted', 'reason',
            'daily_wage'}]}``
        """
        self.ensure_one()
        company = self.company_id or self.env.company
        Activity = self.env['construction.labor.activity']
        activities = {}

        def activity_of(code):
            if code not in activities:
                activities[code] = Activity.search([
                    ('code', '=', code), ('company_id', 'in', (company.id, False))],
                    order='company_id', limit=1)
            return activities[code]

        changes = {}
        for item in payload.get('productivity') or []:
            activity = activity_of(item['code'])
            if not activity:
                continue
            self._construction_productivity_ensure(activity)
            if item.get('value') not in ('', None, False):
                changes[activity] = (float(item['value']), item.get('reason') or self.env._(
                    'Hoja de planificación'))
        if changes:
            self._construction_productivity_write(changes)
        Stage = self.env['construction.stage']
        Budget = self.env['construction.labor.budget']
        kept = Budget
        for sequence, block in enumerate(payload.get('blocks') or [], start=1):
            stage = Stage.search([('code', '=', block['stage_code'])], limit=1)
            if not stage:
                continue
            mode = budget_mode(block.get('mode'))
            lines = []
            for item in payload.get('activities') or []:
                activity = activity_of(item['code'])
                if not activity or item.get('stage') != block.get('stage_label') \
                        or budget_mode(item.get('mode')) != mode or not item.get('qty'):
                    continue
                self._construction_productivity_ensure(activity)
                lines.append((0, 0, {'activity_id': activity.id, 'quantity': item['qty'],
                                     'productivity': item.get('productivity') or 0.0,
                                     'rate': item.get('rate') or 0.0}))
            values = {
                'sequence': sequence, 'date_start': block.get('start') or False,
                'date_end': block.get('end') or False,
                'band': payload.get('band') if payload.get('band') is not None else DEFAULT_BAND,
                'daily_wage': block.get('daily_wage') or 0.0 if mode == 'own' else 0.0,
                'line_ids': [(5, 0, 0)] + lines,
            }
            if block.get('start_adjusted') or block.get('end_adjusted'):
                values.update({
                    'date_start_adjusted': block.get('start_adjusted') or False,
                    'date_end_adjusted': block.get('end_adjusted') or False,
                    'adjust_reason': block.get('reason') or self.env._('Hoja de planificación'),
                })
            budget = self._construction_labor_budget_for(stage.code, mode)
            if budget:
                budget.write(values)
            else:
                budget = Budget.create(dict(values, project_id=self.id, stage_id=stage.id,
                                            mode=mode))
            kept |= budget
        (self.construction_labor_budget_ids - kept).unlink()
        return kept

    def _construction_labor_budget_for(self, stage_code, mode):
        self.ensure_one()
        return self.construction_labor_budget_ids.filtered(
            lambda budget: budget.stage == stage_code and budget.mode == budget_mode(mode))[:1]

    def action_open_construction_productivity(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': self.env._('Rendimientos de la obra'),
            'res_model': 'construction.project.productivity', 'view_mode': 'list',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_open_construction_labor_budget(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Presupuesto de mano de obra'),
            'res_model': 'construction.labor.budget', 'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id, 'create': False},
        }

