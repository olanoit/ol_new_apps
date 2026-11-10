# -*- coding: utf-8 -*-
"""Control semanal del presupuesto de mano de obra (paquete 1.19, M119-02).

Una fila por obra, sub etapa, modalidad (y contrata, si es de contrata) y
semana de lunes a domingo, contra el presupuesto de M119-01:

* meta de avance de la semana (en la semana en curso, la de los días
  transcurridos) y avance validado, con sus acumulados;
* persona-días presupuestados y reales: en el personal propio, los jornales
  ejecutados de su marcación; en la contrata, las horas marcadas ÷ la jornada
  completa del horario de obra, repartidas entre las sub etapas que avanzó esa
  semana en proporción a lo que justifica su avance (D5);
* rendimiento real frente al exigido del presupuesto, y personal esperado;
* soles presupuestados y reales (propio: persona-días × jornal; contrata:
  avance × tarifa) y el presupuesto del avance (lo que el presupuesto asigna al
  trabajo hecho), con sus acumulados.

Avisos: «Exceso de personal», con su propia banda (corrección 1 del 1.19);
«Atraso»; y «Sobre el presupuesto», con la banda del rendimiento, que se compara
con el avance y no con el calendario; se marca la primera semana en que ocurre.

Las filas se rehacen con «Actualizar» y con la acción programada de los
jornales ejecutados: el informe no se escribe a mano.
"""
from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


def _monday(day):
    return day - timedelta(days=day.weekday())


class ConstructionLaborWeeklyControl(models.Model):
    _name = 'construction.labor.weekly.control'
    _description = 'Control semanal de mano de obra'
    _order = 'project_id, stage_sequence, mode, partner_id, week_start'
    _check_company_auto = True

    project_id = fields.Many2one('project.project', string='Obra', required=True, index=True,
                                 ondelete='cascade', check_company=True)
    company_id = fields.Many2one(related='project_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='project_id.company_id.currency_id', string='Moneda')
    budget_id = fields.Many2one('construction.labor.budget', string='Presupuesto',
                                required=True, index=True, ondelete='cascade')
    stage_id = fields.Many2one(related='budget_id.stage_id', store=True, string='Sub etapa')
    stage_sequence = fields.Integer(related='budget_id.sequence', store=True)
    mode = fields.Selection(related='budget_id.mode', store=True, string='Modalidad')
    partner_id = fields.Many2one('res.partner', string='Contrata', index=True)
    week_start = fields.Date(string='Semana (lunes)', required=True, index=True)
    week_label = fields.Char(string='Semana', compute='_compute_week_label', store=True)
    in_progress = fields.Boolean(string='Semana en curso')
    single_activity_id = fields.Many2one(
        'construction.labor.activity', string='Actividad',
        help='La actividad de la fila, si es una sola: su rendimiento real se puede usar como '
             'medido.')
    # Avance.
    target = fields.Float(string='Meta', digits=(16, 2))
    progress = fields.Float(string='Avance validado', digits=(16, 2))
    progress_diff = fields.Float(string='Diferencia', digits=(16, 2))
    target_cumulative = fields.Float(string='Meta acumulada', digits=(16, 2))
    progress_cumulative = fields.Float(string='Avance acumulado', digits=(16, 2))
    # Personas.
    person_days_budget = fields.Float(string='Persona-días presupuestados', digits=(16, 3))
    person_days_real = fields.Float(string='Persona-días reales', digits=(16, 3))
    persons = fields.Integer(string='Personas que marcaron')
    required_productivity = fields.Float(string='Rendimiento exigido', digits=(16, 4))
    real_productivity = fields.Float(string='Rendimiento real', digits=(16, 4))
    productivity_deviation = fields.Float(string='Desviación del rendimiento (%)',
                                          digits=(16, 1))
    expected_persons = fields.Float(string='Personal esperado', digits=(16, 1))
    # Soles.
    amount_budget = fields.Monetary(string='Soles presupuestados', currency_field='currency_id')
    amount_real = fields.Monetary(string='Soles reales', currency_field='currency_id')
    progress_person_days = fields.Float(string='Persona-días del avance', digits=(16, 3),
                                        help='Lo que el presupuesto asigna al trabajo hecho.')
    progress_amount = fields.Monetary(string='Soles del avance', currency_field='currency_id')
    person_days_real_cumulative = fields.Float(string='Persona-días reales acumulados',
                                               digits=(16, 3))
    amount_real_cumulative = fields.Monetary(string='Soles reales acumulados',
                                             currency_field='currency_id')
    progress_person_days_cumulative = fields.Float(string='Persona-días del avance acumulados',
                                                   digits=(16, 3))
    progress_amount_cumulative = fields.Monetary(string='Soles del avance acumulados',
                                                 currency_field='currency_id')
    person_days_budget_cumulative = fields.Float(string='Persona-días presupuestados acumulados',
                                                 digits=(16, 3))
    amount_budget_cumulative = fields.Monetary(string='Soles presupuestados acumulados',
                                               currency_field='currency_id')
    # Avisos.
    excess_staff = fields.Boolean(string='Exceso de personal')
    delay = fields.Boolean(string='Atraso')
    over_budget = fields.Boolean(string='Sobre el presupuesto')
    first_over_budget = fields.Boolean(string='Primera semana sobre el presupuesto')
    missing_productivity = fields.Boolean(string='Sin rendimiento')
    warning = fields.Char(string='Aviso')

    @api.depends('week_start', 'budget_id.week_ids.week_start')
    def _compute_week_label(self):
        for row in self:
            week = row.budget_id.week_ids.filtered(lambda w: w.week_start == row.week_start)[:1]
            row.week_label = 'S%s · %s' % (week.number, row.week_start.strftime('%d/%m')) \
                if week and row.week_start else (row.week_start and
                                                 row.week_start.strftime('%d/%m') or '')

    # ------------------------------------------------------------------
    # Datos reales
    # ------------------------------------------------------------------
    @api.model
    def _validated_progress(self, project, activities, date_from, date_to):
        """Avance validado de la obra: ``{(modalidad, contrata, actividad,
        lunes): cantidad}``."""
        # sudo: el informe lee los avances validados de la obra para
        # comparar; no los cambia.
        progress_sudo = self.env['construction.task.progress'].sudo().search([
            ('project_id', '=', project.id), ('state', '=', 'validated'),
            ('activity_id', 'in', activities.ids), ('date', '>=', date_from),
            ('date', '<=', date_to)])
        result = defaultdict(float)
        for progress in progress_sudo:
            mode = 'own' if progress.plan_line_id.resource_type == 'labor' else 'contract'
            partner = progress.partner_id.commercial_partner_id if mode == 'contract' \
                else self.env['res.partner']
            result[(mode, partner.id, progress.activity_id.id, _monday(progress.date))] += \
                progress.qty
        return result

    @api.model
    def _own_person_days(self, project, date_from, date_to):
        """Jornales ejecutados del personal propio: ``{(sub etapa, lunes):
        (persona-días, {personas})}``."""
        # sudo: los jornales vienen de la marcación (RR. HH.).
        days_sudo = self.env['construction.crew.day'].sudo().search([
            ('project_id', '=', project.id), ('kind', '=', 'executed'),
            ('date', '>=', date_from), ('date', '<=', date_to)])
        result = defaultdict(lambda: [0.0, set()])
        for day in days_sudo:
            key = (day.stage, _monday(day.date))
            result[key][0] += day.days
            if day.employee_id:
                result[key][1].add(day.employee_id.id)
        return result

    @api.model
    def _contract_person_days(self, project, date_from, date_to):
        """Marcación de las contratas en la obra: ``{(contrata, lunes):
        (persona-días, {personas})}`` con las horas ÷ la jornada completa."""
        company = project.company_id or self.env.company
        full_day = company._construction_full_day_hours() or 8.0
        # sudo: la marcación de las contratas es de la sede (RR. HH.).
        attendances_sudo = self.env['construction.contractor.attendance'].sudo().search([
            ('project_id', '=', project.id), ('date', '>=', date_from),
            ('date', '<=', date_to), ('check_out', '!=', False)])
        result = defaultdict(lambda: [0.0, set()])
        for attendance in attendances_sudo:
            hours = (attendance.check_out - attendance.check_in).total_seconds() / 3600.0
            key = (attendance.partner_id.commercial_partner_id.id, _monday(attendance.date))
            result[key][0] += hours / full_day
            result[key][1].add(attendance.worker_id.id)
        return result

    # ------------------------------------------------------------------
    # Armado del informe
    # ------------------------------------------------------------------
    @api.model
    def _construction_refresh(self, projects):
        """Rehace las filas de ``projects`` desde su presupuesto, su avance
        validado y su marcación."""
        today = fields.Date.context_today(self)
        values = []
        for project in projects:
            budgets = project.construction_labor_budget_ids.filtered(
                lambda b: b.date_from and b.date_to and b.week_ids)
            if not budgets:
                continue
            date_from = min(budgets.mapped('date_from'))
            date_to = max(max(budgets.mapped('date_to')), today)
            activities = budgets.line_ids.activity_id
            progress = self._validated_progress(project, activities, date_from, date_to)
            own_days = self._own_person_days(project, date_from, date_to)
            contract_days = self._contract_person_days(project, date_from, date_to)
            # D5: persona-días de cada contrata repartidos entre los
            # presupuestos que avanzó en la semana, por lo que justifica su
            # avance.
            justified = defaultdict(float)
            required = {}
            for budget in budgets:
                result = budget._result()
                required[budget] = {item['key'].activity_id.id: item['required_productivity']
                                    for item in result['lines']}
                if budget.mode != 'contract':
                    continue
                for (mode, partner, activity, week), qty in progress.items():
                    if mode == 'contract' and required[budget].get(activity):
                        justified[(partner, week, budget.id)] += \
                            qty / required[budget][activity]
            for budget in budgets:
                values += self._budget_rows(project, budget, required[budget], progress,
                                            own_days, contract_days, justified, today)
        self.search([('project_id', 'in', projects.ids)]).unlink()
        return self.create(values)

    def _budget_rows(self, project, budget, required, progress, own_days, contract_days,
                     justified, today):
        lines = budget.line_ids
        activity_ids = lines.activity_id.ids
        band = (budget.band or 0.0) / 100.0
        # Corrección 1 del 1.19: «Exceso de personal» con su propia banda.
        excess_band = (budget.excess_band or 0.0) / 100.0
        company = project.company_id or self.env.company
        single = lines.activity_id if len(lines) == 1 else self.env['construction.labor.activity']
        missing = any(not required.get(activity_id) for activity_id in activity_ids)
        weeks = budget.week_ids.sorted('week_start')
        last_week = _monday(today)
        if budget.mode == 'contract':
            partners = sorted({partner for (mode, partner, activity, _week) in progress
                               if mode == 'contract' and activity in activity_ids and partner})
            partners = partners or [False]
        else:
            partners = [False]
        rows = []
        for partner in partners:
            share_partner = 1.0 / len(partners)
            cumulative = defaultdict(float)
            first_over_done = False
            for week in weeks:
                if week.week_start > last_week:
                    break
                current = week.week_start <= today <= week.week_start + timedelta(days=6)
                share = week.share
                if current:
                    end = min(today, budget.date_to)
                    start = max(week.week_start, budget.date_from)
                    share = company._construction_equivalent_days(start, end) \
                        / budget.equivalent_days if budget.equivalent_days and end >= start \
                        else 0.0
                target = budget.quantity * share * share_partner
                done = {activity_id: progress.get(
                    (budget.mode, partner if budget.mode == 'contract' else False, activity_id,
                     week.week_start), 0.0) for activity_id in activity_ids}
                done_qty = sum(done.values())
                progress_pd = sum(qty / required[activity_id] for activity_id, qty in done.items()
                                  if required.get(activity_id))
                if budget.mode == 'own':
                    real_pd, persons = own_days.get((budget.stage, week.week_start), (0.0, set()))
                    persons = len(persons)
                    amount_real = real_pd * budget.daily_wage
                    progress_amount = progress_pd * budget.daily_wage
                else:
                    total_pd, people = contract_days.get((partner, week.week_start), (0.0, set()))
                    weights = {key[2]: value for key, value in justified.items()
                               if key[0] == partner and key[1] == week.week_start}
                    weight_total = sum(weights.values())
                    part = weights.get(budget.id, 0.0) / weight_total if weight_total else (
                        1.0 if not weights else 0.0)
                    real_pd = total_pd * part
                    persons = len(people) if part else 0
                    rates = {line.activity_id.id: line.rate for line in lines}
                    amount_real = sum(qty * rates.get(activity_id, 0.0)
                                      for activity_id, qty in done.items())
                    progress_amount = amount_real
                budget_pd = budget.person_days_budget * share * share_partner
                budget_amount = budget.amount * share * share_partner
                cumulative['target'] += target
                cumulative['progress'] += done_qty
                cumulative['real_pd'] += real_pd
                cumulative['amount_real'] += amount_real
                cumulative['progress_pd'] += progress_pd
                cumulative['progress_amount'] += progress_amount
                cumulative['budget_pd'] += budget_pd
                cumulative['budget_amount'] += budget_amount
                exigido = (budget.quantity / (budget.persons * budget.equivalent_days)
                           if budget.persons and budget.equivalent_days else 0.0)
                if single and required.get(single.id):
                    exigido = required[single.id]
                real = done_qty / real_pd if real_pd and not missing else 0.0
                deviation = (real / exigido - 1) * 100 if real and exigido else 0.0
                week_days = week.equivalent_days
                expected = (done_qty / exigido / week_days) if exigido and week_days \
                    and not missing else 0.0
                excess = bool(real) and float_compare(
                    real, exigido * (1 - excess_band), precision_digits=4) < 0
                delay = float_compare(cumulative['progress'], cumulative['target'],
                                      precision_digits=2) < 0
                over = float_compare(cumulative['real_pd'],
                                     cumulative['progress_pd'] * (1 + band),
                                     precision_digits=2) > 0 or (
                    budget.mode == 'own' and float_compare(
                        cumulative['amount_real'], cumulative['progress_amount'] * (1 + band),
                        precision_digits=2) > 0)
                first_over = over and not first_over_done
                first_over_done = first_over_done or over
                messages = []
                if excess:
                    messages.append(self.env._('Exceso de personal'))
                if delay:
                    messages.append(self.env._('Atraso de %s',
                                               round(cumulative['target'] -
                                                     cumulative['progress'], 2)))
                if over:
                    messages.append(self.env._('Sobre el presupuesto') + (
                        self.env._(' (desde esta semana)') if first_over else ''))
                if missing:
                    messages.append(self.env._('Sin rendimiento: no se calcula el rendimiento '
                                               'real'))
                rows.append({
                    'project_id': project.id, 'budget_id': budget.id,
                    'partner_id': partner or False, 'week_start': week.week_start,
                    'in_progress': current, 'single_activity_id': single.id,
                    'target': target, 'progress': done_qty, 'progress_diff': done_qty - target,
                    'target_cumulative': cumulative['target'],
                    'progress_cumulative': cumulative['progress'],
                    'person_days_budget': budget_pd, 'person_days_real': real_pd,
                    'persons': persons, 'required_productivity': exigido,
                    'real_productivity': real, 'productivity_deviation': deviation,
                    'expected_persons': expected,
                    'amount_budget': budget_amount, 'amount_real': amount_real,
                    'progress_person_days': progress_pd, 'progress_amount': progress_amount,
                    'person_days_real_cumulative': cumulative['real_pd'],
                    'amount_real_cumulative': cumulative['amount_real'],
                    'progress_person_days_cumulative': cumulative['progress_pd'],
                    'progress_amount_cumulative': cumulative['progress_amount'],
                    'person_days_budget_cumulative': cumulative['budget_pd'],
                    'amount_budget_cumulative': cumulative['budget_amount'],
                    'excess_staff': excess, 'delay': delay, 'over_budget': over,
                    'first_over_budget': first_over, 'missing_productivity': missing,
                    'warning': ' · '.join(messages) or False,
                })
        return rows

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def action_use_as_measured(self):
        """M119-01, punto 10: el rendimiento real de la fila pasa a la tabla
        de la obra con origen «Medido»."""
        for row in self:
            if not row.single_activity_id or not row.real_productivity:
                raise UserError(self.env._(
                    'Solo una fila con una actividad y rendimiento real se usa como rendimiento '
                    'medido.'))
            row.project_id._construction_productivity_write(
                {row.single_activity_id: (round(row.real_productivity, 4), self.env._(
                    'Medido en el control semanal, %s', row.week_label))}, origin='measured')
        return True

    def action_open_details(self):
        """Avances y marcaciones de la fila."""
        self.ensure_one()
        end = self.week_start + timedelta(days=6)
        domain = [('project_id', '=', self.project_id.id), ('date', '>=', self.week_start),
                  ('date', '<=', end)]
        if self.mode == 'contract':
            return {
                'type': 'ir.actions.act_window',
                'name': self.env._('Marcaciones de la contrata'),
                'res_model': 'construction.contractor.attendance', 'view_mode': 'list',
                'domain': domain + ([('partner_id', 'child_of', self.partner_id.id)]
                                    if self.partner_id else []),
            }
        return {
            'type': 'ir.actions.act_window', 'name': self.env._('Jornales ejecutados'),
            'res_model': 'construction.crew.day', 'view_mode': 'list',
            'domain': domain + [('kind', '=', 'executed'), ('stage', '=', self.budget_id.stage)],
        }

    @api.model
    def _cron_refresh(self):
        projects = self.env['construction.labor.budget'].search([]).project_id
        self._construction_refresh(projects)


class ProjectProject(models.Model):
    _inherit = 'project.project'

    def action_open_construction_labor_control(self):
        """«Control semanal de mano de obra» de la obra (se rehace al abrir)."""
        self.ensure_one()
        self.env['construction.labor.weekly.control']._construction_refresh(self)
        action = self.env['ir.actions.act_window']._for_xml_id(
            'al_construction_attendance.action_construction_labor_weekly_control')
        action['domain'] = [('project_id', '=', self.id)]
        action['name'] = self.env._('Control semanal · %s', self.display_name)
        return action
