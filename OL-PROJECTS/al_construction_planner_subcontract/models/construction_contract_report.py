# -*- coding: utf-8 -*-
"""Reportes de contratas (requerimiento CREVAL v1.0, 3.13): el resumen de
valorizaciones por orden (con IGV) con el despacho semanal y los indicadores,
y el análisis de valorizaciones (tabla dinámica de las líneas)."""
from datetime import timedelta

from odoo import api, fields, models
from odoo.tools import SQL


def _positive(operator, value):
    """¿El filtro booleano pide «sí»? Odoo 19 puede pasar ``in [True]``."""
    if operator in ('in', 'not in'):
        truthy = True in set(value)
    else:
        truthy = bool(value)
    return truthy if operator in ('=', 'in') else not truthy


class ConstructionContractSummaryReport(models.Model):
    _name = 'construction.contract.summary.report'
    _description = 'Resumen de valorizaciones de contratas'
    _auto = False
    _order = 'project_id, partner_id, order_id'
    # Lo que lee la consulta: se escribe en la base antes de leer la vista.
    _depends = {
        'purchase.order': [
            'partner_id', 'construction_project_id', 'company_id', 'currency_id',
            'construction_specialty', 'construction_uses_terms', 'amount_total', 'state',
            'construction_is_service_order', 'construction_opening_valued',
            'construction_opening_paid', 'construction_opening_advance_granted',
            'construction_opening_advance_amortized'],
        'purchase.order.line': ['order_id', 'price_subtotal', 'construction_is_additional'],
        'construction.contract.settlement': [
            'purchase_order_id', 'state', 'settlement_type', 'uses_terms', 'amount_total',
            'amount_gross', 'amount_direct', 'amount_advance', 'amount_to_pay', 'amount_net',
            'payment_date', 'date_approved', 'date_submitted', 'invoice_id'],
        'account.move': ['state', 'amount_total', 'amount_residual',
                         'construction_advance_order_id'],
        'construction.guarantee.fund': ['purchase_order_id', 'amount'],
        'construction.contract.deduction': ['purchase_order_id', 'state', 'signed_amount'],
        'project.project': ['date_start', 'date'],
    }

    order_id = fields.Many2one('purchase.order', string='Orden de contrata', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Contratista', readonly=True)
    project_id = fields.Many2one('project.project', string='Obra', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', readonly=True)
    specialty = fields.Char(string='Especialidad', readonly=True)
    uses_terms = fields.Boolean(string='Con condiciones', readonly=True)
    amount_contract = fields.Monetary(string='P. base', readonly=True, aggregator='sum',
                                      help='Monto contractual de la orden, con IGV.')
    amount_valued = fields.Monetary(string='Valorizado', readonly=True, aggregator='sum')
    valued_pct = fields.Float(string='% valorizado', readonly=True, aggregator='avg')
    amount_paid = fields.Monetary(string='Pagado', readonly=True, aggregator='sum')
    advance_to_amortize = fields.Monetary(string='Adelanto por amortizar', readonly=True,
                                          aggregator='sum')
    guarantee_amount = fields.Monetary(string='Fondo de garantía', readonly=True,
                                       aggregator='sum')
    amount_deductions = fields.Monetary(string='Deductivos', readonly=True, aggregator='sum')
    amount_to_pay = fields.Monetary(string='Saldo por pagar', readonly=True, aggregator='sum')
    next_payment_date = fields.Date(string='Próximo pago', readonly=True)
    progress_pct = fields.Float(string='Avance físico', readonly=True, aggregator='avg',
                                help='Costo directo valorizado entre el contractual.')
    time_pct = fields.Float(string='Plazo transcurrido', readonly=True, aggregator='avg',
                            help='Días transcurridos de la obra entre su plazo.')
    deductions_pct = fields.Float(string='Deductivos sobre valorizado', readonly=True,
                                  aggregator='avg')
    approval_days = fields.Float(string='Días de aprobación', readonly=True, aggregator='avg',
                                 help='Promedio de días entre la presentación y la aprobación.')
    payment_this_week = fields.Boolean(string='Despacho semanal',
                                       compute='_compute_payment_this_week',
                                       search='_search_payment_this_week')

    @property
    def _table_sql(self):
        query = SQL("""(
            SELECT po.id AS id, po.id AS order_id, po.partner_id AS partner_id,
                   po.construction_project_id AS project_id, po.company_id AS company_id,
                   po.currency_id AS currency_id, po.construction_specialty AS specialty,
                   COALESCE(po.construction_uses_terms, FALSE) AS uses_terms,
                   po.amount_total AS amount_contract,
                   COALESCE(po.construction_opening_valued, 0) + COALESCE(s.valued, 0)
                       AS amount_valued,
                   CASE WHEN po.amount_total > 0 THEN
                       (COALESCE(po.construction_opening_valued, 0) + COALESCE(s.valued, 0))
                       / po.amount_total ELSE 0 END AS valued_pct,
                   COALESCE(po.construction_opening_paid, 0) + COALESCE(inv.paid, 0)
                       + COALESCE(adv.paid, 0) AS amount_paid,
                   GREATEST(COALESCE(po.construction_opening_advance_granted, 0)
                       + COALESCE(adv.granted, 0)
                       - COALESCE(po.construction_opening_advance_amortized, 0)
                       - COALESCE(s.amortized, 0), 0) AS advance_to_amortize,
                   COALESCE(f.retained, 0) AS guarantee_amount,
                   COALESCE(d.amount, 0) AS amount_deductions,
                   COALESCE(s.to_pay, 0) AS amount_to_pay,
                   s.next_payment AS next_payment_date,
                   CASE WHEN COALESCE(l.direct, 0) > 0 THEN COALESCE(s.direct, 0) / l.direct
                       ELSE 0 END AS progress_pct,
                   CASE WHEN p.date_start IS NOT NULL AND p.date IS NOT NULL
                             AND p.date > p.date_start
                        THEN LEAST(GREATEST((CURRENT_DATE - p.date_start)::float
                                            / (p.date - p.date_start), 0), 1)
                        ELSE 0 END AS time_pct,
                   CASE WHEN COALESCE(s.valued, 0) > 0 THEN COALESCE(d.amount, 0) / s.valued
                       ELSE 0 END AS deductions_pct,
                   COALESCE(s.approval_days, 0) AS approval_days
              FROM purchase_order po
              LEFT JOIN project_project p ON p.id = po.construction_project_id
              LEFT JOIN (
                    SELECT purchase_order_id,
                           SUM(CASE WHEN uses_terms THEN amount_total ELSE amount_gross END)
                               AS valued,
                           SUM(amount_direct) AS direct,
                           SUM(amount_advance) AS amortized,
                           MIN(CASE WHEN state = 'approved' THEN payment_date END) AS next_payment,
                           AVG(EXTRACT(EPOCH FROM (date_approved - date_submitted)) / 86400.0)
                               AS approval_days,
                           SUM(CASE WHEN state = 'approved'
                                    THEN CASE WHEN uses_terms THEN amount_to_pay ELSE amount_net END
                                    ELSE 0 END) AS to_pay
                      FROM construction_contract_settlement
                     WHERE state IN ('approved', 'paid') AND settlement_type != 'opening'
                     GROUP BY purchase_order_id) s ON s.purchase_order_id = po.id
              LEFT JOIN (
                    SELECT st.purchase_order_id, SUM(m.amount_total - m.amount_residual) AS paid
                      FROM construction_contract_settlement st
                      JOIN account_move m ON m.id = st.invoice_id AND m.state = 'posted'
                     GROUP BY st.purchase_order_id) inv ON inv.purchase_order_id = po.id
              LEFT JOIN (
                    SELECT construction_advance_order_id AS order_id,
                           SUM(amount_total) AS granted,
                           SUM(amount_total - amount_residual) AS paid
                      FROM account_move
                     WHERE state = 'posted' AND construction_advance_order_id IS NOT NULL
                     GROUP BY construction_advance_order_id) adv ON adv.order_id = po.id
              LEFT JOIN (
                    SELECT purchase_order_id, SUM(amount) AS retained
                      FROM construction_guarantee_fund
                     GROUP BY purchase_order_id) f ON f.purchase_order_id = po.id
              LEFT JOIN (
                    SELECT purchase_order_id, SUM(signed_amount) AS amount
                      FROM construction_contract_deduction
                     WHERE state = 'applied'
                     GROUP BY purchase_order_id) d ON d.purchase_order_id = po.id
              LEFT JOIN (
                    SELECT order_id, SUM(price_subtotal) AS direct
                      FROM purchase_order_line
                     WHERE NOT COALESCE(construction_is_additional, FALSE)
                     GROUP BY order_id) l ON l.order_id = po.id
             WHERE po.construction_is_service_order AND po.state != 'cancel'
        )""")
        # Como el _table_sql base: se escribe en la base lo que lee la consulta.
        to_flush = [self.env[model]._fields[fname]
                    for model, fnames in self._depends.items() for fname in fnames]
        return SQL("%s", query, to_flush=to_flush)

    @api.model
    def _week_bounds(self):
        today = fields.Date.context_today(self)
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=6)

    def _compute_payment_this_week(self):
        start, end = self._week_bounds()
        for row in self:
            row.payment_this_week = bool(row.next_payment_date
                                         and start <= row.next_payment_date <= end)

    def _search_payment_this_week(self, operator, value):
        start, end = self._week_bounds()
        domain = [('next_payment_date', '>=', start), ('next_payment_date', '<=', end)]
        positive = _positive(operator, value)
        return domain if positive else [
            '|', '|', ('next_payment_date', '=', False), ('next_payment_date', '<', start),
            ('next_payment_date', '>', end)]

    def _report_usd_rate(self):
        """Tipo de cambio del día (dólar) para el encabezado del impreso."""
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        company = self.company_id or self.env.company
        if not usd or usd == company.currency_id:
            return 0.0
        return usd._get_conversion_rate(usd, company.currency_id, company,
                                        fields.Date.context_today(self))

    def _report_sale_order_name(self, project):
        if 'sale_order_id' in project._fields and project.sale_order_id:
            return project.sale_order_id.name
        return ''

    def _report_weekly_dispatch(self, project):
        return self.env['construction.contract.settlement'].search([
            ('project_id', '=', project.id), ('payment_this_week', '=', True)],
            order='payment_date, partner_id')

    def _report_sign_boxes(self):
        Sign = self.env['construction.contract.settlement']
        return [Sign._construction_sign_box(self.env._('Elaboró'), self.env.user,
                                            fields.Datetime.now()),
                Sign._construction_sign_box(self.env._('Aprobó'), name='', job='')]

    def action_open_order(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'purchase.order',
                'res_id': self.order_id.id, 'view_mode': 'form'}


class ConstructionContractSettlement(models.Model):
    _inherit = 'construction.contract.settlement'

    payment_this_week = fields.Boolean(
        string='Despacho semanal', compute='_compute_payment_this_week',
        search='_search_payment_this_week',
        help='Aprobada y con fecha de pago en la semana en curso.')

    def _compute_payment_this_week(self):
        start, end = self.env['construction.contract.summary.report']._week_bounds()
        for settlement in self:
            settlement.payment_this_week = settlement.state == 'approved' and bool(
                settlement.payment_date and start <= settlement.payment_date <= end)

    def _search_payment_this_week(self, operator, value):
        start, end = self.env['construction.contract.summary.report']._week_bounds()
        domain = [('state', '=', 'approved'), ('payment_date', '>=', start),
                  ('payment_date', '<=', end)]
        positive = _positive(operator, value)
        return domain if positive else [
            '|', '|', ('state', '!=', 'approved'), ('payment_date', '<', start),
            ('payment_date', '>', end)]


class ConstructionContractSettlementLine(models.Model):
    _inherit = 'construction.contract.settlement.line'

    # Análisis de valorizaciones (3.13): obra, contratista, partida,
    # especialidad, mes y estado.
    project_id = fields.Many2one(related='settlement_id.project_id', string='Obra', store=True,
                                 index=True)
    partner_id = fields.Many2one(related='settlement_id.partner_id', string='Contratista',
                                 store=True, index=True)
    state = fields.Selection(related='settlement_id.state', string='Estado', store=True)
    period_end = fields.Date(related='settlement_id.period_end', string='Corte', store=True)
    specialty = fields.Char(related='purchase_line_id.order_id.construction_specialty',
                            string='Especialidad', store=True)
