# -*- coding: utf-8 -*-
"""Adelantos y préstamos al trabajador.

Portado de ``hr_advances_and_loans`` (v18):

* **hr.advance / hr.advance.type**: adelanto puntual descontable en la
  planilla cuyo rango cubra ``discount_date``; el tipo define el input
  de la boleta por el que se descuenta.
* **hr.loan / hr.loan.type / hr.loan.line**: préstamo con cronograma de
  cuotas iguales que vencen a fin de mes, con saldo decreciente
  (``debt``). No se puede eliminar un préstamo con cuotas ya aplicadas.
* **import_advances / import_loans** en la boleta (y por lote): vuelca
  los importes ``not payed`` del periodo a los inputs, excluyendo los
  tipos BBSS (gratificación, CTS, liquidación, vacaciones — esos van
  por el flujo de beneficios sociales) y el de quincena; añade como
  regularización los importes de tipos especiales ya pagados en el
  periodo (paridad v18). Al final marca ``paid out``.

Cambios v19: sin SQL ``.format()`` (agregación por ORM); redondeo con
``custom_round``; los tipos especiales (``grat/cts/liqui/vaca/quin_
advance_id`` y ``*_loan_id``) los añade ``hr_benefits_engine`` a
`hr.main.parameter` y aquí se leen con ``getattr`` con guard. El acta
PDF de autorización de descuento, el Excel del cronograma y el wizard
de duplicado por compañía quedan para la Fase 7.
"""
import calendar
from collections import defaultdict

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.al_hr_pe.tools import custom_round
from .hr_benefits_engine import notify_success

SPECIAL_ADVANCE_FIELDS = ('grat_advance_id', 'cts_advance_id',
                          'liqui_advance_id', 'vaca_advance_id',
                          'quin_advance_id')
SPECIAL_LOAN_FIELDS = ('grat_loan_id', 'cts_loan_id', 'liqui_loan_id',
                       'vaca_loan_id', 'quin_loan_id')


def _special_types(param, field_names):
    """Tipos especiales configurados en Parámetros Principales (leídos
    con ``getattr``: los campos los añade ``hr_benefits_engine``).
    Exige que al menos los 4 tipos BBSS estén configurados (v18)."""
    records = [getattr(param, field_name, False)
               for field_name in field_names]
    bbss = records[:4]  # grat, cts, liqui, vaca
    if not any(bbss):
        raise UserError(param.env._(
            'No se han configurado los tipos de adelantos/préstamos de '
            'los BBSS en los Parámetros Principales de Nómina.'))
    return [record for record in records if record]


class HrAdvanceType(models.Model):
    """Catálogo de tipos de adelanto (sueldo, gratificación, CTS...)."""
    _name = 'hr.advance.type'
    _description = 'Tipo de adelanto'
    _check_company_auto = True

    name = fields.Char(string='Nombre', required=True)
    input_id = fields.Many2one(
        'hr.payslip.input.type', string='Input de planillas')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)


class HrAdvance(models.Model):
    """Adelanto otorgado al empleado, descontable en su planilla."""
    _name = 'hr.advance'
    _description = 'Adelanto'
    _inherit = ['mail.thread']
    _order = 'date desc'
    _check_company_auto = True

    name = fields.Char(string='Nombre')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', tracking=True,
        check_company=True)
    amount = fields.Float(string='Monto', tracking=True)
    date = fields.Date(string='Fecha de adelanto')
    discount_date = fields.Date(string='Fecha de descuento', tracking=True)
    advance_type_id = fields.Many2one(
        'hr.advance.type', string='Tipo de adelanto', tracking=True,
        check_company=True)
    state = fields.Selection(
        selection=[('not payed', 'No pagado'), ('paid out', 'Pagado')],
        string='Estado', default='not payed', tracking=True)
    observations = fields.Text(string='Observaciones')
    active = fields.Boolean(string='Activo', default=True)

    def turn_paid_out(self):
        """Marca el adelanto como aplicado en la planilla."""
        self.write({'state': 'paid out'})

    def set_not_payed(self):
        """Revierte a ``not payed`` (cancela la aplicación)."""
        self.write({'state': 'not payed'})

    @api.onchange('employee_id', 'advance_type_id')
    def _get_name(self):
        for record in self:
            if record.advance_type_id and record.employee_id:
                record.name = '%s %s' % (record.advance_type_id.name,
                                         record.employee_id.name)

    @api.ondelete(at_uninstall=False)
    def _unlink_if_not_paid(self):
        """Borrar un adelanto ``paid out`` rompería la trazabilidad del
        descuento ya aplicado; primero use «Cambiar a no pagado»."""
        if any(advance.state == 'paid out' for advance in self):
            raise UserError(self.env._(
                'No puede eliminar un adelanto que ya fue aplicado.'))


class HrLoanType(models.Model):
    """Catálogo de tipos de préstamo (regular, contra grati, CTS...)."""
    _name = 'hr.loan.type'
    _description = 'Tipo de préstamo'
    _check_company_auto = True

    name = fields.Char(string='Nombre', required=True)
    input_id = fields.Many2one(
        'hr.payslip.input.type', string='Input de planillas')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)


class HrLoan(models.Model):
    """Préstamo al empleado con cronograma de cuotas iguales."""
    _name = 'hr.loan'
    _description = 'Préstamo'
    _inherit = ['mail.thread']
    _order = 'date desc'
    _check_company_auto = True

    name = fields.Char(string='Nombre')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', tracking=True,
        check_company=True)
    date = fields.Date(string='Fecha de préstamo', tracking=True)
    amount = fields.Float(string='Monto de préstamo', tracking=True)
    loan_type_id = fields.Many2one(
        'hr.loan.type', string='Tipo de préstamo', check_company=True)
    fees_number = fields.Integer(string='Número de cuotas', tracking=True)
    line_ids = fields.One2many('hr.loan.line', 'loan_id', string='Cuotas')
    observations = fields.Text(string='Observaciones')
    active = fields.Boolean(string='Activo', default=True)
    saldo_final = fields.Float(
        string='Saldo final', compute='_compute_saldo_final',
        help='Suma de cuotas aún no aplicadas a una boleta.')

    @api.depends('line_ids.amount', 'line_ids.validation')
    def _compute_saldo_final(self):
        for loan in self:
            loan.saldo_final = sum(loan.line_ids.filtered(
                lambda line: line.validation == 'not payed'
            ).mapped('amount'))

    @api.onchange('employee_id', 'loan_type_id')
    def _get_name(self):
        for record in self:
            if record.employee_id and record.loan_type_id:
                record.name = '%s %s' % (record.loan_type_id.name,
                                         record.employee_id.name)

    @api.ondelete(at_uninstall=False)
    def _unlink_if_not_applied(self):
        """``saldo_final != amount`` indica cuotas ya aplicadas a alguna
        boleta; eliminar el préstamo dejaría descuentos sin fuente."""
        if any(loan.saldo_final != loan.amount for loan in self):
            raise UserError(self.env._(
                'No puede eliminar un préstamo que ya fue aplicado.'))

    def get_fees(self):
        """Genera el cronograma: monto ÷ nº de cuotas (redondeo
        ``custom_round``), cada cuota vence el último día del mes y el
        saldo ``debt`` decrece cuota a cuota. Puede llamarse de nuevo si
        cambia el monto o el número de cuotas (regenera todo)."""
        self.ensure_one()
        if not (self.date and self.amount and self.fees_number > 0):
            raise UserError(self.env._(
                'Debe indicar fecha, monto y número de cuotas.'))
        self.line_ids.unlink()
        current = self.date
        debt = self.amount
        for fee in range(1, self.fees_number + 1):
            if fee != 1:
                current = current + relativedelta(months=1)
            current = current.replace(day=calendar.monthrange(
                current.year, current.month)[1])
            fee_amount = custom_round(self.amount / self.fees_number, 2)
            debt -= fee_amount
            self.env['hr.loan.line'].create({
                'loan_id': self.id,
                'fee': fee,
                'amount': fee_amount,
                'date': current,
                'debt': debt,
                'loan_type_id': self.loan_type_id.id,
            })
        return notify_success(self.env._('Se calculó correctamente.'))

    def refresh_fees(self):
        """Recalcula el saldo decreciente tras editar cuotas a mano y
        sincroniza ``fees_number`` con las líneas existentes."""
        self.ensure_one()
        total = self.amount
        for line in self.line_ids.sorted(lambda line: line.fee):
            total -= line.amount
            line.debt = total
        self.fees_number = len(self.line_ids)


class HrLoanLine(models.Model):
    _name = 'hr.loan.line'
    _description = 'Cuota de préstamo'
    _order = 'loan_id, fee'

    loan_id = fields.Many2one(
        'hr.loan', string='Préstamo', ondelete='cascade', required=True,
        index=True)
    company_id = fields.Many2one(
        related='loan_id.company_id', string='Compañía', store=True,
        index=True)
    employee_id = fields.Many2one(
        related='loan_id.employee_id', string='Empleado', store=True)
    loan_type_id = fields.Many2one(
        'hr.loan.type', string='Tipo de préstamo')
    fee = fields.Integer(string='Cuota')
    amount = fields.Float(string='Monto')
    date = fields.Date(string='Fecha de pago')
    debt = fields.Float(string='Deuda por pagar')
    validation = fields.Selection(
        selection=[('not payed', 'NO PAGADO'), ('paid out', 'PAGADO')],
        string='Validación', default='not payed')

    def turn_paid_out(self):
        self.write({'validation': 'paid out'})

    def set_not_payed(self):
        self.write({'validation': 'not payed'})


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def import_advances(self):
        """Vuelca los adelantos ``not payed`` con ``discount_date`` en
        el rango de la boleta a sus inputs, excluyendo los tipos
        especiales (BBSS + quincena); esos importes ya pagados en el
        periodo se suman como regularización (paridad v18). Marca los
        adelantos importados como ``paid out``."""
        log = ''
        for slip in self:
            param = self.env['hr.main.parameter'].get_main_parameter(
                slip.company_id)
            special = _special_types(param, SPECIAL_ADVANCE_FIELDS)
            special_ids = [record.id for record in special]
            pending = self.env['hr.advance'].search([
                ('discount_date', '>=', slip.date_from),
                ('discount_date', '<=', slip.date_to),
                ('employee_id', '=', slip.employee_id.id),
                ('company_id', '=', slip.company_id.id),
                ('state', '=', 'not payed'),
                ('advance_type_id', 'not in', special_ids),
            ])
            paid_special = self.env['hr.advance'].search([
                ('discount_date', '>=', slip.date_from),
                ('discount_date', '<=', slip.date_to),
                ('employee_id', '=', slip.employee_id.id),
                ('company_id', '=', slip.company_id.id),
                ('state', '=', 'paid out'),
                ('advance_type_id', 'in', special_ids),
            ])
            amounts = defaultdict(float)
            for advance in pending:
                amounts[advance.advance_type_id.input_id] += advance.amount
            regularization = sum(paid_special.mapped('amount'))
            for input_type, amount in amounts.items():
                if not input_type:
                    continue
                slip._set_pe_input_amount(
                    input_type, amount + regularization)
            pending.turn_paid_out()
            if amounts:
                log += '%s\n' % slip.employee_id.display_name
        if log:
            return notify_success(self.env._(
                'Se importaron adelantos a los siguientes empleados:\n'
                '%(log)s', log=log))
        return notify_success(self.env._('No se importó ningún adelanto.'))

    def import_loans(self):
        """Análogo a :meth:`import_advances` para cuotas de préstamo
        (`hr.loan.line`) con vencimiento en el rango de la boleta."""
        log = ''
        for slip in self:
            param = self.env['hr.main.parameter'].get_main_parameter(
                slip.company_id)
            special = _special_types(param, SPECIAL_LOAN_FIELDS)
            special_ids = [record.id for record in special]
            pending = self.env['hr.loan.line'].search([
                ('date', '>=', slip.date_from),
                ('date', '<=', slip.date_to),
                ('employee_id', '=', slip.employee_id.id),
                ('company_id', '=', slip.company_id.id),
                ('validation', '=', 'not payed'),
                ('loan_type_id', 'not in', special_ids),
            ])
            paid_special = self.env['hr.loan.line'].search([
                ('date', '>=', slip.date_from),
                ('date', '<=', slip.date_to),
                ('employee_id', '=', slip.employee_id.id),
                ('company_id', '=', slip.company_id.id),
                ('validation', '=', 'paid out'),
                ('loan_type_id', 'in', special_ids),
            ])
            amounts = defaultdict(float)
            for line in pending:
                amounts[line.loan_type_id.input_id] += line.amount
            regularization = sum(paid_special.mapped('amount'))
            for input_type, amount in amounts.items():
                if not input_type:
                    continue
                slip._set_pe_input_amount(
                    input_type, amount + regularization)
            pending.turn_paid_out()
            if amounts:
                log += '%s\n' % slip.employee_id.display_name
        if log:
            return notify_success(self.env._(
                'Se importaron préstamos a los siguientes empleados:\n'
                '%(log)s', log=log))
        return notify_success(self.env._('No se importó ningún préstamo.'))


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    def import_advances_by_lot(self):
        return self.slip_ids.import_advances()

    def import_loans_by_lot(self):
        return self.slip_ids.import_loans()
