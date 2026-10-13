# -*- coding: utf-8 -*-
"""Contrato o línea de factoring con un factor: condiciones por defecto de las
operaciones, simulación de la liquidación y control de la línea de crédito.

Intereses (descuento por adelantado, como liquidan los factores en el Perú):
tasa efectiva anual (TEA) llevada a los días de la factura con año de 360
días: ``adelanto × ((1 + TEA) ^ (días / 360) − 1)``. La comisión es un
porcentaje del valor nominal con un mínimo por factura, más un importe fijo;
si el factor la factura, lleva IGV (los intereses están exonerados).
"""
from odoo import api, fields, models

from .factoring_account_config import MODALITIES

IGV_RATE = 0.18


class L10nPeFactoringContract(models.Model):
    _name = 'l10n_pe.factoring.contract'
    _description = 'Contrato de factoring'
    _inherit = ['mail.thread']
    _check_company_auto = True
    _order = 'factor_id, date_start desc, id desc'

    name = fields.Char(string='Contrato', required=True, tracking=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    factor_id = fields.Many2one('res.partner', string='Factor', required=True, tracking=True,
                                check_company=True)
    factor_bank_id = fields.Many2one(
        'res.partner.bank', string='Cuenta del factor', check_company=True,
        domain="[('partner_id', '=', factor_id)]",
        help='Cuenta en la que el cliente debe pagar las facturas transferidas (va en la '
             'notificación al cliente).')
    modality = fields.Selection(MODALITIES, string='Modalidad', required=True,
                                default='without_recourse', tracking=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True,
                                  default=lambda self: self.env.company.currency_id)
    date_start = fields.Date(string='Vigente desde', required=True, default=fields.Date.context_today)
    date_end = fields.Date(string='Vigente hasta')
    advance_percent = fields.Float(string='% de adelanto', digits=(5, 2), default=90.0, tracking=True)
    annual_rate = fields.Float(
        string='TEA (%)', digits=(7, 4), tracking=True,
        help='Tasa efectiva anual del descuento, aplicada al adelanto por los días hasta el '
             'vencimiento (año de 360 días).')
    min_days = fields.Integer(
        string='Días mínimos', default=0,
        help='Días mínimos que cobra el factor aunque la factura venza antes.')
    fee_percent = fields.Float(string='Comisión (% del nominal)', digits=(7, 4))
    fee_min = fields.Monetary(string='Comisión mínima por factura')
    fee_fixed = fields.Monetary(string='Comisión fija por operación')
    expense_fixed = fields.Monetary(string='Gastos por factura',
                                    help='Gastos administrativos o de CAVALI por factura.')
    fee_with_igv = fields.Boolean(
        string='La comisión lleva IGV', default=True,
        help='El factor factura la comisión con IGV (crédito fiscal). Los intereses no llevan IGV.')
    require_cavali = fields.Boolean(
        string='Exige anotación en CAVALI',
        help='Solo se ceden facturas negociables anotadas en cuenta en CAVALI (el factor recibe '
             'la transferencia allí).')
    credit_limit = fields.Monetary(
        string='Línea de crédito', tracking=True,
        help='Adelanto máximo vigente con el factor (facturas cedidas aún no cobradas). Cero: sin límite.')
    debtor_limit = fields.Monetary(
        string='Límite por cliente',
        help='Adelanto máximo vigente por cliente (deudor). Cero: sin límite.')
    used_amount = fields.Monetary(string='Línea usada', compute='_compute_used_amount')
    available_amount = fields.Monetary(string='Línea disponible', compute='_compute_used_amount')
    operation_ids = fields.One2many('l10n_pe.factoring', 'contract_id', string='Operaciones')
    note = fields.Html(string='Condiciones')

    _percent = models.Constraint(
        'CHECK(advance_percent >= 0 AND advance_percent <= 100)',
        'El porcentaje de adelanto debe estar entre 0 y 100.')

    def _active_lines(self, partner=None, exclude_operation=None):
        """Facturas cedidas con adelanto vigente (aún no cobradas ni recompradas)."""
        self.ensure_one()
        domain = [('factoring_id.contract_id', '=', self.id), ('state', '=', 'assigned')]
        if exclude_operation:
            domain.append(('factoring_id', '!=', exclude_operation.id))
        if partner:
            domain.append(('partner_id', '=', partner.id))
        return self.env['l10n_pe.factoring.line'].search(domain)

    @staticmethod
    def _outstanding(lines):
        return sum(line.advance_amount - line.advance_applied_amount for line in lines)

    @api.depends('credit_limit', 'operation_ids.state', 'operation_ids.line_ids.state',
                 'operation_ids.line_ids.advance_applied_amount')
    def _compute_used_amount(self):
        for contract in self:
            used = self._outstanding(contract._active_lines()) if contract.id else 0.0
            contract.used_amount = used
            contract.available_amount = contract.credit_limit - used if contract.credit_limit else 0.0

    # ------------------------------------------------------------------
    # Simulación
    # ------------------------------------------------------------------
    def _interest(self, advance, days):
        self.ensure_one()
        days = max(days, self.min_days or 0, 0)
        if not self.annual_rate or not days:
            return 0.0
        return self.currency_id.round(advance * ((1 + self.annual_rate / 100.0) ** (days / 360.0) - 1))

    def _fee(self, nominal):
        self.ensure_one()
        fee = nominal * (self.fee_percent or 0.0) / 100.0
        if self.fee_min:
            fee = max(fee, self.fee_min)
        return self.currency_id.round(fee)

    def _simulate(self, lines, date):
        """``{línea: {'days', 'interest', 'fee', 'expense'}}`` y los totales con el
        IGV de la comisión y la comisión fija de la operación."""
        self.ensure_one()
        result = {}
        for line in lines:
            due = line.due_date or line.move_id.invoice_date_due or date
            days = (due - date).days
            result[line] = {
                'days': max(days, self.min_days or 0, 0),
                'interest': self._interest(line.advance_amount, days),
                'fee': self._fee(line.nominal_amount),
                'expense': self.expense_fixed or 0.0,
            }
        fee = sum(v['fee'] for v in result.values()) + (self.fee_fixed or 0.0)
        igv = self.currency_id.round(fee * IGV_RATE) if self.fee_with_igv else 0.0
        totals = {
            'interest': sum(v['interest'] for v in result.values()),
            'fee': fee,
            'fee_igv': igv,
            'expense': sum(v['expense'] for v in result.values()),
        }
        return result, totals

    # ------------------------------------------------------------------
    # Línea de crédito
    # ------------------------------------------------------------------
    def _check_limits(self, operation):
        """Errores de la línea y del límite por cliente si se cede ``operation``."""
        self.ensure_one()
        errors = []
        lines = operation.line_ids.filtered(lambda l: l.state != 'cancelled')
        if operation.date and (operation.date < self.date_start
                               or (self.date_end and operation.date > self.date_end)):
            errors.append(self.env._('El contrato %(contract)s no está vigente el %(date)s.',
                                     contract=self.name, date=operation.date))
        if self.credit_limit:
            used = self._outstanding(self._active_lines(exclude_operation=operation))
            new = sum(lines.mapped('advance_amount'))
            if self.currency_id.compare_amounts(used + new, self.credit_limit) > 0:
                errors.append(self.env._(
                    'La línea de %(contract)s es %(limit)s: hay %(used)s en uso y la operación pide '
                    '%(new)s.', contract=self.name, limit=self.credit_limit, used=used, new=new))
        if self.debtor_limit:
            for partner in lines.partner_id:
                used = self._outstanding(self._active_lines(partner=partner, exclude_operation=operation))
                new = sum(lines.filtered(lambda l: l.partner_id == partner).mapped('advance_amount'))
                if self.currency_id.compare_amounts(used + new, self.debtor_limit) > 0:
                    errors.append(self.env._(
                        'El límite por cliente de %(contract)s es %(limit)s: %(partner)s tendría '
                        '%(total)s.', contract=self.name, limit=self.debtor_limit,
                        partner=partner.name, total=used + new))
        return errors
