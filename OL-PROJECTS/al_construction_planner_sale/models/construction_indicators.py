# -*- coding: utf-8 -*-
"""Indicadores de la obra (paquete 7 de CREVAL, CR-60 y CR-59).

Un solo cálculo para la ficha de la obra y la cartera del Inicio: así las
cifras de una obra son las mismas en las dos pantallas. Cada indicador tiene
su presupuestado (fila de arriba) y su ejecutado (fila de abajo):

============================  ===============================  ==============================
Indicador                     Presupuestado                    Ejecutado
============================  ===============================  ==============================
Venta a hoy                   valorización prevista acumulada  ingreso contable (CR-62)
Costo a hoy                   costo programado (valor plan.)   costo ejecutado contable
Margen                        venta − costo                    ingreso − costo
Avance físico                 avance programado a hoy          avance por partida (CR-61)
Valorizado                    valorización prevista ÷ venta    valorizaciones confirmadas ÷ venta
Por valorizar                 (avance − valorizado) × venta    (avance − valorizado) × venta
Valorización del mes          meta aprobada (CR-63)            valorizado con corte en el mes
Costo del mes                 costo programado del mes         costo contable del mes
Al cierre · venta             venta vigente (con CR-64)        la misma
Al cierre · margen %          (venta − costo meta) ÷ venta     (venta − costo final est.) ÷ venta
============================  ===============================  ==============================

Valor ganado (EV), índices CPI = EV ÷ costo ejecutado y SPI = EV ÷ costo
programado, costo final estimado = costo ejecutado + (costo meta − EV) ÷ CPI
y fin estimado = inicio + duración ÷ SPI, como en la guía PMBOK."""
import math
from collections import defaultdict
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date

from odoo.addons.al_construction_planner.models.common import can_see_amounts

from .construction_accounting import EXPENSE_TYPES
from .construction_schedule_report import CONFIRMED_VALUATION_STATES

#: Indicadores con dos filas (presupuestado y ejecutado), por bloque.
INDICATOR_BLOCKS = [
    ('today', 'A hoy', ['sale', 'cost', 'margin', 'margin_pct']),
    ('progress', 'Avance y valorización', ['physical', 'valued', 'to_value']),
    ('month', 'Mes', ['month_valuation', 'month_cost', 'month_margin']),
    ('close', 'Al cierre', ['close_sale', 'close_margin_pct']),
]
#: Claves que son porcentaje o índice: se ven sin el grupo «Ve montos».
RATIO_KEYS = frozenset({'margin_pct', 'physical', 'valued', 'close_margin_pct', 'cpi', 'spi',
                        'progress', 'progress_planned', 'valued_pct', 'light'})
#: Posiciones y proporciones de la línea de plazo y del gráfico de avance.
CHART_POSITION_KEYS = frozenset({'pos', 'value', 'to_value_pct'})
#: Enteros que no son montos: identificadores, días.
KEPT_INTEGER_KEYS = frozenset({'id', 'project_id', 'plan_id', 'days_late', 'duration'})
#: Puntos máximos de las curvas de la ficha (una por semana).
MAX_CHART_POINTS = 40


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_index_green = fields.Float(
        string='Índices en verde desde', default=0.95, digits=(4, 2),
        help='Índice de costo (CPI) y de plazo (SPI) desde el que la obra va en verde.')
    construction_index_amber = fields.Float(
        string='Índices en ámbar desde', default=0.90, digits=(4, 2),
        help='Debajo de este índice la obra va en rojo; entre este y el verde, en ámbar.')
    construction_margin_green = fields.Float(
        string='Margen en verde desde', default=10.0,
        help='Margen previsto al cierre (%) desde el que la obra va en verde.')
    construction_margin_amber = fields.Float(
        string='Margen en ámbar desde', default=5.0,
        help='Debajo de este margen (%) la obra va en rojo.')

    def _construction_light(self, value, kind):
        """'green', 'amber' o 'red' de un índice (``kind='index'``) o de un
        margen en % (``kind='margin'``); ``False`` sin valor."""
        self.ensure_one()
        if value is False or value is None:
            return False
        green, amber = (self.construction_index_green, self.construction_index_amber) \
            if kind == 'index' else (self.construction_margin_green,
                                      self.construction_margin_amber)
        if value >= green:
            return 'green'
        return 'amber' if value >= amber else 'red'


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_index_green = fields.Float(
        related='company_id.construction_index_green', readonly=False)
    construction_index_amber = fields.Float(
        related='company_id.construction_index_amber', readonly=False)
    construction_margin_green = fields.Float(
        related='company_id.construction_margin_green', readonly=False)
    construction_margin_amber = fields.Float(
        related='company_id.construction_margin_amber', readonly=False)


class ProjectProject(models.Model):
    _inherit = 'project.project'

    # ------------------------------------------------------------------
    # Cálculo común
    # ------------------------------------------------------------------
    def _construction_indicator_dates(self, plan):
        """(inicio, fin del contrato) de la obra: los de la obra o, sin ellos,
        los del plan."""
        self.ensure_one()
        return (self.date_start or plan.date_start, self.date or plan.date_end)

    def _construction_sale_total(self, day):
        """Venta vigente: la orden del contrato sin impuestos, con las líneas
        de los cambios cobrables (CR-64), en la moneda de la compañía."""
        self.ensure_one()
        return sum(line._construction_price(day)
                   for line in self.construction_sale_order_id.order_line
                   if not line.display_type)

    @api.model
    def _construction_estimated_end(self, start, end, spi):
        """Fin estimado = inicio + duración ÷ SPI, en días enteros hacia
        arriba (un día empezado cuenta)."""
        if not (start and end and spi):
            return False
        return start + timedelta(days=math.ceil(round((end - start).days / spi, 6)))

    def _construction_indicators(self, month=None, today=None, plan=None):
        """Indicadores de la obra a ``today`` y del mes ``month`` (el de hoy
        por defecto). Montos en la moneda de la compañía, sin IGV.

        :return: ``{'budget': {...}, 'executed': {...}, 'cpi', 'spi', ...}``
            o ``{}`` si la obra no tiene plan.
        """
        self.ensure_one()
        today = today or fields.Date.context_today(self)
        first = (month or today).replace(day=1)
        last = first + relativedelta(day=31)
        plan = plan or self._construction_current_plan()
        if not plan:
            return {}
        company = self.company_id or plan.company_id
        currency = company.currency_id
        start, end = self._construction_indicator_dates(plan)
        # Costo programado (valor planificado) por día y costo meta.
        cache = {}
        cost_by_day = self._construction_planned_by_day({False: plan.line_ids}, cache)[False]
        planned_cost = sum(v for d, v in cost_by_day.items() if d <= today)
        month_cost_planned = sum(v for d, v in cost_by_day.items() if first <= d <= last)
        bac = sum(line.amount_budgeted or line.amount_planned for line in plan.line_ids)
        # Venta vigente y avance programado (precio de cada partida × su
        # avance previsto).
        sale_total = self._construction_sale_total(today) if self.construction_sale_order_id \
            else 0.0
        lines_by_partida = self._construction_lines_by_partida(plan) \
            if self.construction_sale_order_id else {}
        planned = self._construction_planned_by_day(lines_by_partida, cache)
        price_total = done_price = 0.0
        for sale_line, by_day in planned.items():
            total = sum(by_day.values())
            price = sale_line._construction_price(today)
            price_total += price
            if total:
                done_price += price * sum(v for d, v in by_day.items() if d <= today) / total
        progress_planned = done_price / price_total if price_total else 0.0
        # Valorización prevista: las partidas del calendario (P-21) × (venta ÷
        # partidas), así cierra en la venta.
        forecast_rows = []
        if self.construction_sale_order_id:
            try:
                forecast_rows = self._construction_get_valuation_forecast()['rows']
            except UserError:
                forecast_rows = []
        partidas = sum(line._construction_price(today) for line in self._construction_partida_lines()) \
            if self.construction_sale_order_id else 0.0
        factor = sale_total / partidas if partidas else 1.0
        forecast_today = sum(r['amount'] for r in forecast_rows if r['cutoff'] <= today) * factor
        valued_planned = forecast_today / sale_total if sale_total else 0.0
        target, target_approved = (self._construction_valuation_target(first)
                                   if self.construction_sale_order_id else (0.0, False))
        # Ejecutado.
        accounting = self._construction_accounting_amounts(date_to=today)
        accounting_month = self._construction_accounting_amounts(first, last)
        physical = self._construction_physical_values(today, plan)
        ev = physical['earned_value']
        valuations = self.env['construction.valuation'].search([
            ('project_id', '=', self.id), ('state', 'in', CONFIRMED_VALUATION_STATES)])
        valued_amount = sum(valuations.mapped('amount_confirmed'))
        month_valuation = sum(valuations.filtered(
            lambda v: first <= v.cutoff_date <= last).mapped('amount_confirmed'))
        valued_pct = valued_amount / sale_total if sale_total else 0.0
        ac = accounting['cost']
        cpi = ev / ac if ac else False
        spi = ev / planned_cost if planned_cost else False
        eac = ac + (bac - ev) / cpi if cpi else bac
        estimated_end = self._construction_estimated_end(start, end, spi)
        budget = {
            'sale': forecast_today,
            'cost': planned_cost,
            'margin': forecast_today - planned_cost,
            'margin_pct': (forecast_today - planned_cost) / forecast_today
            if forecast_today else False,
            'physical': progress_planned,
            'valued': valued_planned,
            'to_value': (progress_planned - valued_planned) * sale_total,
            'month_valuation': target,
            'month_cost': month_cost_planned,
            'month_margin': target - month_cost_planned,
            'close_sale': sale_total,
            'close_margin_pct': (sale_total - bac) / sale_total if sale_total else False,
        }
        executed = {
            'sale': accounting['income'],
            'cost': ac,
            'margin': accounting['income'] - ac,
            'margin_pct': (accounting['income'] - ac) / accounting['income']
            if accounting['income'] else False,
            'physical': physical['progress'],
            'valued': valued_pct,
            'to_value': (physical['progress'] - valued_pct) * sale_total,
            'month_valuation': month_valuation,
            'month_cost': accounting_month['cost'],
            'month_margin': month_valuation - accounting_month['cost'],
            'close_sale': sale_total,
            'close_margin_pct': (sale_total - eac) / sale_total if sale_total else False,
        }
        for values in (budget, executed):
            for key, value in values.items():
                if key not in RATIO_KEYS and value is not False:
                    values[key] = currency.round(value)
        lights = {
            'cpi': company._construction_light(cpi, 'index'),
            'spi': company._construction_light(spi, 'index'),
            'margin': company._construction_light(
                executed['close_margin_pct'] * 100 if executed['close_margin_pct'] is not False
                else False, 'margin'),
        }
        order = {'red': 0, 'amber': 1, 'green': 2}
        worst = min((light for light in lights.values() if light), key=order.get, default=False)
        return {
            'budget': budget,
            'executed': executed,
            'cpi': cpi,
            'spi': spi,
            'ev': currency.round(ev),
            'bac': currency.round(bac),
            'eac': currency.round(eac),
            'pv': currency.round(planned_cost),
            'target_approved': target_approved,
            'date_start': start,
            'date_end': end,
            'date_estimated_end': estimated_end,
            'days_late': (estimated_end - end).days if estimated_end and end else 0,
            'lights': lights,
            'light': worst,
            'month': first,
            'plan': plan,
            'physical_lines': physical['lines'],
            'forecast_rows': forecast_rows,
            'forecast_factor': factor,
            'cost_by_day': cost_by_day,
            'valuations': valuations,
        }


class ConstructionProjectIndicators(models.AbstractModel):
    """Ficha de indicadores de la obra (CR-60): acción cliente de una página."""
    _name = 'construction.project.indicators'
    _description = 'Ficha de indicadores de la obra'

    @api.model
    def _construction_project(self, project_id):
        project = self.env['project.project'].browse(project_id).exists()
        if not project or not project.is_construction_site:
            raise UserError(self.env._('La obra ya no existe.'))
        project.check_access('read')
        return project

    @api.model
    def _construction_strip(self, data):
        """Sin el grupo «Ve montos» quedan los avances, porcentajes, índices
        y fechas; los montos van en ``False``."""
        if can_see_amounts(self.env):
            return data

        def visit(value, key=None):
            if isinstance(value, dict):
                return {k: visit(v, k) for k, v in value.items()}
            if isinstance(value, list):
                return [visit(item, key) for item in value]
            if isinstance(value, (int, float)) and not isinstance(value, bool) \
                    and key not in RATIO_KEYS and key not in CHART_POSITION_KEYS \
                    and key not in KEPT_INTEGER_KEYS:
                return False
            return value
        return visit(data)

    @api.model
    def get_indicator_sheet(self, project_id, month=False):
        project = self._construction_project(project_id)
        today = fields.Date.context_today(self)
        month = fields.Date.to_date(month) if month else today
        # sudo: la ficha resume documentos de otras áreas (contabilidad,
        # inventario, compras, horas) de una obra que el usuario puede leer
        # (comprobado arriba); los montos se quitan a quien no los ve.
        project_sudo = project.sudo()
        data = project_sudo._construction_indicators(
            month, today, project_sudo._construction_portfolio_plan())
        if not data:
            return self._construction_strip({
                'project_id': project.id, 'name': project.display_name, 'empty': True})
        currency = (project.company_id or self.env.company).currency_id
        sheet = {
            'project_id': project.id,
            'name': project.display_name,
            'partner': project.partner_id.display_name or '',
            'is_favorite': project.is_favorite,
            'stage': project_sudo._construction_portfolio_stage(data['plan']),
            'plan_id': data['plan'].id,
            'currency_symbol': currency.symbol,
            'month': fields.Date.to_string(data['month']),
            'month_label': format_date(self.env, data['month'], date_format='MMMM yyyy'),
            'today': fields.Date.to_string(today),
            'budget': data['budget'],
            'executed': data['executed'],
            'cpi': data['cpi'],
            'spi': data['spi'],
            'lights': data['lights'],
            'light': data['light'],
            'target_approved': data['target_approved'],
            'close': {'bac': data['bac'], 'eac': data['eac']},
            'tracking': self._construction_tracking(project_sudo, data, today),
            'schedule': self._construction_timeline(data, today),
            'charts': self._construction_charts(project_sudo, data, today),
            'valuations': self._construction_valuation_rows(project_sudo, data),
            'specialties': self._construction_specialty_rows(project_sudo, data, today),
            'changes': self._construction_change_rows(project_sudo),
            'show_amounts': can_see_amounts(self.env),
        }
        return self._construction_strip(sheet)

    # ------------------------------------------------------------------
    # Bloques de la ficha
    # ------------------------------------------------------------------
    @api.model
    def _construction_invoices(self, project):
        order = project.construction_sale_order_id
        return order.invoice_ids.filtered(
            lambda m: m.state == 'posted' and m.move_type in ('out_invoice', 'out_refund'))

    @api.model
    def _construction_tracking(self, project, data, today):
        """Facturado, cobrado y por cobrar; comprometido y por gastar hasta el
        cierre; índices."""
        Report = self.env['construction.schedule.report']
        invoices = self._construction_invoices(project)
        invoiced = sum(invoices.mapped('amount_untaxed_signed'))
        collected = sum(sum(Report._construction_collections(invoice).values())
                        for invoice in invoices)
        executed_cost = data['executed']['cost']
        return {
            'invoiced': invoiced,
            'collected': collected,
            'receivable': invoiced - collected,
            'committed': data['plan'].amount_committed,
            'to_spend': max(data['eac'] - executed_cost, 0.0),
        }

    @api.model
    def _construction_timeline(self, data, today):
        start, end, estimated = data['date_start'], data['date_end'], data['date_estimated_end']
        dates = [d for d in (start, end, estimated, today) if d]
        first, last = (min(dates), max(dates)) if dates else (today, today)
        span = max((last - first).days, 1)

        def mark(day):
            return {'date': fields.Date.to_string(day),
                    'label': format_date(self.env, day, date_format='dd/MM/yy'),
                    'pos': round((day - first).days * 100.0 / span, 2)} if day else False
        return {
            'start': mark(start),
            'end': mark(end),
            'estimated_end': mark(estimated),
            'today': mark(today),
            'duration': (end - start).days if start and end else 0,
            'days_late': data['days_late'],
        }

    @api.model
    def _construction_chart_dates(self, start, until):
        """Fechas de las curvas: cada semana desde el inicio hasta ``until``,
        como mucho ``MAX_CHART_POINTS`` (se espacian si la obra es larga)."""
        if not start or until < start:
            return []
        weeks = (until - start).days // 7 + 1
        step = max(1, math.ceil(weeks / MAX_CHART_POINTS))
        dates = [start + timedelta(weeks=n) for n in range(0, weeks, step)]
        if dates[-1] != until:
            dates.append(until)
        return dates

    @api.model
    def _construction_charts(self, project, data, today):
        """«Avance físico contra valorizado» (en % de la venta) y curva S de
        costo (programado, valor ganado y ejecutado)."""
        start, end = data['date_start'], data['date_end']
        sale = data['budget']['close_sale'] or 0.0
        until = min(today, max(filter(None, [end, today])))
        dates = self._construction_chart_dates(start, until)
        physical, earned = [], []
        for day in dates[:-1]:
            values = project._construction_physical_values(day, data['plan'])
            physical.append(values['progress'])
            earned.append(values['earned_value'])
        if dates:
            physical.append(data['executed']['physical'])
            earned.append(data['ev'])
        # Valorizado: escalones en cada corte confirmado.
        steps, cumulative = [], 0.0
        for valuation in data['valuations'].sorted('cutoff_date'):
            cumulative += valuation.amount_confirmed
            steps.append({'date': fields.Date.to_string(valuation.cutoff_date),
                          'value': cumulative / sale if sale else 0.0})
        planned_steps, cumulative = [], 0.0
        for row in data['forecast_rows']:
            cumulative += row['amount'] * data['forecast_factor']
            planned_steps.append({'date': fields.Date.to_string(row['cutoff']),
                                  'value': cumulative / sale if sale else 0.0})
        # Curva S: costo programado por semana hasta el fin; ejecutado
        # contable acumulado hasta hoy.
        cost_dates = self._construction_chart_dates(start, max(filter(None, [end, today]))) \
            if start else []
        by_day = sorted(data['cost_by_day'].items())
        planned_cost = []
        for day in cost_dates:
            planned_cost.append(sum(v for d, v in by_day if d <= day))
        actual = []
        if project.account_id and dates:
            # sudo: solo importes de los apuntes de la obra (ver
            # _construction_accounting_amounts).
            groups = self.env['account.analytic.line'].sudo()._read_group(
                project._construction_analytic_domain(EXPENSE_TYPES, date_to=today),
                ['date:day'], ['amount:sum'])
            amounts = sorted((fields.Date.to_date(day), -amount) for day, amount in groups)
            for day in dates:
                actual.append(sum(a for d, a in amounts if d <= day))
        to_date = fields.Date.to_string
        return {
            'progress': {
                'dates': [to_date(d) for d in dates],
                'physical': physical,
                'valued': steps,
                'planned': planned_steps,
                'to_value': data['executed']['to_value'],
                'to_value_pct': data['executed']['physical'] - data['executed']['valued'],
                'start': to_date(start) if start else False,
                'end': to_date(max(filter(None, [end, today]))) if start else False,
                'today': to_date(today),
            },
            'cost': {
                'dates': [to_date(d) for d in cost_dates],
                'planned': planned_cost,
                'actual_dates': [to_date(d) for d in dates],
                'earned': earned,
                'actual': actual,
                'today': to_date(today),
            },
        }

    @api.model
    def _construction_valuation_rows(self, project, data):
        Report = self.env['construction.schedule.report']
        states = dict(self.env['construction.valuation']._fields['state']
                      ._description_selection(self.env))
        rows = []
        for valuation in self.env['construction.valuation'].search(
                [('project_id', '=', project.id), ('state', '!=', 'cancel')],
                order='cutoff_date'):
            target = project.construction_valuation_target_ids.filtered(
                lambda t: t.month == valuation.cutoff_date.replace(day=1))[:1]
            invoice = valuation.invoice_id.filtered(lambda m: m.state == 'posted')
            rows.append({
                'id': valuation.id,
                'name': valuation.display_name,
                'cutoff': format_date(self.env, valuation.cutoff_date, date_format='dd/MM/yy'),
                'target': target.amount_approved or False,
                'valued': valuation.amount_confirmed,
                'invoiced': invoice.amount_untaxed_signed if invoice else 0.0,
                'collected': sum(Report._construction_collections(invoice).values())
                if invoice else 0.0,
                'state': states.get(valuation.state, valuation.state),
            })
        return rows

    @api.model
    def _construction_specialty_rows(self, project, data, today):
        """Por especialidad (primer nivel de la plantilla): costo meta, avance
        presupuestado, avance físico (valor ganado ÷ costo meta), valorizado
        y el índice de costo contra lo ejecutado valorizado al costo del
        plan (la contabilidad no separa por especialidad)."""
        plan = data['plan']
        groups = defaultdict(lambda: {'target': 0.0, 'planned': 0.0, 'earned': 0.0,
                                      'actual': 0.0, 'valued': 0.0})
        planned_by_line = project._construction_planned_by_day(
            {line: line for line in plan.line_ids}, {})
        sale_level = {}
        by_partida = project._construction_lines_by_partida(plan) \
            if project.construction_sale_order_id else {}
        for (sale_line, (progress, _price, _target)) in data['physical_lines'].items():
            for line in by_partida.get(sale_line, []):
                key = line.level_1_id
                groups[key]['earned'] += progress * (line.amount_budgeted or line.amount_planned)
                sale_level.setdefault(sale_line, key)
        for line in plan.line_ids:
            key = line.level_1_id
            target = line.amount_budgeted or line.amount_planned
            groups[key]['target'] += target
            by_day = planned_by_line.get(line, {})
            total = sum(by_day.values())
            if total:
                groups[key]['planned'] += target * sum(
                    v for d, v in by_day.items() if d <= today) / total
            groups[key]['actual'] += line.amount_actual
        for valuation_line in data['valuations'].line_ids:
            key = sale_level.get(valuation_line.sale_line_id)
            if key is not None:
                groups[key]['valued'] += valuation_line.amount_confirmed
        rows = []
        for level, values in sorted(groups.items(), key=lambda item: item[0].display_name or ''):
            target = values['target']
            rows.append({
                'name': level.display_name or self.env._('Sin especialidad'),
                'target': target,
                'progress_planned': values['planned'] / target if target else 0.0,
                'progress': values['earned'] / target if target else 0.0,
                'valued': values['valued'],
                'cpi': values['earned'] / values['actual'] if values['actual'] else False,
            })
        return rows

    @api.model
    def _construction_change_rows(self, project):
        Change = self.env['construction.change.order']
        kinds = dict(Change._fields['kind']._description_selection(self.env))
        billing = dict(Change._fields['billing']._description_selection(self.env))
        states = dict(Change._fields['state']._description_selection(self.env))
        return [{
            'id': change.id,
            'name': change.name,
            'date': format_date(self.env, change.date, date_format='dd/MM/yy'),
            'kind': kinds.get(change.kind, ''),
            'billing': billing.get(change.billing, ''),
            'sale': change.amount_sale,
            'cost': change.amount_cost,
            'margin': change.amount_margin,
            'state': states.get(change.state, ''),
        } for change in Change.search([('project_id', '=', project.id)], order='date desc, id desc')]

    # ------------------------------------------------------------------
    # Accesos del encabezado
    # ------------------------------------------------------------------
    @api.model
    def action_open_document(self, project_id, kind, res_id=False):
        project = self._construction_project(project_id)
        if kind == 'schedule':
            return {'type': 'ir.actions.client', 'tag': 'al_construction_planner.schedule_report',
                    'name': self.env._('Cronograma valorizado'),
                    'context': {'construction_project_id': project.id}}
        if kind == 'control':
            plan = project._construction_current_plan()
            if not plan:
                raise UserError(self.env._('La obra no tiene plan.'))
            return plan.action_open_control_analysis()
        models_by_kind = {
            'valuation': ('construction.valuation',
                          'al_construction_planner_sale.action_construction_valuation'),
            'change': ('construction.change.order',
                       'al_construction_planner_sale.action_construction_change_order'),
        }
        if kind not in models_by_kind:
            raise UserError(self.env._('Documento desconocido.'))
        model, xmlid = models_by_kind[kind]
        if res_id:
            return {'type': 'ir.actions.act_window', 'res_model': model, 'res_id': res_id,
                    'views': [[False, 'form']], 'target': 'current'}
        action = self.env['ir.actions.act_window']._for_xml_id(xmlid)
        action['domain'] = [('project_id', '=', project.id)]
        action['context'] = {'default_project_id': project.id}
        return action

    @api.model
    def toggle_favorite(self, project_id):
        """La estrella usa el favorito nativo del proyecto, por usuario."""
        project = self._construction_project(project_id)
        # El método nativo escribe con sudo: quien lee la obra la marca.
        project._set_favorite_user_ids(not project.is_favorite)
        project.invalidate_recordset(['is_favorite'])
        return project.is_favorite


class ProjectProjectSheet(models.Model):
    _inherit = 'project.project'

    def action_construction_indicator_sheet(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'al_construction_planner_sale.indicator_sheet',
            'name': self.env._('Ficha · %s', self.display_name),
            'context': {'construction_project_id': self.id},
        }
