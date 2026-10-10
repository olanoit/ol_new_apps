# -*- coding: utf-8 -*-
"""Cronograma valorizado de la obra (P-22, fase 11).

Una fila por obra, semana de la obra, concepto y escenario:

- Plan. Costo: cada línea del plan vigente repartida en partes iguales entre
  los días hábiles de la etapa de su ambiente (``construction.space.stage``)
  o, sin etapa, en su fecha de necesidad. Ingreso devengado: precio de cada
  partida × su avance previsto (el mismo reparto, con material). Valorización,
  factura y cobro: el calendario de la obra (P-21); el fondo de garantía se
  cobra al cierre y el adelanto, al inicio. La última semana absorbe el
  redondeo para cerrar en el costo del plan y en el precio.
- Real. Costo: lo ejecutado valorizado de las líneas del plan vigente
  (avances validados × tarifa, horas × costo hora y consumos × costo del
  plan) hasta el cierre de cada semana. Ingreso: las entregas confirmadas.
  Valorización: las confirmadas en la fecha de conformidad. Factura: las
  facturas publicadas de la orden de venta del contrato (sin IGV). Cobro: los
  pagos conciliados con esas facturas, en proporción a su base imponible.

No es una vista SQL: el reparto por días hábiles y el calendario del ingreso
salen de la lógica de las fases 8 y 10 (feriados, días hábiles, partidas).
Las filas se recalculan al abrir P-22 y con la acción programada diaria; el
pivote y el gráfico leen la tabla."""
import base64
import io
import logging
from collections import defaultdict
from datetime import timedelta

import xlsxwriter

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date

SCENARIOS = [
    ('plan', 'Plan'),
    ('real', 'Real'),
]
CONCEPTS = [
    ('cost', 'Costo'),
    ('revenue', 'Ingreso devengado'),
    ('valuation', 'Valorización confirmada'),
    ('invoice', 'Facturado'),
    ('collection', 'Cobrado'),
]
# Columnas de la tabla de P-22: concepto → acumula.
TABLE_CONCEPTS = ('cost', 'revenue', 'valuation', 'invoice', 'collection')
# Estados de la valorización que cuentan como confirmada.
CONFIRMED_VALUATION_STATES = ('confirmed', 'invoiced')

_logger = logging.getLogger(__name__)


class ConstructionScheduleReport(models.Model):
    _name = 'construction.schedule.report'
    _description = 'Cronograma valorizado de la obra'
    _order = 'project_id, week_start, scenario, concept'
    _check_company_auto = True

    project_id = fields.Many2one(
        'project.project', string='Obra', required=True, index=True, ondelete='cascade',
        check_company=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True, readonly=True)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    plan_id = fields.Many2one(
        'construction.resource.plan', string='Plan', check_company=True, readonly=True,
        ondelete='set null')
    scenario = fields.Selection(SCENARIOS, string='Escenario', required=True, readonly=True)
    concept = fields.Selection(CONCEPTS, string='Concepto', required=True, readonly=True)
    week_start = fields.Date(string='Semana', required=True, readonly=True)
    week_end = fields.Date(string='Fin de la semana', readonly=True)
    is_guarantee = fields.Boolean(
        string='Fondo de garantía', readonly=True,
        help='Cobro del fondo de garantía al cierre de la obra.')
    is_advance = fields.Boolean(string='Adelanto', readonly=True)
    amount = fields.Monetary(string='Monto', readonly=True, aggregator='sum')

    # ------------------------------------------------------------------
    # Cálculo
    # ------------------------------------------------------------------
    @api.model
    def _construction_refresh(self, projects):
        """Recalcula las filas de ``projects`` (obras con plan vigente o en
        preparación) y devuelve las nuevas."""
        rows = []
        projects = projects.filtered('is_construction_site')
        projects.check_access('read')
        # sudo: la tabla resume documentos de otras áreas (inventario,
        # fabricación, horas de RR. HH., contabilidad) de obras que el usuario
        # puede leer (comprobado arriba); los usuarios solo la leen, sin
        # permiso de escritura, y las reglas por compañía la filtran.
        report_sudo = self.sudo()
        for project_sudo in projects.sudo():
            rows += report_sudo.with_company(
                project_sudo.company_id or self.env.company)._construction_rows(project_sudo)
        report_sudo.search([('project_id', 'in', projects.ids)]).unlink()
        return self.browse(report_sudo.create(rows).ids)

    @api.model
    def _construction_rows(self, project):
        plan = project._construction_current_plan()
        if not plan:
            return []
        company = project.company_id or plan.company_id
        currency = company.currency_id
        base = {'project_id': project.id, 'company_id': company.id, 'plan_id': plan.id}
        rows = []

        def add(scenario, concept, amounts, **extra):
            for week, amount in sorted(amounts.items()):
                if not currency.is_zero(amount):
                    rows.append(dict(base, scenario=scenario, concept=concept, week_start=week,
                                     week_end=week + timedelta(days=6),
                                     amount=currency.round(amount), **extra))

        plan_data = self._construction_plan_amounts(project, plan)
        for concept, amounts in plan_data['weekly'].items():
            add('plan', concept, amounts)
        for concept, week, amount, flag in plan_data['extra']:
            add('plan', concept, {week: amount}, **{flag: True})
        real = self._construction_real_amounts(project, plan)
        for concept, amounts in real['weekly'].items():
            add('real', concept, amounts)
        return rows

    @api.model
    def _construction_weekly(self, project, by_day, total=None):
        """{inicio de semana: monto redondeado} desde {día: monto}. Con
        ``total``, la última semana absorbe el redondeo para cerrar en él."""
        currency = (project.company_id or self.env.company).currency_id
        weekly = defaultdict(float)
        for day, amount in by_day.items():
            weekly[project._construction_period(day)[0]] += amount
        weekly = {week: currency.round(amount) for week, amount in weekly.items()}
        if weekly:
            if total is None:
                total = sum(by_day.values())
            last = max(weekly)
            weekly[last] = currency.round(
                currency.round(total) - sum(v for w, v in weekly.items() if w != last))
        return weekly

    @api.model
    def _construction_plan_amounts(self, project, plan):
        """Escenario plan: {'weekly': {concepto: {semana: monto}}, 'extra':
        [(concepto, semana, monto, marca)]} con el fondo de garantía y el
        adelanto."""
        currency = (project.company_id or plan.company_id).currency_id
        cache = {}
        weekly = {}
        extra = []
        cost_by_day = project._construction_planned_by_day({False: plan.line_ids}, cache)[False]
        weekly['cost'] = self._construction_weekly(project, cost_by_day)
        if not project.construction_sale_order_id:
            return {'weekly': weekly, 'extra': extra}
        lines_by_partida = project._construction_lines_by_partida(plan)
        planned = project._construction_planned_by_day(lines_by_partida, cache)
        end = project._construction_income_period()[1] or fields.Date.context_today(self)
        revenue_by_day = defaultdict(float)
        total_price = 0.0
        for sale_line, by_day in planned.items():
            total = sum(by_day.values())
            if not total:
                continue
            price = sale_line._construction_price(end)
            total_price += price
            for day, amount in by_day.items():
                revenue_by_day[day] += price * amount / total
        weekly['revenue'] = self._construction_weekly(project, revenue_by_day, total_price)
        forecast = project._construction_get_valuation_forecast()
        week = lambda day: project._construction_period(day)[0]
        valuation, invoice, collection = defaultdict(float), defaultdict(float), defaultdict(float)
        for row in forecast['rows']:
            valuation[week(row['confirm'])] += row['amount']
            invoice[week(row['invoice'])] += row['amount']
            collection[week(row['collection'])] += row['net']
        weekly.update(valuation=valuation, invoice=invoice, collection=collection)
        total = forecast['total']
        if total and not currency.is_zero(total['guarantee']) and total.get('guarantee_date'):
            extra.append(('collection', week(total['guarantee_date']), total['guarantee'],
                          'is_guarantee'))
        if total and not currency.is_zero(total['amortization']):
            # Adelanto: se factura y se cobra al inicio; las valorizaciones lo
            # amortizan, así el cobrado acumulado cierra en el precio.
            start = project._construction_income_period()[0] or plan.date_start
            advance = currency.round(total['amortization'])
            extra.append(('invoice', week(start), advance, 'is_advance'))
            extra.append(('collection', week(start), advance, 'is_advance'))
        return {'weekly': weekly, 'extra': extra}

    @api.model
    def _construction_real_amounts(self, project, plan, today=None):
        """Escenario real: {'weekly': {concepto: {semana: monto}}}."""
        today = today or fields.Date.context_today(self)
        week = lambda day: project._construction_period(day)[0]
        weekly = {concept: defaultdict(float) for concept in TABLE_CONCEPTS}
        # Costo: diferencias del ejecutado valorizado al cierre de cada semana,
        # desde el inicio de la obra hasta hoy o su fin (lo registrado con
        # fecha futura también cuenta).
        start = min(filter(None, [project.date_start, plan.date_start]), default=False)
        last = max(filter(None, [today, project.date, plan.date_end]))
        if start and start <= last:
            lines = plan.line_ids
            previous = 0.0
            first = week(start)
            for index in range((week(last) - first).days // 7 + 1):
                week_start = first + timedelta(weeks=index)
                executed = lines._construction_valued_execution(week_start + timedelta(days=6))
                cumulative = sum(sum(kinds.values()) for kinds in executed.values())
                weekly['cost'][week_start] += cumulative - previous
                previous = cumulative
        # Ingreso devengado: entregas confirmadas (también las ya valorizadas).
        for delivery in self.env['construction.weekly.delivery'].search(
                [('project_id', '=', project.id), ('state', 'in', ('confirmed', 'valued'))]):
            weekly['revenue'][delivery.period_start] += delivery.revenue_amount
        for valuation in self.env['construction.valuation'].search(
                [('project_id', '=', project.id), ('state', 'in', CONFIRMED_VALUATION_STATES),
                 ('confirm_date', '!=', False)]):
            weekly['valuation'][week(valuation.confirm_date)] += valuation.amount_confirmed
        order = project.construction_sale_order_id
        if order:
            invoices = order.invoice_ids.filtered(
                lambda m: m.state == 'posted' and m.move_type in ('out_invoice', 'out_refund'))
            for invoice in invoices:
                weekly['invoice'][week(invoice.invoice_date or invoice.date)] += \
                    invoice.amount_untaxed_signed
                for day, amount in self._construction_collections(invoice).items():
                    weekly['collection'][week(day)] += amount
        return {'weekly': weekly}

    @api.model
    def _construction_collections(self, invoice):
        """{fecha: cobrado sin IGV} de una factura: los pagos y extractos
        conciliados con sus líneas por cobrar (no las notas de crédito),
        en proporción de la base imponible al total."""
        result = defaultdict(float)
        total = invoice.amount_total_signed
        if invoice.move_type != 'out_invoice' or not total:
            return result
        ratio = invoice.amount_untaxed_signed / total
        receivable = invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable')
        for partial in receivable.matched_credit_ids:
            counterpart = partial.credit_move_id
            if counterpart.move_id.is_invoice(include_receipts=True):
                continue
            result[counterpart.date] += partial.amount * ratio
        return result

    # ------------------------------------------------------------------
    # Pantalla P-22
    # ------------------------------------------------------------------
    @api.model
    def get_schedule_projects(self):
        plans = self.env['construction.resource.plan'].search(
            [('state', 'not in', ('cancel', 'replaced'))])
        return [{'id': project.id, 'name': project.display_name}
                for project in plans.project_id.sorted('name')]

    @api.model
    def get_schedule(self, project_id, refresh=True):
        """Tabla semanal de P-22 con plan y real lado a lado, la curva S y
        los totales. Recalcula la obra antes (``refresh``)."""
        project = self.env['project.project'].browse(project_id).exists()
        if not project:
            raise UserError(self.env._('La obra ya no existe.'))
        if refresh:
            self._construction_refresh(project)
        records = self.search([('project_id', '=', project.id)])
        currency = (project.company_id or self.env.company).currency_id
        by_week = defaultdict(lambda: {s: defaultdict(float) for s, _l in SCENARIOS})
        today_week = project._construction_period(fields.Date.context_today(self))[0]
        real_until = today_week
        guarantee = {s: 0.0 for s, _l in SCENARIOS}
        guarantee_week = False
        for record in records:
            if record.is_guarantee:
                guarantee[record.scenario] += record.amount
                guarantee_week = record.week_start
                continue
            by_week[record.week_start][record.scenario][record.concept] += record.amount
            if record.scenario == 'real':
                real_until = max(real_until, record.week_start)
        weeks = sorted(by_week)
        if weeks:
            # Semanas sin movimiento entre la primera y la última, como en P-22.
            weeks = [weeks[0] + timedelta(weeks=i)
                     for i in range((weeks[-1] - weeks[0]).days // 7 + 1)]
        cumulative = {s: defaultdict(float) for s, _l in SCENARIOS}
        rows = []
        for week_start in weeks:
            row = {'week_start': fields.Date.to_string(week_start),
                   'label': '%s – %s' % (format_date(self.env, week_start, date_format='dd/MM'),
                                         format_date(self.env, week_start + timedelta(days=6),
                                                     date_format='dd/MM'))}
            for scenario, _label in SCENARIOS:
                values = by_week[week_start][scenario] if week_start in by_week else {}
                data = {}
                for concept in TABLE_CONCEPTS:
                    amount = currency.round(values.get(concept, 0.0))
                    cumulative[scenario][concept] += amount
                    data[concept] = amount
                    data[concept + '_cum'] = currency.round(cumulative[scenario][concept])
                data['margin_cum'] = currency.round(
                    cumulative[scenario]['revenue'] - cumulative[scenario]['cost'])
                row[scenario] = data
            rows.append(row)
        totals = {}
        for scenario, _label in SCENARIOS:
            data = {concept: currency.round(cumulative[scenario][concept])
                    for concept in TABLE_CONCEPTS}
            data['guarantee'] = currency.round(guarantee[scenario])
            data['collection_total'] = currency.round(
                data['collection'] + data['guarantee'])
            data['margin'] = currency.round(data['revenue'] - data['cost'])
            gaps = [(r[scenario]['cost_cum'] - r[scenario]['collection_cum'], r['week_start'])
                    for r in rows]
            gap = max(gaps, default=(0.0, False))
            data['max_gap'] = currency.round(gap[0])
            data['max_gap_week'] = gap[1]
            totals[scenario] = data
        plan = project._construction_current_plan()
        return {
            'project_id': project.id,
            'project_name': project.display_name,
            'plan_name': plan.display_name or '',
            'currency_symbol': currency.symbol,
            'currency_position': currency.position,
            'rows': rows,
            'totals': totals,
            'guarantee_week': fields.Date.to_string(guarantee_week) if guarantee_week else False,
            'concepts': [list(c) for c in CONCEPTS],
            'today_week': fields.Date.to_string(today_week),
            # La curva real llega hasta hoy o hasta lo último registrado.
            'real_until': fields.Date.to_string(real_until),
        }

    @api.model
    def action_open_analysis(self, project_id=False):
        action = self.env['ir.actions.act_window']._for_xml_id(
            'al_construction_planner.action_construction_schedule_report')
        if project_id:
            project = self.env['project.project'].browse(project_id)
            self._construction_refresh(project)
            action['domain'] = [('project_id', '=', project.id)]
            action['name'] = self.env._('Cronograma valorizado de %s', project.display_name)
        return action

    @api.model
    def action_export_xlsx(self, project_id):
        """Exporta la tabla de P-22 (plan y real) a Excel."""
        data = self.get_schedule(project_id, refresh=False)
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        bold = workbook.add_format({'bold': True})
        head = workbook.add_format({'bold': True, 'bg_color': '#E5E7EB', 'border': 1,
                                    'text_wrap': True, 'valign': 'top'})
        money = workbook.add_format({'num_format': '#,##0.00'})
        money_bold = workbook.add_format({'num_format': '#,##0.00', 'bold': True})
        labels = [
            ('cost', self.env._('Costo')), ('cost_cum', self.env._('Costo acum.')),
            ('revenue', self.env._('Ingreso devengado')),
            ('revenue_cum', self.env._('Ingreso acum.')),
            ('margin_cum', self.env._('Margen acum.')),
            ('valuation', self.env._('Valorización confirmada')),
            ('invoice', self.env._('Facturado')), ('collection', self.env._('Cobrado')),
            ('collection_cum', self.env._('Cobrado acum.')),
        ]
        for scenario, title in SCENARIOS:
            sheet = workbook.add_worksheet(dict(
                self._fields['scenario']._description_selection(self.env))[scenario])
            sheet.write(0, 0, self.env._('Cronograma valorizado · %(project)s · %(plan)s',
                                         project=data['project_name'], plan=data['plan_name']),
                        bold)
            sheet.write(2, 0, self.env._('Semana'), head)
            for col, (_key, label) in enumerate(labels, start=1):
                sheet.write(2, col, label, head)
            row_index = 3
            for row in data['rows']:
                sheet.write(row_index, 0, row['label'])
                for col, (key, _label) in enumerate(labels, start=1):
                    sheet.write_number(row_index, col, row[scenario][key], money)
                row_index += 1
            totals = data['totals'][scenario]
            if totals['guarantee']:
                sheet.write(row_index, 0, self.env._('Fondo de garantía, al cierre'), bold)
                sheet.write_number(row_index, 8, totals['guarantee'], money_bold)
                sheet.write_number(row_index, 9, totals['collection_total'], money_bold)
            sheet.set_column(0, 0, 16)
            sheet.set_column(1, len(labels), 15)
            sheet.freeze_panes(3, 1)
        workbook.close()
        project = self.env['project.project'].browse(project_id)
        # Sin documento asociado: solo lo descarga quien lo genera (adjuntarlo
        # a la obra exigiría poder editarla).
        attachment = self.env['ir.attachment'].create({
            'name': self.env._('Cronograma valorizado %s.xlsx', project.name),
            'datas': base64.b64encode(output.getvalue()),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }

    # ------------------------------------------------------------------
    # Acción programada
    # ------------------------------------------------------------------
    @api.model
    def _cron_refresh(self):
        plans = self.env['construction.resource.plan'].search(
            [('state', 'not in', ('cancel', 'replaced', 'closed'))])
        for project in plans.project_id:
            try:
                with self.env.cr.savepoint():
                    self._construction_refresh(project)
            except UserError as error:
                _logger.warning('Cronograma valorizado de %s: %s', project.display_name,
                                error.args[0])
