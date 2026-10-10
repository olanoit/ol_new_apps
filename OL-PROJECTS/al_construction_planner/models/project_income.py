# -*- coding: utf-8 -*-
"""Calendario e ingresos de la obra (P-21, fase 10): la orden de venta del
contrato con sus partidas, la frecuencia de valorización y los plazos de
presentación, confirmación, factura y cobro, el adelanto y el fondo de
garantía, y la tabla de valorizaciones previstas."""
from collections import defaultdict
from datetime import timedelta

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import format_date, formatLang

from .common import GUARANTEE_RELEASES, VALUATION_UNITS

# Campos del calendario de la obra con su valor por defecto en la compañía.
INCOME_DEFAULTS = (
    'construction_valuation_every', 'construction_valuation_unit',
    'construction_valuation_submit_days', 'construction_client_confirm_days',
    'construction_invoice_days', 'construction_advance_pct',
    'construction_advance_amortization_pct', 'construction_guarantee_pct',
    'construction_guarantee_release',
)


class ConstructionValuationCutoff(models.Model):
    """Fecha de corte de la obra que valoriza en «fechas fijas»."""
    _name = 'construction.valuation.cutoff'
    _description = 'Corte de valorización de la obra'
    _order = 'project_id, date'
    _check_company_auto = True

    project_id = fields.Many2one(
        'project.project', string='Obra', required=True, ondelete='cascade', index=True,
        check_company=True)
    company_id = fields.Many2one(
        related='project_id.company_id', string='Compañía', store=True, index=True)
    date = fields.Date(string='Corte', required=True)

    _date_unique = models.Constraint(
        'UNIQUE(project_id, date)', 'La obra ya tiene ese corte de valorización.')


class ProjectProject(models.Model):
    _inherit = 'project.project'

    construction_sale_order_id = fields.Many2one(
        'sale.order', string='Orden de venta del contrato', check_company=True, tracking=True,
        domain="[('state', '!=', 'cancel')]",
        help='Una línea por partida (cantidad 1). Las entregas semanales devengan el precio de '
             'cada partida y la factura de la valorización sale de esta orden.')
    construction_valuation_every = fields.Integer(
        string='Valorizar cada', compute='_compute_construction_income_config', store=True,
        readonly=False)
    construction_valuation_unit = fields.Selection(
        VALUATION_UNITS, string='Frecuencia de valorización',
        compute='_compute_construction_income_config', store=True, readonly=False,
        help='Cada tantas semanas de la obra (el corte es el último día de la semana) o en las '
             'fechas fijas de la lista de cortes.')
    construction_valuation_cutoff_ids = fields.One2many(
        'construction.valuation.cutoff', 'project_id', string='Cortes de valorización')
    construction_valuation_submit_days = fields.Integer(
        string='Días para presentar', compute='_compute_construction_income_config', store=True,
        readonly=False, help='Desde el corte.')
    construction_client_confirm_days = fields.Integer(
        string='Días para la confirmación del cliente',
        compute='_compute_construction_income_config', store=True, readonly=False,
        help='Desde la presentación.')
    construction_invoice_days = fields.Integer(
        string='Días para facturar', compute='_compute_construction_income_config', store=True,
        readonly=False, help='Desde la confirmación.')
    construction_collection_days = fields.Integer(
        string='Plazo de cobro (días)', compute='_compute_construction_collection_days',
        store=True, readonly=False,
        help='Desde la factura. Por defecto, el plazo de pago del cliente del contrato.')
    construction_advance_pct = fields.Float(
        string='Adelanto (%)', compute='_compute_construction_income_config', store=True,
        readonly=False)
    construction_advance_amortization_pct = fields.Float(
        string='Amortización por valorización (%)',
        compute='_compute_construction_income_config', store=True, readonly=False,
        help='Previsión: la amortización la decide el cliente en cada valorización.')
    construction_guarantee_pct = fields.Float(
        string='Fondo de garantía (%)', compute='_compute_construction_income_config',
        store=True, readonly=False, help='Se retiene en cada valorización y se cobra al final.')
    construction_guarantee_release = fields.Selection(
        GUARANTEE_RELEASES, string='Cobro del fondo de garantía',
        compute='_compute_construction_income_config', store=True, readonly=False)
    construction_guarantee_release_date = fields.Date(string='Fecha de cobro del fondo')
    construction_valuation_forecast_html = fields.Html(
        string='Valorizaciones previstas', compute='_compute_construction_valuation_forecast',
        sanitize=False)
    construction_delivery_count = fields.Integer(
        string='Nº de entregas semanales', compute='_compute_construction_income_counts')
    construction_valuation_count = fields.Integer(
        string='Nº de valorizaciones', compute='_compute_construction_income_counts')

    @api.constrains('construction_sale_order_id', 'company_id')
    def _check_construction_sale_order_company(self):
        for project in self:
            order = project.construction_sale_order_id
            if order and project.company_id and order.company_id != project.company_id:
                raise ValidationError(self.env._(
                    'La orden de venta del contrato %(order)s es de %(company)s y la obra, de '
                    '%(project_company)s.', order=order.name, company=order.company_id.name,
                    project_company=project.company_id.name))

    @api.depends('company_id')
    def _compute_construction_income_config(self):
        for project in self:
            company = project.company_id or self.env.company
            for field in INCOME_DEFAULTS:
                if not project[field]:
                    project[field] = company[field]

    @api.depends('construction_sale_order_id.payment_term_id', 'partner_id', 'company_id')
    def _compute_construction_collection_days(self):
        for project in self:
            order = project.construction_sale_order_id
            term = order.payment_term_id or \
                (order.partner_id or project.partner_id).property_payment_term_id
            days = max(term.line_ids.mapped('nb_days'), default=0) if term else 0
            company = project.company_id or self.env.company
            project.construction_collection_days = days or \
                project.construction_collection_days or company.construction_collection_days

    def _compute_construction_income_counts(self):
        deliveries = dict(self.env['construction.weekly.delivery']._read_group(
            [('project_id', 'in', self.ids)], ['project_id'], ['__count']))
        valuations = dict(self.env['construction.valuation']._read_group(
            [('project_id', 'in', self.ids)], ['project_id'], ['__count']))
        for project in self:
            project.construction_delivery_count = deliveries.get(project, 0)
            project.construction_valuation_count = valuations.get(project, 0)

    # ------------------------------------------------------------------
    # Partidas del contrato
    # ------------------------------------------------------------------
    def _construction_partida_lines(self):
        """Líneas de la OV del contrato que son partidas: las de producto
        (sin secciones, notas ni anticipos)."""
        self.ensure_one()
        return self.construction_sale_order_id.order_line.filtered(
            lambda l: not l.display_type and not l.is_downpayment and l.product_id)

    def _construction_lines_by_partida(self, plan=None):
        """{línea de la OV: líneas del plan de su partida}. La partida con
        familia toma las líneas cuyo ambiente (o la propia línea) tiene una
        tipología de esa familia; la única partida sin familia, el resto."""
        self.ensure_one()
        partidas = self._construction_partida_lines()
        plan = plan if plan is not None else self._construction_current_plan()
        result = {sale_line: self.env['construction.resource.plan.line'] for sale_line in partidas}
        if not partidas:
            return result
        catch_all = partidas.filtered(lambda l: not l.construction_family)
        if len(catch_all) > 1:
            raise UserError(self.env._(
                'La orden de venta %(order)s tiene %(count)s partidas sin familia: solo una '
                'puede tomar el resto de la obra. Indique la familia de cada partida.',
                order=self.construction_sale_order_id.name, count=len(catch_all)))
        by_family = {line.construction_family: line for line in partidas
                     if line.construction_family}
        for plan_line in plan.line_ids:
            family = (plan_line.space_task_id.construction_typology_id.family
                      or plan_line.typology_id.family)
            sale_line = by_family.get(family) or catch_all
            if sale_line:
                result[sale_line] |= plan_line
        return result

    # ------------------------------------------------------------------
    # Fechas del ingreso (P-21)
    # ------------------------------------------------------------------
    def _construction_income_period(self):
        """(inicio, fin) de la obra para el calendario: los del proyecto o,
        si faltan, los del plan vigente."""
        self.ensure_one()
        plan = self._construction_current_plan()
        return (self.date_start or plan.date_start or False,
                self.date or plan.date_end or False)

    def _construction_valuation_cutoffs(self):
        """Cortes de valorización de la obra, ordenados. Por semanas: el
        primer bloque empieza en el primer inicio de semana desde el inicio
        de la obra (los días anteriores entran en la primera valorización) y
        cada corte es el último día del bloque; el último bloque cubre el fin
        de la obra."""
        self.ensure_one()
        if self.construction_valuation_unit == 'dates':
            return sorted(self.construction_valuation_cutoff_ids.mapped('date'))
        start, end = self._construction_income_period()
        if not start or not end or end < start:
            return []
        week_start = int(self.construction_week_start_day or '3')
        anchor = start + timedelta(days=(week_start - start.weekday()) % 7)
        step = timedelta(days=7 * max(self.construction_valuation_every, 1))
        cutoffs = []
        cutoff = anchor + step - timedelta(days=1)
        while True:
            cutoffs.append(cutoff)
            if cutoff >= end or len(cutoffs) > 520:
                break
            cutoff += step
        return cutoffs

    def _construction_income_dates(self, cutoff, cache=None):
        """Fechas previstas desde un corte: presentación = corte + días para
        presentar; confirmación = presentación + días del cliente; factura =
        confirmación + días para facturar; cobro = factura + plazo de cobro.
        Cada una pasa al siguiente día hábil y la siguiente cuenta desde ella."""
        self.ensure_one()
        company = self.company_id or self.env.company
        cache = {} if cache is None else cache
        submit = company._construction_next_working_day(
            cutoff + timedelta(days=self.construction_valuation_submit_days), cache)
        confirm = company._construction_next_working_day(
            submit + timedelta(days=self.construction_client_confirm_days), cache)
        invoice = company._construction_next_working_day(
            confirm + timedelta(days=self.construction_invoice_days), cache)
        collection = company._construction_next_working_day(
            invoice + timedelta(days=self.construction_collection_days), cache)
        return {'submit': submit, 'confirm': confirm, 'invoice': invoice,
                'collection': collection}

    def _construction_guarantee_collection_date(self, cache=None):
        """Cobro del fondo de garantía: la fecha fija o el fin de la obra más
        el plazo de cobro, corridos al siguiente día hábil."""
        self.ensure_one()
        company = self.company_id or self.env.company
        if self.construction_guarantee_release == 'date':
            day = self.construction_guarantee_release_date
        else:
            end = self._construction_income_period()[1]
            day = end and end + timedelta(days=self.construction_collection_days)
        return day and company._construction_next_working_day(day, cache)

    def _construction_planned_by_day(self, lines_by_partida, cache=None):
        """{línea de la OV: {día: monto del plan}}: cada línea del plan
        repartida en partes iguales entre los días hábiles de la etapa de su
        ambiente (construction.space.stage) o, sin etapa, en su fecha de
        necesidad. Es el avance previsto de la partida (en el plan, cada
        semana devenga ingreso en la misma proporción que su costo)."""
        self.ensure_one()
        company = self.company_id or self.env.company
        cache = {} if cache is None else cache
        stages = {}
        for stage in self.env['construction.space.stage'].search([('project_id', '=', self.id)]):
            stages[(stage.space_task_id.id, stage.stage)] = (stage.date_start, stage.date_end)
        result = {}
        for sale_line, plan_lines in lines_by_partida.items():
            amounts = defaultdict(float)
            for line in plan_lines:
                start, end = stages.get((line.space_task_id.id, line.stage),
                                        (line.date_needed, line.date_needed))
                if not start:
                    continue
                end = max(end or start, start)
                days = [start + timedelta(days=n) for n in range((end - start).days + 1)]
                working = [d for d in days if company._construction_is_working_day(d, cache)]
                days = working or days
                share = line.amount_planned / len(days)
                for day in days:
                    amounts[day] += share
            result[sale_line] = amounts
        return result

    def _construction_get_valuation_forecast(self):
        """Valorizaciones previstas de la obra (P-21): una fila por corte con
        sus fechas, el monto previsto (precio de cada partida × avance
        previsto del periodo), la amortización del adelanto, el fondo de
        garantía y el neto a cobrar. La última absorbe el redondeo para
        cerrar en el precio."""
        self.ensure_one()
        currency = (self.company_id or self.env.company).currency_id
        cache = {}
        cutoffs = self._construction_valuation_cutoffs()
        rows = []
        if not cutoffs:
            return {'rows': rows, 'total': {}, 'currency': currency}
        lines_by_partida = self._construction_lines_by_partida()
        planned = self._construction_planned_by_day(lines_by_partida, cache)
        prices = {sale_line: sale_line._construction_price(cutoffs[-1])
                  for sale_line in lines_by_partida}
        total_price = currency.round(sum(prices.values()))
        cumulative = []
        for cutoff in cutoffs:
            amount = 0.0
            for sale_line, by_day in planned.items():
                total = sum(by_day.values())
                if total:
                    done = sum(v for d, v in by_day.items() if d <= cutoff)
                    amount += prices[sale_line] * done / total
            cumulative.append(currency.round(amount))
        cumulative[-1] = total_price
        advance_left = currency.round(total_price * self.construction_advance_pct / 100.0)
        previous = 0.0
        for index, cutoff in enumerate(cutoffs):
            amount = currency.round(cumulative[index] - previous)
            previous = cumulative[index]
            guarantee = currency.round(amount * self.construction_guarantee_pct / 100.0)
            amortization = min(currency.round(
                amount * self.construction_advance_amortization_pct / 100.0), advance_left)
            advance_left -= amortization
            dates = self._construction_income_dates(cutoff, cache)
            rows.append(dict(dates, number=index + 1, cutoff=cutoff, amount=amount,
                             amortization=amortization, guarantee=guarantee,
                             net=amount - guarantee - amortization))
        total = {
            'amount': sum(r['amount'] for r in rows),
            'amortization': sum(r['amortization'] for r in rows),
            'guarantee': sum(r['guarantee'] for r in rows),
            'net': sum(r['net'] for r in rows),
            'guarantee_date': self._construction_guarantee_collection_date(cache),
        }
        return {'rows': rows, 'total': total, 'currency': currency}

    @api.depends('construction_valuation_every', 'construction_valuation_unit',
                 'construction_valuation_cutoff_ids.date', 'construction_valuation_submit_days',
                 'construction_client_confirm_days', 'construction_invoice_days',
                 'construction_collection_days', 'construction_advance_pct',
                 'construction_advance_amortization_pct', 'construction_guarantee_pct',
                 'construction_guarantee_release', 'construction_guarantee_release_date',
                 'construction_sale_order_id', 'construction_week_start_day',
                 'date_start', 'date')
    def _compute_construction_valuation_forecast(self):
        for project in self:
            if not project.is_construction_site or not project.id:
                project.construction_valuation_forecast_html = False
                continue
            try:
                forecast = project._construction_get_valuation_forecast()
            except UserError as error:
                project.construction_valuation_forecast_html = Markup(
                    '<div class="alert alert-warning mb-0">%s</div>') % error.args[0]
                continue
            project.construction_valuation_forecast_html = project._construction_forecast_table(
                forecast)

    def _construction_forecast_table(self, forecast):
        """Tabla HTML de las valorizaciones previstas."""
        self.ensure_one()
        rows = forecast['rows']
        if not rows:
            return Markup('<p class="text-muted mb-0">%s</p>') % self.env._(
                'Sin cortes: indique el inicio y el fin de la obra (o del plan) o cargue las '
                'fechas fijas de corte.')
        currency = forecast['currency']
        with_advance = any(r['amortization'] for r in rows)

        def money(value):
            return formatLang(self.env, value, currency_obj=currency)

        def day(value):
            return format_date(self.env, value) if value else ''

        headers = [self.env._('Val.'), self.env._('Corte'), self.env._('Presentación'),
                   self.env._('Confirmación'), self.env._('Factura'), self.env._('Cobro'),
                   self.env._('Monto previsto')]
        if with_advance:
            headers.append(self.env._('Amortización del adelanto'))
        headers += [self.env._('Fondo de garantía %s %%') % formatLang(
            self.env, self.construction_guarantee_pct, digits=2), self.env._('Neto a cobrar')]
        numeric = len(headers) - (4 if with_advance else 3)
        html = Markup('<table class="table table-sm table-hover o_construction_forecast mb-1">'
                      '<thead><tr>')
        for index, header in enumerate(headers):
            css = ' class="text-end"' if index >= numeric else ''
            html += Markup('<th%s>%s</th>') % (Markup(css), header)
        html += Markup('</tr></thead><tbody>')
        for row in rows:
            cells = [str(row['number']), day(row['cutoff']), day(row['submit']),
                     day(row['confirm']), day(row['invoice']), day(row['collection'])]
            amounts = [row['amount']] + ([row['amortization']] if with_advance else []) + [
                row['guarantee'], row['net']]
            html += Markup('<tr>') + Markup('').join(
                Markup('<td>%s</td>') % c for c in cells) + Markup('').join(
                Markup('<td class="text-end">%s</td>') % money(a) for a in amounts) + \
                Markup('</tr>')
        total = forecast['total']
        label = self.env._('Total · el fondo de garantía se cobra el %s',
                           day(total['guarantee_date'])) \
            if total.get('guarantee_date') else self.env._('Total')
        amounts = [total['amount']] + ([total['amortization']] if with_advance else []) + [
            total['guarantee'], total['net']]
        html += Markup('</tbody><tfoot><tr class="fw-bold"><td colspan="6">%s</td>') % label
        html += Markup('').join(
            Markup('<td class="text-end">%s</td>') % money(a) for a in amounts)
        html += Markup('</tr></tfoot></table>')
        return html + Markup('<p class="text-muted small mb-0">%s</p>') % escape(self.env._(
            'Una fecha que cae en día no hábil (sin horario en el calendario de la compañía o '
            'feriado) pasa al siguiente día hábil. Monto previsto: precio de cada partida × su '
            'avance previsto en el periodo, con las líneas del plan repartidas en los días '
            'hábiles de su etapa.'))

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def action_view_construction_deliveries(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Entregas semanales de %s', self.display_name),
            'res_model': 'construction.weekly.delivery',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_construction_valuations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Valorizaciones de %s', self.display_name),
            'res_model': 'construction.valuation',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_construction_prepare_valuation(self):
        """Preparar valorización (W-13) de la obra."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Preparar valorización'),
            'res_model': 'construction.valuation.prepare.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_project_id': self.id},
        }
