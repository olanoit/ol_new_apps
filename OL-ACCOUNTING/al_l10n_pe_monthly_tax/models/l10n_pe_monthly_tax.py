# -*- coding: utf-8 -*-
"""Resumen mensual del Formulario Virtual 621 (IGV - Renta mensual).

Reúne en un documento por compañía y periodo:

* IGV: débito fiscal de las ventas y crédito fiscal de las compras del
  periodo (líneas de impuesto IGV de los asientos publicados), el saldo a
  favor del periodo anterior y el que pasa al siguiente (art. 25 de la Ley
  del IGV).
* Percepciones y retenciones del IGV sufridas en el periodo (módulos
  ``al_l10n_pe_perception`` y ``al_l10n_pe_retention``, si están
  instalados) más las no aplicadas de periodos anteriores: se descuentan del
  IGV por pagar y el saldo no aplicado pasa al mes siguiente.
* Pago a cuenta del impuesto a la renta según el régimen: Régimen General,
  el mayor entre coeficiente y 1,5 % (art. 85 de la Ley del Impuesto a la
  Renta); MYPE Tributario, 1 % hasta 300 UIT de ingresos netos en el
  ejercicio y desde que se superan, como el General (art. 6 del D. Leg.
  1269); Régimen Especial, cuota de 1,5 % (art. 120 de la Ley).
"""
import calendar
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from odoo import api, fields, models
from odoo.exceptions import UserError

from .l10n_pe_tax_regime import TAX_REGIMES

MONTHS = [(str(m), name) for m, name in enumerate(
    ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto',
     'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'], start=1)]
MYPE_LIMIT_UIT = 300
GENERAL_RATE = 0.015
MYPE_RATE = 0.01
SPECIAL_RATE = 0.015
IGV_CODE = '1000'


def _round_sol(amount):
    """El 621 se declara en soles enteros, redondeando al entero más cercano."""
    return float(Decimal(str(amount)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


class L10nPeMonthlyTax(models.Model):
    _name = 'l10n_pe.monthly.tax'
    _description = 'Declaración mensual IGV - Renta (621)'
    _inherit = ['mail.thread']
    _order = 'company_id, year desc, month_num desc'
    _check_company_auto = True

    name = fields.Char(string='Periodo', compute='_compute_name', store=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True, readonly=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    year = fields.Integer(
        string='Año', required=True, aggregator=False,
        default=lambda self: fields.Date.context_today(self).year)
    month = fields.Selection(
        MONTHS, string='Mes', required=True,
        default=lambda self: str(fields.Date.context_today(self).month))
    month_num = fields.Integer(string='Mes (número)', compute='_compute_dates', store=True)
    date_from = fields.Date(string='Desde', compute='_compute_dates', store=True)
    date_to = fields.Date(string='Hasta', compute='_compute_dates', store=True)
    state = fields.Selection(
        [('draft', 'Borrador'), ('calculated', 'Calculado'), ('declared', 'Declarado')],
        string='Estado', default='draft', required=True, copy=False, tracking=True)
    previous_id = fields.Many2one(
        'l10n_pe.monthly.tax', string='Periodo anterior', readonly=True, copy=False,
        check_company=True)

    # IGV
    sale_base = fields.Monetary(string='Base de ventas gravadas', readonly=True)
    sale_igv = fields.Monetary(string='IGV de ventas (débito fiscal)', readonly=True)
    purchase_base = fields.Monetary(string='Base de compras gravadas', readonly=True)
    purchase_igv = fields.Monetary(string='IGV de compras (crédito fiscal)', readonly=True)
    igv_result = fields.Monetary(
        string='Tributo resultante', readonly=True,
        help='Débito fiscal menos crédito fiscal del periodo.')
    previous_credit = fields.Monetary(
        string='Saldo a favor del periodo anterior',
        help='Se toma del periodo anterior calculado; sin él, escríbalo a mano.')
    next_credit = fields.Monetary(
        string='Saldo a favor para el periodo siguiente', readonly=True)
    igv_payable = fields.Monetary(
        string='IGV antes de percepciones y retenciones', readonly=True)
    previous_perception = fields.Monetary(
        string='Percepciones no aplicadas de periodos anteriores')
    period_perception = fields.Monetary(string='Percepciones del periodo', readonly=True)
    applied_perception = fields.Monetary(string='Percepciones aplicadas', readonly=True)
    next_perception = fields.Monetary(
        string='Percepciones por aplicar en el siguiente periodo', readonly=True)
    previous_retention = fields.Monetary(
        string='Retenciones no aplicadas de periodos anteriores')
    period_retention = fields.Monetary(string='Retenciones del periodo', readonly=True)
    applied_retention = fields.Monetary(string='Retenciones aplicadas', readonly=True)
    next_retention = fields.Monetary(
        string='Retenciones por aplicar en el siguiente periodo', readonly=True)
    igv_to_pay = fields.Monetary(string='IGV a pagar', readonly=True)

    # Renta
    regime = fields.Selection(TAX_REGIMES, string='Régimen', readonly=True)
    net_income = fields.Monetary(
        string='Ingresos netos del mes', readonly=True,
        help='Ventas netas y otros ingresos de gestión del periodo (cuentas de ingreso), '
             'descontadas las devoluciones y descuentos.')
    year_net_income = fields.Monetary(
        string='Ingresos netos del ejercicio a la fecha', readonly=True)
    coefficient = fields.Float(string='Coeficiente', digits=(16, 4), readonly=True)
    income_rate_label = fields.Char(string='Sistema aplicado', readonly=True)
    income_tax = fields.Monetary(string='Pago a cuenta de renta', readonly=True)
    income_tax_to_pay = fields.Monetary(string='Renta a pagar', readonly=True)
    total_to_pay = fields.Monetary(string='Total a pagar', readonly=True)
    income_move_id = fields.Many2one(
        'account.move', string='Asiento del pago a cuenta', readonly=True, copy=False,
        check_company=True)
    note = fields.Text(string='Notas')

    _period_unique = models.Constraint(
        'UNIQUE(company_id, year, month)', 'Ya existe la declaración de ese periodo.')

    @api.depends('year', 'month')
    def _compute_dates(self):
        for record in self:
            month = int(record.month or 1)
            year = record.year or fields.Date.context_today(self).year
            record.month_num = month
            record.date_from = date(year, month, 1)
            record.date_to = date(year, month, calendar.monthrange(year, month)[1])

    @api.depends('year', 'month')
    def _compute_name(self):
        for record in self:
            record.name = '621 %02d/%s' % (int(record.month or 1), record.year or '')

    # ------------------------------------------------------------------
    # Cálculo
    # ------------------------------------------------------------------
    def _previous_period(self):
        self.ensure_one()
        year, month = (self.year, self.month_num - 1) if self.month_num > 1 else (self.year - 1, 12)
        return self.search([
            ('company_id', '=', self.company_id.id), ('year', '=', year), ('month', '=', str(month)),
            ('state', 'in', ('calculated', 'declared'))], limit=1)

    def _move_line_domain(self, date_from, date_to):
        return [
            ('company_id', '=', self.company_id.id),
            ('parent_state', '=', 'posted'),
            ('date', '>=', date_from), ('date', '<=', date_to),
        ]

    def _igv_amounts(self):
        """(impuesto, base) de ventas y de compras del periodo. El impuesto sale
        de las líneas de IGV (código 1000) y la base de las líneas que lo
        llevan, ambas con su signo: las notas de crédito restan. El IGV
        retenido de la liquidación de compra (impuesto negativo) se declara en
        el formulario 1662, no aquí."""
        self.ensure_one()
        Line = self.env['account.move.line']
        totals = {}
        for use, sign in (('sale', -1), ('purchase', 1)):
            period = self._move_line_domain(self.date_from, self.date_to)
            tax = Line._read_group(period + [
                ('tax_line_id.l10n_pe_edi_tax_code', '=', IGV_CODE),
                ('tax_line_id.type_tax_use', '=', use),
                ('tax_line_id.amount', '>', 0),
            ], aggregates=['balance:sum'])
            base = Line._read_group(period + [
                ('tax_ids.l10n_pe_edi_tax_code', '=', IGV_CODE),
                ('tax_ids.type_tax_use', '=', use),
                ('tax_ids.amount', '>', 0),
            ], aggregates=['balance:sum'])
            totals[use] = (sign * (tax[0][0] or 0.0), sign * (base[0][0] or 0.0))
        return totals

    def _net_income(self, date_from, date_to):
        """Ingresos netos: saldo acreedor de las cuentas de ingresos."""
        groups = self.env['account.move.line']._read_group(
            self._move_line_domain(date_from, date_to) + [
                ('account_id.account_type', 'in', ('income', 'income_other'))],
            aggregates=['balance:sum'])
        return -(groups[0][0] or 0.0) if groups else 0.0

    def _received_amount(self, model, date_from, date_to):
        if model not in self.env:
            return 0.0
        # sudo: el resumen lo calcula contabilidad aunque las percepciones y
        # retenciones sufridas las registre tesorería; solo se suman importes.
        records_sudo = self.env[model].sudo().search([
            ('company_id', '=', self.company_id.id), ('state', '=', 'posted'),
            ('date', '>=', date_from), ('date', '<=', date_to)])
        return sum(records_sudo.mapped('amount'))

    def _income_tax(self, net_income, year_net_income):
        """(régimen, coeficiente, sistema, pago a cuenta)."""
        self.ensure_one()
        company = self.company_id.root_id
        regime = company._l10n_pe_tax_regime_at(self.date_from).regime or 'general'
        coefficient = company.l10n_pe_income_coefficient_jan_feb if self.month_num <= 2 \
            else company.l10n_pe_income_coefficient
        if regime == 'special':
            return regime, 0.0, self.env._('Régimen Especial: 1,5 %'), net_income * SPECIAL_RATE
        if regime == 'mype':
            limit = MYPE_LIMIT_UIT * company._l10n_pe_tax_uit(self.year)
            if year_net_income <= limit:
                return regime, 0.0, self.env._('MYPE hasta 300 UIT: 1 %'), net_income * MYPE_RATE
        if company.l10n_pe_income_suspended:
            return regime, coefficient, self.env._('Pagos a cuenta suspendidos'), 0.0
        by_coefficient = net_income * coefficient
        by_rate = net_income * GENERAL_RATE
        if coefficient and by_coefficient > by_rate:
            return regime, coefficient, self.env._('Coeficiente %s', ('%.4f' % coefficient).replace('.', ',')), by_coefficient
        return regime, coefficient, self.env._('1,5 % (mayor que el coeficiente)') if coefficient \
            else self.env._('1,5 % (sin impuesto calculado)'), by_rate

    def action_compute(self):
        for record in self:
            if record.state == 'declared':
                raise UserError(self.env._('El periodo %s ya está declarado.', record.name))
            record._compute_621()
        return True

    def _compute_621(self):
        self.ensure_one()
        currency = self.currency_id
        previous = self._previous_period()
        vals = {'previous_id': previous.id}
        if previous:
            vals.update(previous_credit=previous.next_credit,
                        previous_perception=previous.next_perception,
                        previous_retention=previous.next_retention)
        previous_credit = vals.get('previous_credit', self.previous_credit)
        previous_perception = vals.get('previous_perception', self.previous_perception)
        previous_retention = vals.get('previous_retention', self.previous_retention)

        igv = self._igv_amounts()
        sale_igv, sale_base = igv['sale']
        purchase_igv, purchase_base = igv['purchase']
        igv_result = currency.round(sale_igv - purchase_igv)
        after_credit = igv_result - previous_credit
        next_credit = currency.round(max(0.0, -after_credit))
        payable = currency.round(max(0.0, after_credit))

        period_perception = currency.round(self._received_amount(
            'l10n_pe.perception.received', self.date_from, self.date_to))
        perception_total = previous_perception + period_perception
        applied_perception = currency.round(min(payable, perception_total))
        payable -= applied_perception

        period_retention = currency.round(self._received_amount(
            'l10n_pe.retention.received', self.date_from, self.date_to))
        retention_total = previous_retention + period_retention
        applied_retention = currency.round(min(payable, retention_total))
        payable -= applied_retention

        net_income = currency.round(self._net_income(self.date_from, self.date_to))
        year_net_income = currency.round(self._net_income(date(self.year, 1, 1), self.date_to))
        regime, coefficient, label, income_tax = self._income_tax(net_income, year_net_income)
        igv_to_pay = _round_sol(payable)
        income_tax_to_pay = _round_sol(income_tax)
        vals.update(
            sale_base=sale_base, sale_igv=sale_igv, purchase_base=purchase_base,
            purchase_igv=purchase_igv, igv_result=igv_result, next_credit=next_credit,
            igv_payable=currency.round(max(0.0, after_credit)),
            period_perception=period_perception, applied_perception=applied_perception,
            next_perception=currency.round(perception_total - applied_perception),
            period_retention=period_retention, applied_retention=applied_retention,
            next_retention=currency.round(retention_total - applied_retention),
            igv_to_pay=igv_to_pay, regime=regime, net_income=net_income,
            year_net_income=year_net_income, coefficient=coefficient,
            income_rate_label=label, income_tax=currency.round(income_tax),
            income_tax_to_pay=income_tax_to_pay, total_to_pay=igv_to_pay + income_tax_to_pay,
            state='calculated',
        )
        self.write(vals)

    def action_declare(self):
        for record in self:
            if record.state != 'calculated':
                raise UserError(self.env._('Calcule el periodo %s antes de declararlo.', record.name))
        self.write({'state': 'declared'})
        return True

    def action_reset(self):
        for record in self:
            if record.income_move_id and record.income_move_id.state == 'posted':
                raise UserError(self.env._(
                    'Anule antes el asiento del pago a cuenta de %s.', record.name))
        self.write({'state': 'draft'})
        return True

    def action_post_income_move(self):
        """Asiento del pago a cuenta: cuenta de pagos a cuenta contra la cuenta
        por pagar, por el importe declarado."""
        self.ensure_one()
        company = self.company_id
        if self.state == 'draft':
            raise UserError(self.env._('Calcule el periodo antes de registrar el asiento.'))
        if self.income_move_id:
            raise UserError(self.env._('El periodo ya tiene su asiento del pago a cuenta.'))
        if not self.income_tax_to_pay:
            raise UserError(self.env._('El periodo no tiene pago a cuenta de renta.'))
        journal = company.l10n_pe_monthly_tax_journal_id
        debit = company.l10n_pe_income_advance_account_id
        credit = company.l10n_pe_income_payable_account_id
        if not (journal and debit and credit):
            raise UserError(self.env._(
                'Configure el diario y las cuentas del pago a cuenta en Ajustes ▸ Perú ▸ '
                'Declaración mensual.'))
        label = self.env._('Pago a cuenta del impuesto a la renta %s', self.name)
        move = self.env['account.move'].create({
            'move_type': 'entry', 'journal_id': journal.id, 'date': self.date_to,
            'company_id': company.id, 'ref': label,
            'line_ids': [
                (0, 0, {'account_id': debit.id, 'name': label, 'debit': self.income_tax_to_pay}),
                (0, 0, {'account_id': credit.id, 'name': label, 'credit': self.income_tax_to_pay}),
            ],
        })
        move.action_post()
        self.income_move_id = move
        return True
