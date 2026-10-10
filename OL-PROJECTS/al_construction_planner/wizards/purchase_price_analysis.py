# -*- coding: utf-8 -*-
"""Precios de compra del producto (P-16): las compras confirmadas de una
ventana (6 meses por defecto) en la moneda de la compañía, con estadísticos,
medias móviles, resumen por semana, mes y proveedor y un gráfico semanal con
las compras atípicas. Desde aquí se abre «Aplicar costo» (W-12) con la base
elegida."""
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from markupsafe import Markup, escape

from odoo import Command, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date, formatLang

from ..models.common import WEEKDAYS
from ..models.construction_purchase_price_report import week_start
from .plan_price_wizard import BASES

CHART_WIDTH = 760
CHART_HEIGHT = 250
CHART_PAD = {'left': 56, 'right': 16, 'top': 16, 'bottom': 34}


class ConstructionPurchasePriceAnalysis(models.TransientModel):
    _name = 'construction.purchase.price.analysis'
    _description = 'Precios de compra del producto'
    _check_company_auto = True

    product_id = fields.Many2one(
        'product.product', string='Producto', check_company=True,
        domain="[('purchase_ok', '=', True)]")
    uom_id = fields.Many2one(
        related='product_id.uom_id', string='Unidad', help='Unidad del producto: la de los precios.')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    plan_id = fields.Many2one(
        'construction.resource.plan', string='Plan', check_company=True,
        domain="[('state', '=', 'draft')]",
        help='Plan en borrador al que se aplica el costo con W-12.')
    line_ids = fields.Many2many(
        'construction.resource.plan.line', 'construction_price_analysis_line_rel',
        'analysis_id', 'line_id', string='Líneas destino', check_company=True)
    week_start_day = fields.Selection(
        WEEKDAYS, string='Las semanas empiezan el', required=True,
        compute='_compute_week_start_day', store=True, readonly=False, precompute=True)
    date_from = fields.Date(
        string='Desde', required=True,
        default=lambda self: fields.Date.context_today(self) - relativedelta(months=6))
    date_to = fields.Date(string='Hasta', required=True, default=fields.Date.context_today)
    basis = fields.Selection(
        BASES, string='Base para el costo', required=True, default='weighted_6m',
        help='Base que se elige al abrir «Aplicar costo»; su fecha es la del fin de la '
             'ventana.')
    purchase_count = fields.Integer(string='Nº de compras', compute='_compute_stats')
    qty_total = fields.Float(string='Cantidad comprada', digits='Product Unit',
                             compute='_compute_stats')
    price_weighted = fields.Monetary(string='Ponderado', compute='_compute_stats')
    price_mean = fields.Monetary(string='Promedio simple', compute='_compute_stats')
    price_median = fields.Monetary(string='Mediana', compute='_compute_stats')
    price_min = fields.Monetary(string='Mínimo', compute='_compute_stats')
    price_max = fields.Monetary(string='Máximo', compute='_compute_stats')
    price_stdev = fields.Monetary(string='Desviación estándar', compute='_compute_stats')
    price_last = fields.Monetary(string='Último precio', compute='_compute_stats')
    date_last = fields.Date(string='Última compra', compute='_compute_stats')
    price_moving_4w = fields.Monetary(
        string='Media móvil 4 semanas', compute='_compute_stats',
        help='Ponderado de la semana del fin de la ventana y las 3 anteriores.')
    price_moving_3m = fields.Monetary(
        string='Media móvil 3 meses', compute='_compute_stats',
        help='Ponderado del mes del fin de la ventana y los 2 anteriores.')
    outlier_count = fields.Integer(
        string='Compras atípicas', compute='_compute_stats',
        help='Precios fuera de 1.5 veces el rango intercuartílico (con 4 compras o más).')
    chart_html = fields.Html(string='Gráfico semanal', compute='_compute_stats', sanitize=False)
    week_html = fields.Html(string='Por semana', compute='_compute_stats', sanitize=False)
    month_html = fields.Html(string='Por mes', compute='_compute_stats', sanitize=False)
    partner_html = fields.Html(string='Por proveedor', compute='_compute_stats', sanitize=False)
    purchase_ids = fields.Many2many(
        'construction.purchase.price.report', string='Compras', compute='_compute_stats',
        check_company=True)

    @api.depends('plan_id')
    def _compute_week_start_day(self):
        for wizard in self:
            wizard.week_start_day = (
                wizard.plan_id.project_id.construction_week_start_day
                or wizard.company_id.construction_week_start_day or '3')

    @api.depends('product_id', 'company_id', 'date_from', 'date_to', 'week_start_day')
    def _compute_stats(self):
        Report = self.env['construction.purchase.price.report']
        for wizard in self:
            if not wizard.product_id or not wizard.date_from or not wizard.date_to:
                stats = Report._compute_price_stats([], False)
            else:
                stats = Report._get_price_stats(
                    wizard.product_id, wizard.company_id, wizard.date_from, wizard.date_to,
                    wizard.week_start_day or '3')
            wizard.purchase_count = stats['count']
            wizard.qty_total = stats['qty']
            wizard.price_weighted = stats['weighted']
            wizard.price_mean = stats['mean']
            wizard.price_median = stats['median']
            wizard.price_min = stats['min']
            wizard.price_max = stats['max']
            wizard.price_stdev = stats['stdev']
            wizard.price_last = stats['last']
            wizard.date_last = stats['last_date']
            wizard.price_moving_4w = stats['moving_4w']
            wizard.price_moving_3m = stats['moving_3m']
            wizard.outlier_count = len(stats['outlier_ids'])
            wizard.purchase_ids = Report.browse([row['id'] for row in reversed(stats['rows'])])
            wizard.chart_html = wizard._render_chart(stats)
            wizard.week_html = wizard._render_weeks(stats)
            wizard.month_html = wizard._render_months(stats)
            wizard.partner_html = wizard._render_partners(stats)

    # ------------------------------------------------------------------
    # Presentación
    # ------------------------------------------------------------------
    def _fmt(self, value, digits=2):
        return formatLang(self.env, value or 0.0, digits=digits)

    def _html_table(self, headers, rows, numeric_from=1):
        head = Markup('').join(
            Markup('<th class="%s">%s</th>') % ('text-end' if i >= numeric_from else '', h)
            for i, h in enumerate(headers))
        body = Markup('').join(
            Markup('<tr class="%s">%s</tr>') % (row_class, Markup('').join(
                Markup('<td class="%s">%s</td>') % ('text-end' if i >= numeric_from else '', cell)
                for i, cell in enumerate(cells)))
            for row_class, cells in rows)
        return Markup(
            '<table class="table table-sm table-hover o_cp_price_table mb-0">'
            '<thead><tr>%s</tr></thead><tbody>%s</tbody></table>') % (head, body)

    def _empty(self):
        return Markup('<p class="text-muted mb-0">%s</p>') % self.env._(
            'Sin compras confirmadas en la ventana.')

    def _render_weeks(self, stats):
        if not stats['weeks']:
            return self._empty()
        uom = self.uom_id.name or ''
        rows = [('', [
            format_date(self.env, week['week']),
            str(week['count']),
            self._fmt(week['qty']),
            self._fmt(week['weighted']),
            self._fmt(week['moving_4w']),
        ]) for week in reversed(stats['weeks'])]
        return self._html_table([self.env._('Semana del'), self.env._('Compras'), uom or
                            self.env._('Cantidad'), self.env._('Ponderado'),
                            self.env._('Media 4 semanas')], rows)

    def _render_months(self, stats):
        if not stats['months']:
            return self._empty()
        uom = self.uom_id.name or ''
        rows = [('', [
            format_date(self.env, month['month'], date_format='MMM-yyyy'),
            str(month['count']),
            self._fmt(month['qty']),
            self._fmt(month['weighted']),
            self._fmt(month['moving_3m']),
        ]) for month in stats['months']]
        return self._html_table([self.env._('Mes'), self.env._('Compras'), uom or
                            self.env._('Cantidad'), self.env._('Ponderado'),
                            self.env._('Media 3 meses')], rows)

    def _render_partners(self, stats):
        if not stats['partners']:
            return self._empty()
        uom = self.uom_id.name or ''
        rows = [('', [
            partner['partner'].display_name or self.env._('Sin proveedor'),
            partner['currencies'],
            str(partner['count']),
            self._fmt(partner['qty']),
            self._fmt(partner['weighted']),
            self._fmt(partner['last']),
        ]) for partner in stats['partners']]
        return self._html_table([self.env._('Proveedor'), self.env._('Moneda'),
                            self.env._('Compras'), uom or self.env._('Cantidad'),
                            self.env._('Ponderado'), self.env._('Último')], rows, numeric_from=2)

    def _render_chart(self, stats):
        """Gráfico SVG: cada punto es una semana con compras (ponderado), la
        media móvil de 4 semanas punteada y las compras atípicas en rojo. Al
        pasar el cursor sobre un punto se ven compras, cantidad y media
        móvil."""
        weeks = stats['weeks']
        if not weeks:
            return self._empty()
        outliers = [row for row in stats['rows'] if row['id'] in stats['outlier_ids']]
        start_day = self.week_start_day or '3'
        first = week_start(self.date_from or weeks[0]['week'], start_day)
        last = week_start(self.date_to or weeks[-1]['week'], start_day)
        span = max((last - first).days, 7)
        values = [w['weighted'] for w in weeks] + [w['moving_4w'] for w in weeks] + \
            [row['price'] for row in outliers]
        low, high = min(values), max(values)
        margin = (high - low) * 0.08 or max(high * 0.05, 1.0)
        low, high = max(low - margin, 0.0), high + margin
        left, right = CHART_PAD['left'], CHART_WIDTH - CHART_PAD['right']
        top, bottom = CHART_PAD['top'], CHART_HEIGHT - CHART_PAD['bottom']

        def x(day):
            return left + (right - left) * ((day - first).days / span)

        def y(value):
            return bottom - (bottom - top) * ((value - low) / (high - low))

        parts = []
        # Rejilla horizontal con 5 valores.
        for i in range(5):
            value = low + (high - low) * i / 4
            parts.append(Markup(
                '<line x1="%s" x2="%s" y1="%.1f" y2="%.1f" class="o_cp_grid"/>'
                '<text x="%s" y="%.1f" class="o_cp_axis" text-anchor="end">%s</text>') % (
                left, right, y(value), y(value), left - 6, y(value) + 4, self._fmt(value)))
        # Meses en el eje X.
        month = first.replace(day=1) + relativedelta(months=1)
        while month <= last + timedelta(days=6):
            parts.append(Markup(
                '<line x1="%.1f" x2="%.1f" y1="%s" y2="%s" class="o_cp_grid"/>'
                '<text x="%.1f" y="%s" class="o_cp_axis" text-anchor="middle">%s</text>') % (
                x(month), x(month), top, bottom, x(month), bottom + 18,
                format_date(self.env, month, date_format='MMM-yy')))
            month += relativedelta(months=1)
        # Media móvil de 4 semanas y ponderado semanal.
        moving = ' '.join('%.1f,%.1f' % (x(w['week']), y(w['moving_4w'])) for w in weeks)
        weekly = ' '.join('%.1f,%.1f' % (x(w['week']), y(w['weighted'])) for w in weeks)
        parts.append(Markup('<polyline points="%s" class="o_cp_moving"/>') % moving)
        parts.append(Markup('<polyline points="%s" class="o_cp_weekly"/>') % weekly)
        uom = self.uom_id.name or ''
        for week in weeks:
            tip = self.env._(
                'Semana del %(week)s: %(count)s compras, %(qty)s %(uom)s, ponderado %(price)s, '
                'media móvil 4 semanas %(moving)s', week=format_date(self.env, week['week']),
                count=week['count'], qty=self._fmt(week['qty']), uom=uom,
                price=self._fmt(week['weighted']), moving=self._fmt(week['moving_4w']))
            parts.append(Markup(
                '<circle cx="%.1f" cy="%.1f" r="4.5" class="o_cp_point"><title>%s</title>'
                '</circle>') % (x(week['week']), y(week['weighted']), tip))
        for row in outliers:
            tip = self.env._(
                'Compra atípica del %(date)s: %(partner)s, %(qty)s %(uom)s a %(price)s',
                date=format_date(self.env, row['date']), partner=row['partner'].display_name,
                qty=self._fmt(row['qty']), uom=uom, price=self._fmt(row['price']))
            parts.append(Markup(
                '<circle cx="%.1f" cy="%.1f" r="5" class="o_cp_outlier"><title>%s</title>'
                '</circle>') % (x(week_start(row['date'], start_day)), y(row['price']), tip))
        legend = Markup(
            '<div class="o_cp_chart_legend small text-muted">'
            '<span><i class="o_cp_legend_weekly"></i>%s</span>'
            '<span><i class="o_cp_legend_moving"></i>%s</span>'
            '<span><i class="o_cp_legend_outlier"></i>%s</span></div>') % (
            self.env._('Ponderado de la semana'), self.env._('Media móvil 4 semanas'),
            self.env._('Compra atípica'))
        return Markup(
            '<div class="o_cp_price_chart"><svg viewBox="0 0 %s %s" role="img" '
            'aria-label="%s">%s</svg>%s</div>') % (
            CHART_WIDTH, CHART_HEIGHT, escape(self.env._('Precio por semana')),
            Markup('').join(parts), legend)

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    @api.model
    def _action_open(self, product, plan=None, lines=None, target='new'):
        """Abre P-16 de ``product``; con ``plan``, «Aplicar costo» va a sus
        líneas (``lines`` o todas las del producto)."""
        context = {
            'default_product_id': product.id,
            'dialog_size': 'extra-large',
        }
        if plan:
            context.update({
                'default_plan_id': plan.id if plan.state == 'draft' else False,
                'default_company_id': (plan.company_id or self.env.company).id,
                'default_line_ids': [Command.set(lines.ids if lines else [])],
            })
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Precios de compra · %s', product.display_name),
            'res_model': self._name,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': target,
            'context': context,
        }

    def action_refresh(self):
        """Recalcula con la ventana editada (los cálculos ya siguen a los
        campos; el botón mantiene abierto el diálogo)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Precios de compra · %s', self.product_id.display_name),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {'dialog_size': 'extra-large'},
        }

    def action_apply_cost(self):
        """«Aplicar costo» (W-12) con la base elegida y la fecha del fin de la
        ventana."""
        self.ensure_one()
        if not self.product_id:
            raise UserError(self.env._('Elija el producto.'))
        if not self.plan_id:
            raise UserError(self.env._('Elija el plan en borrador al que se aplica el costo.'))
        self.plan_id._check_draft()
        lines = self.line_ids.filtered(
            lambda l: l.plan_id == self.plan_id and l.product_id == self.product_id)
        if not lines:
            lines = self.plan_id.line_ids.filtered(lambda l: l.product_id == self.product_id)
        if not lines:
            raise UserError(self.env._(
                'El plan %(plan)s no tiene líneas de %(product)s.',
                plan=self.plan_id.display_name, product=self.product_id.display_name))
        action = self.plan_id.action_open_price_wizard()
        action['context'] = {
            'default_plan_id': self.plan_id.id,
            'default_product_id': self.product_id.id,
            'default_basis': self.basis,
            'default_basis_date': fields.Date.to_string(self.date_to),
            'default_line_ids': [Command.set(lines.ids)],
        }
        return action
