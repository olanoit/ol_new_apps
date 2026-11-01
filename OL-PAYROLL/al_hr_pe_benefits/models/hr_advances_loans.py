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
  periodo (paridad v18). Al final marca ``paid out``. En la boleta del
  mes del cese trae además todo lo pendiente de vencimiento posterior:
  las cuotas vencen a fin de mes y con un cese a mitad de mes quedaban
  fuera de la última boleta para siempre.
* **_l10n_pe_pending_advances / _l10n_pe_discount_benefit_advances**: los
  adelantos y préstamos de tipo BBSS (gratificación, CTS, vacaciones,
  liquidación) los descuenta el proceso respectivo al exportar a su
  boleta, con el tope del 50 % cuando van contra la CTS (art. 40 del TUO
  de la Ley de CTS). Cada importe guarda la boleta donde se descontó.

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
from odoo.addons.al_hr_pe.models.display_name import pe_join
from odoo.exceptions import UserError

from odoo.addons.al_hr_pe.tools import custom_round
from .hr_benefits_engine import notify_success
from .hr_benefits_engine import ensure_slips_draft

SPECIAL_ADVANCE_FIELDS = ('grat_advance_id', 'cts_advance_id',
                          'liqui_advance_id', 'vaca_advance_id',
                          'quin_advance_id')
SPECIAL_LOAN_FIELDS = ('grat_loan_id', 'cts_loan_id', 'liqui_loan_id',
                       'vaca_loan_id', 'quin_loan_id')
# Tipos BBSS que descuenta su propio proceso (prefijo de los campos
# ``<tipo>_advance_id`` / ``<tipo>_loan_id`` de los parámetros).
BENEFIT_KINDS = ('grat', 'cts', 'liqui', 'vaca')


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
        'hr.salary.rule', domain=[('input_usage_payslip', '=', True)], string='Entrada de la boleta',
        help='Entrada de la boleta por la que se descuenta el adelanto.')
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
        'hr.employee', string='Trabajador', tracking=True,
        check_company=True)
    amount = fields.Float(string='Importe', tracking=True)
    date = fields.Date(string='Fecha de adelanto')
    discount_date = fields.Date(
        string='Fecha de descuento', tracking=True,
        help='Se descuenta en la boleta cuyo periodo incluye esta fecha.')
    advance_type_id = fields.Many2one(
        'hr.advance.type', string='Tipo de adelanto', tracking=True,
        check_company=True)
    state = fields.Selection(
        selection=[('not payed', 'No pagado'), ('paid out', 'Pagado')],
        string='Estado', default='not payed', tracking=True,
        help='Pagado: ya se descontó en una boleta.')
    observations = fields.Text(string='Observaciones')
    active = fields.Boolean(string='Activo', default=True)
    l10n_pe_payslip_id = fields.Many2one(
        'hr.payslip', string='Descontado en', readonly=True, copy=False,
        index='btree_not_null', ondelete='set null',
        help='Boleta en la que se descontó el adelanto.')

    def turn_paid_out(self):
        """Marca el adelanto como aplicado en la planilla."""
        self.write({'state': 'paid out'})

    def action_set_unpaid(self):
        """Revierte a ``not payed`` (cancela la aplicación)."""
        self.write({'state': 'not payed', 'l10n_pe_payslip_id': False})

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
        'hr.salary.rule', domain=[('input_usage_payslip', '=', True)], string='Entrada de la boleta',
        help='Entrada de la boleta por la que se descuentan las cuotas.')
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
        'hr.employee', string='Trabajador', tracking=True,
        check_company=True)
    date = fields.Date(string='Fecha de préstamo', tracking=True)
    amount = fields.Float(string='Importe del préstamo', tracking=True)
    loan_type_id = fields.Many2one(
        'hr.loan.type', string='Tipo de préstamo', check_company=True)
    fees_number = fields.Integer(
        string='Número de cuotas', tracking=True,
        help='Cuotas mensuales iguales que vencen a fin de mes; la última '
             'absorbe el redondeo.')
    line_ids = fields.One2many('hr.loan.line', 'loan_id', string='Cuotas')
    observations = fields.Text(string='Observaciones')
    active = fields.Boolean(string='Activo', default=True)
    saldo_final = fields.Float(
        string='Saldo pendiente', compute='_compute_saldo_final',
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
        """Una cuota ya aplicada a alguna boleta impide borrar el
        préstamo: dejaría descuentos sin fuente. (v18 comparaba
        ``saldo_final != amount``, que falla por redondeo aunque no se
        haya pagado nada.)"""
        if any(line.validation == 'paid out'
               for line in self.line_ids):
            raise UserError(self.env._(
                'No puede eliminar un préstamo que ya fue aplicado.'))

    def action_generate_fees(self):
        """Genera el cronograma: monto ÷ nº de cuotas (redondeo
        ``custom_round``), cada cuota vence el último día del mes y el
        saldo ``debt`` decrece cuota a cuota. La última cuota absorbe el
        residuo del redondeo para que la suma sea exactamente el monto
        (100 / 3 → 33.33, 33.33, 33.34). Puede llamarse de nuevo si
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
            if fee == self.fees_number:
                fee_amount = custom_round(debt, 2)
            else:
                fee_amount = custom_round(
                    self.amount / self.fees_number, 2)
            debt = custom_round(debt - fee_amount, 2)
            self.env['hr.loan.line'].create({
                'loan_id': self.id,
                'fee': fee,
                'amount': fee_amount,
                'date': current,
                'debt': debt,
                'loan_type_id': self.loan_type_id.id,
            })
        return notify_success(self.env._('Se calculó correctamente.'))

    def action_recompute_fees(self):
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
    _check_company_auto = True
    _order = 'loan_id, fee'

    loan_id = fields.Many2one(
        'hr.loan', string='Préstamo', ondelete='cascade', required=True,
        index=True,
        check_company=True)
    company_id = fields.Many2one(
        related='loan_id.company_id', string='Compañía', store=True,
        index=True)
    employee_id = fields.Many2one(
        related='loan_id.employee_id', string='Trabajador', store=True)
    loan_type_id = fields.Many2one(
        'hr.loan.type', string='Tipo de préstamo',
        check_company=True)
    fee = fields.Integer(string='N.º de cuota')
    amount = fields.Float(string='Importe de la cuota')
    date = fields.Date(string='Vencimiento')
    debt = fields.Float(
        string='Saldo después de la cuota',
        help='Lo que queda por pagar tras esta cuota.')
    validation = fields.Selection(
        selection=[('not payed', 'No pagado'), ('paid out', 'Pagado')],
        string='Estado', default='not payed',
        help='Pagado: la cuota ya se descontó en una boleta.')
    l10n_pe_payslip_id = fields.Many2one(
        'hr.payslip', string='Descontada en', readonly=True, copy=False,
        index='btree_not_null', ondelete='set null',
        help='Boleta en la que se descontó la cuota.')

    def turn_paid_out(self):
        self.write({'validation': 'paid out'})

    def action_set_unpaid(self):
        self.write({'validation': 'not payed', 'l10n_pe_payslip_id': False})

    @api.depends('loan_id', 'fee')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = pe_join(rec.loan_id.display_name, 'Cuota %s' % rec.fee if rec.fee else '')


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _l10n_pe_is_cessation_slip(self):
        """La boleta cubre el cese del contrato: es la última del
        trabajador y en ella se cobra todo lo pendiente."""
        self.ensure_one()
        cessation = self.version_id.contract_date_end
        return bool(cessation and self.date_from <= cessation <= self.date_to)

    def _l10n_pe_discount_domain(self, date_field, state_field, state):
        """Dominio base de adelantos (``discount_date``/``state``) o cuotas
        (``date``/``validation``) del trabajador en el periodo de la boleta.
        En la boleta del cese no hay límite de fechas: entra todo lo
        pendiente (y lo ya descontado en ella)."""
        self.ensure_one()
        domain = [
            ('employee_id', '=', self.employee_id.id),
            ('company_id', '=', self.company_id.id),
            (state_field, '=', state),
        ]
        if self._l10n_pe_is_cessation_slip():
            if state == 'paid out':
                domain += ['|', ('l10n_pe_payslip_id', '=', self.id),
                           '&', (date_field, '>=', self.date_from),
                           (date_field, '<=', self.date_to)]
            return domain
        return domain + [(date_field, '>=', self.date_from),
                         (date_field, '<=', self.date_to)]

    def import_advances(self):
        """Vuelca los adelantos ``not payed`` con ``discount_date`` en
        el rango de la boleta a sus inputs, excluyendo los tipos
        especiales (BBSS + quincena); los BBSS ya pagados en el periodo
        se suman como regularización (paridad v18). Marca los adelantos
        importados como ``paid out``.

        La quincena no entra en la regularización: su exportación ya los
        descuenta en la mensual por el input de su tipo (se descontaban
        dos veces). Si ese input es el mismo que el de un tipo ordinario,
        el importe lleva ambos para que ningún flujo pise al otro. Los BBSS
        que ya descontó su proceso en esta boleta tampoco son
        regularización, pero se conservan en el input si lo comparten.
        En la boleta del cese entran también los de fecha posterior. Solo
        boletas en borrador."""
        ensure_slips_draft(self)
        log = ''
        for slip in self:
            param = self.env['hr.main.parameter'].get_main_parameter(
                slip.company_id)
            special = _special_types(param, SPECIAL_ADVANCE_FIELDS)
            special_ids = [record.id for record in special]
            quin = param.quin_advance_id
            pending = self.env['hr.advance'].search(
                slip._l10n_pe_discount_domain(
                    'discount_date', 'state', 'not payed')
                + [('advance_type_id', 'not in', special_ids)])
            paid_special = self.env['hr.advance'].search([
                ('discount_date', '>=', slip.date_from),
                ('discount_date', '<=', slip.date_to),
                ('employee_id', '=', slip.employee_id.id),
                ('company_id', '=', slip.company_id.id),
                ('state', '=', 'paid out'),
                ('advance_type_id', 'in', special_ids),
                ('advance_type_id', '!=', quin.id),
                ('l10n_pe_payslip_id', '=', False),
            ])
            # Solo se aplica (y se marca pagado) lo que tiene input: un
            # tipo sin input nunca llega a descontarse en la boleta.
            pending = pending.filtered(
                lambda advance: advance.advance_type_id.input_id)
            # El input se recalcula con TODO lo del periodo, también lo
            # importado antes: importar dos veces pisaba la primera tanda
            # (ya marcada como pagada) con la segunda.
            imported = self.env['hr.advance'].search(
                slip._l10n_pe_discount_domain(
                    'discount_date', 'state', 'paid out')
                + [('advance_type_id', 'not in', special_ids),
                   ('advance_type_id.input_id', '!=', False)],
            ) if pending else self.env['hr.advance']
            amounts = defaultdict(float)
            for advance in pending | imported:
                amounts[advance.advance_type_id.input_id] += advance.amount
            if quin.input_id in amounts:
                amounts[quin.input_id] += sum(self.env['hr.advance'].search([
                    ('discount_date', '>=', slip.date_from),
                    ('discount_date', '<=', slip.date_to),
                    ('employee_id', '=', slip.employee_id.id),
                    ('company_id', '=', slip.company_id.id),
                    ('state', '=', 'paid out'),
                    ('advance_type_id', '=', quin.id),
                ]).mapped('amount'))
            for advance in slip._l10n_pe_benefit_discounted()[0]:
                if advance.advance_type_id.input_id in amounts:
                    amounts[advance.advance_type_id.input_id] += \
                        advance.amount
            # La regularización se suma una sola vez (v18 la repetía en
            # cada tipo de input).
            regularization = sum(paid_special.mapped('amount'))
            for input_type, amount in amounts.items():
                slip._set_pe_input_amount(
                    input_type, amount + regularization)
                regularization = 0.0
            pending.write({'state': 'paid out',
                           'l10n_pe_payslip_id': slip.id})
            if amounts:
                log += '%s\n' % slip.employee_id.display_name
        if log:
            return notify_success(self.env._(
                'Se importaron adelantos a los siguientes empleados:\n'
                '%(log)s', log=log))
        return notify_success(self.env._('No se importó ningún adelanto.'))

    def import_loans(self):
        """Análogo a :meth:`import_advances` para cuotas de préstamo
        (`hr.loan.line`) con vencimiento en el rango de la boleta (la
        quincena tampoco entra en la regularización). En la boleta del
        cese entran todas las cuotas pendientes: vencen a fin de mes y con
        un cese a mitad de mes el saldo quedaba sin descontar."""
        ensure_slips_draft(self)
        log = ''
        for slip in self:
            param = self.env['hr.main.parameter'].get_main_parameter(
                slip.company_id)
            special = _special_types(param, SPECIAL_LOAN_FIELDS)
            special_ids = [record.id for record in special]
            quin = param.quin_loan_id
            pending = self.env['hr.loan.line'].search(
                slip._l10n_pe_discount_domain('date', 'validation', 'not payed')
                + [('loan_type_id', 'not in', special_ids)])
            paid_special = self.env['hr.loan.line'].search([
                ('date', '>=', slip.date_from),
                ('date', '<=', slip.date_to),
                ('employee_id', '=', slip.employee_id.id),
                ('company_id', '=', slip.company_id.id),
                ('validation', '=', 'paid out'),
                ('loan_type_id', 'in', special_ids),
                ('loan_type_id', '!=', quin.id),
                ('l10n_pe_payslip_id', '=', False),
            ])
            pending = pending.filtered(
                lambda line: line.loan_type_id.input_id)
            # Igual que en los adelantos: se suman también las cuotas del
            # periodo importadas antes.
            imported = self.env['hr.loan.line'].search(
                slip._l10n_pe_discount_domain('date', 'validation', 'paid out')
                + [('loan_type_id', 'not in', special_ids),
                   ('loan_type_id.input_id', '!=', False)],
            ) if pending else self.env['hr.loan.line']
            amounts = defaultdict(float)
            for line in pending | imported:
                amounts[line.loan_type_id.input_id] += line.amount
            if quin.input_id in amounts:
                amounts[quin.input_id] += sum(self.env['hr.loan.line'].search([
                    ('date', '>=', slip.date_from),
                    ('date', '<=', slip.date_to),
                    ('employee_id', '=', slip.employee_id.id),
                    ('company_id', '=', slip.company_id.id),
                    ('validation', '=', 'paid out'),
                    ('loan_type_id', '=', quin.id),
                ]).mapped('amount'))
            for line in slip._l10n_pe_benefit_discounted()[1]:
                if line.loan_type_id.input_id in amounts:
                    amounts[line.loan_type_id.input_id] += line.amount
            regularization = sum(paid_special.mapped('amount'))
            for input_type, amount in amounts.items():
                slip._set_pe_input_amount(
                    input_type, amount + regularization)
                regularization = 0.0
            pending.write({'validation': 'paid out',
                           'l10n_pe_payslip_id': slip.id})
            if amounts:
                log += '%s\n' % slip.employee_id.display_name
        if log:
            return notify_success(self.env._(
                'Se importaron préstamos a los siguientes empleados:\n'
                '%(log)s', log=log))
        return notify_success(self.env._('No se importó ningún préstamo.'))

    # ------------------------------------------------------------------
    # Adelantos y préstamos BBSS (gratificación, CTS, vacaciones,
    # liquidación): los descuenta su propio proceso
    # ------------------------------------------------------------------
    @api.model
    def _l10n_pe_benefit_types(self, kinds, company):
        """Tipos de adelanto y de préstamo configurados para ``kinds``
        (``'grat'``, ``'cts'``, ``'liqui'``, ``'vaca'``)."""
        if isinstance(kinds, str):
            kinds = (kinds,)
        unknown = set(kinds) - set(BENEFIT_KINDS)
        if unknown:
            raise UserError(self.env._(
                'Tipo de beneficio desconocido: %(kinds)s.',
                kinds=', '.join(sorted(unknown))))
        param = self.env['hr.main.parameter'].get_main_parameter(company)
        advance_types = self.env['hr.advance.type'].union(
            param['%s_advance_id' % kind] for kind in kinds)
        loan_types = self.env['hr.loan.type'].union(
            param['%s_loan_id' % kind] for kind in kinds)
        return advance_types, loan_types

    @api.model
    def _l10n_pe_pending_advances(self, employee, kinds, on_date=None,
                                  company=None):
        """Adelantos y cuotas de préstamo pendientes (``not payed``) del
        trabajador de los tipos BBSS ``kinds`` (``'grat'``, ``'cts'``,
        ``'liqui'``, ``'vaca'`` o una tupla de ellos), con fecha de
        descuento o vencimiento hasta ``on_date`` (sin fecha: todos, como en
        la liquidación). Devuelve ``(adelantos, cuotas)`` ordenados por
        fecha."""
        company = company or employee.company_id
        advance_types, loan_types = self._l10n_pe_benefit_types(
            kinds, company)
        base = [('employee_id', '=', employee.id),
                ('company_id', '=', company.id)]
        advances = self.env['hr.advance'].search(base + [
            ('state', '=', 'not payed'),
            ('advance_type_id', 'in', advance_types.ids),
        ] + (['|', ('discount_date', '=', False),
              ('discount_date', '<=', on_date)] if on_date else []),
            order='discount_date, id')
        loans = self.env['hr.loan.line'].search(base + [
            ('validation', '=', 'not payed'),
            ('loan_type_id', 'in', loan_types.ids),
        ] + ([('date', '<=', on_date)] if on_date else []),
            order='date, id')
        return advances, loans

    def _l10n_pe_benefit_discounted(self, kinds=BENEFIT_KINDS):
        """Adelantos y cuotas BBSS ya descontados en esta boleta."""
        self.ensure_one()
        advance_types, loan_types = self._l10n_pe_benefit_types(
            kinds, self.company_id)
        advances = self.env['hr.advance'].search([
            ('l10n_pe_payslip_id', '=', self.id),
            ('advance_type_id', 'in', advance_types.ids)])
        loans = self.env['hr.loan.line'].search([
            ('l10n_pe_payslip_id', '=', self.id),
            ('loan_type_id', 'in', loan_types.ids)])
        return advances, loans

    def _l10n_pe_discount_benefit_advances(self, kinds, on_date=None,
                                           cap=None):
        """Descuenta en esta boleta (en borrador) los adelantos y cuotas
        BBSS pendientes de ``kinds`` hasta ``on_date``: los marca pagados
        con esta boleta y fija cada input con todo lo descontado en ella
        por ese input, de cualquier tipo (exportar dos veces no duplica y
        dos beneficios con el mismo input no se pisan). Con ``cap``
        (p. ej. el 50 % de la CTS, art. 40 del TUO de la Ley de CTS) se
        descuenta como máximo ese importe: el importe que lo rebasa se
        parte y el resto queda pendiente. Devuelve lo descontado ahora.

        El proceso que llama recalcula la boleta después."""
        self.ensure_one()
        ensure_slips_draft(self)
        advances, loans = self._l10n_pe_pending_advances(
            self.employee_id, kinds, on_date=on_date,
            company=self.company_id)
        # Lo descontado antes en esta boleta cuenta para el tope.
        done_advances, done_loans = self._l10n_pe_benefit_discounted(kinds)
        room = None if cap is None else custom_round(
            cap - sum(done_advances.mapped('amount'))
            - sum(done_loans.mapped('amount')), 2)
        discounted = 0.0
        for record, state_field in [(adv, 'state') for adv in advances] \
                + [(line, 'validation') for line in loans]:
            if room is not None and room <= 0:
                break
            amount = record.amount
            if room is not None and amount > room:
                # Se cobra hasta el tope; el saldo sigue pendiente.
                record.copy({'amount': custom_round(amount - room, 2)})
                amount = room
                record.amount = amount
            record.write({state_field: 'paid out',
                          'l10n_pe_payslip_id': self.id})
            discounted += amount
            if room is not None:
                room = custom_round(room - amount, 2)
        # Cada input se fija con TODO lo descontado en esta boleta por él,
        # sin importar los tipos de esta llamada: dos beneficios que
        # comparten input (p. ej. DES_BBSS para gratificación y CTS) no se
        # pisan, y un tipo ordinario con el mismo input se conserva.
        done_advances, done_loans = self._l10n_pe_benefit_discounted()
        inputs = (done_advances.advance_type_id.input_id
                  | done_loans.loan_type_id.input_id)
        linked_advances = self.env['hr.advance'].search([
            ('l10n_pe_payslip_id', '=', self.id),
            ('advance_type_id.input_id', 'in', inputs.ids)])
        linked_loans = self.env['hr.loan.line'].search([
            ('l10n_pe_payslip_id', '=', self.id),
            ('loan_type_id.input_id', 'in', inputs.ids)])
        totals = defaultdict(float)
        for advance in linked_advances:
            totals[advance.advance_type_id.input_id] += advance.amount
        for line in linked_loans:
            totals[line.loan_type_id.input_id] += line.amount
        for input_type, amount in totals.items():
            self._set_pe_input_amount(input_type, custom_round(amount, 2))
        return custom_round(discounted, 2)


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    def action_import_advances(self):
        return self.slip_ids.import_advances()

    def action_import_loans(self):
        return self.slip_ids.import_loans()
