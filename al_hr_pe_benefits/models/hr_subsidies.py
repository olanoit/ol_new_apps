# -*- coding: utf-8 -*-
"""Subsidios EsSalud (maternidad y enfermedad).

Portado de ``hr_subsidies`` (v18). El subsidio se calcula sobre el
promedio de las remuneraciones de los 12 meses previos a la
contingencia (básico + vacaciones + asignación familiar + comisiones +
horas extras + otros ingresos − faltas) dividido entre 30 × nº de
meses con boleta. La enfermedad descuenta los primeros 20 días del año
a cargo del empleador (acumulado de días DMED en boletas del año);
la maternidad se subsidia completa. El total se reparte por periodo
(`hr.subsidies.periodo`) con estados ``not payed``/``paid out`` y se
importa a la boleta mensual vía ``import_subsidies``.

Cambios v19:

* ``hr.contract`` → ``hr.version`` (situación de baja =
  ``situation_code == '0'`` de la versión vigente).
* Fuente de contingencias: v18 leía ``hr.leave.work_suspension_id``;
  ese override no existe aún, así que el lote se alimenta de las
  suspensiones ``hr.work.suspension`` (``al_hr_pe``) con código T21
  '21' (enfermedad) o '22' (maternidad) que inician en el periodo.
  # TODO(fase4-revisar): al integrar hr_payroll_holidays, alimentar
  # desde hr.leave validados (fechas completas de la contingencia).
* Sin SQL ``.format()``: histórico salarial y acumulado DMED por ORM.
* El corte v18 del histórico conservaba el día del mes (excluía la
  boleta del mes anterior si la contingencia iniciaba a mitad de mes);
  aquí se normaliza a meses completos: 12 meses cerrados previos.
* Los campos de configuración (``vacation_sr_id``, ``otros_sr_ids``,
  ``lack_sr_ids``, ``maternidad_input_id``, ``enfermedad_input_id``)
  los añade ``hr_benefits_engine`` a `hr.main.parameter`; aquí se leen
  con ``getattr`` con guard.
* Reportes PDF/Excel de subsidios quedan para la Fase 7.
"""
import calendar
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.al_hr_pe.tools import custom_round
from .hr_benefits_engine import notify_success

ILLNESS_SUSPENSION_CODE = '21'    # T21-21: enfermedad
MATERNITY_SUSPENSION_CODE = '22'  # T21-22: maternidad
EMPLOYER_ILLNESS_DAYS = 20        # primeros 20 días a cargo del empleador


def _check_param_config(param, requirements):
    """Valida configuración leída con ``getattr`` (los campos los añade
    ``hr_benefits_engine``; mientras no existan también cuentan como
    faltantes)."""
    missing = [label for field_name, label in requirements
               if not getattr(param, field_name, False)]
    if missing:
        raise UserError(param.env._(
            'Faltan configuraciones de subsidios en los Parámetros '
            'Principales de Nómina: %(fields)s.',
            fields=', '.join(missing)))


class HrSubsidiesLot(models.Model):
    """Lote mensual de subsidios EsSalud (maternidad / enfermedad)."""
    _name = 'hr.subsidies.lot'
    _description = 'Lote de subsidios'
    _rec_name = 'periodo_id'
    _order = 'periodo_id desc'
    _check_company_auto = True

    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    periodo_id = fields.Many2one(
        'hr.period', string='Periodo', required=True, check_company=True)
    line_ids = fields.One2many(
        'hr.subsidies', 'subsidies_lot_id', string='Cálculo de subsidios')
    state = fields.Selection(
        selection=[('draft', 'Borrador'), ('done', 'Hecho')],
        string='Estado', default='draft')
    subsidies_count = fields.Integer(
        compute='_compute_subsidies_count', string='Cantidad')

    _unique_period = models.Constraint(
        'UNIQUE(company_id, periodo_id)',
        'Ya existe un lote de subsidios para ese periodo y compañía.')

    @api.depends('line_ids')
    def _compute_subsidies_count(self):
        for lot in self:
            lot.subsidies_count = len(lot.line_ids)

    def action_open_subsidies(self):
        """Abre la lista de subsidios del lote."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.subsidies',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('id', 'in', self.line_ids.ids)],
            'name': self.env._('Subsidios'),
        }

    def turn_done(self):
        """Cierra el lote: no se permite recalcular hasta reabrirlo."""
        self.write({'state': 'done'})
        return notify_success(self.env._('Se cerró exitosamente.'))

    def turn_draft(self):
        """Reabre el lote a borrador para permitir recalcular."""
        self.write({'state': 'draft'})

    def get_subsidies(self):
        """Genera los subsidios del periodo desde las suspensiones.

        Crea un `hr.subsidies` por cada `hr.work.suspension` de tipo
        '21' (enfermedad) o '22' (maternidad) que inicie dentro del
        periodo. Excluye empleados de baja (``situation_code == '0'``).
        Las líneas con ``preserve_record`` se mantienen entre corridas
        y sus duplicados recalculados se descartan (paridad v18).
        """
        self.ensure_one()
        self.line_ids.filtered(lambda sub: not sub.preserve_record).unlink()
        suspensions = self.env['hr.work.suspension'].search([
            ('company_id', '=', self.company_id.id),
            ('suspension_type_id.code', 'in',
             (ILLNESS_SUSPENSION_CODE, MATERNITY_SUSPENSION_CODE)),
            ('date_from', '>=', self.periodo_id.date_start),
            ('date_from', '<=', self.periodo_id.date_end),
        ])
        for suspension in suspensions:
            version = suspension.version_id \
                or suspension.employee_id.version_id
            if version.situation_code == '0':
                continue
            is_maternity = \
                suspension.suspension_type_id.code == \
                MATERNITY_SUSPENSION_CODE
            self.env['hr.subsidies'].create({
                'subsidies_lot_id': self.id,
                'type': 'maternity' if is_maternity else 'illness',
                'suspension_id': suspension.id,
                'employee_id': suspension.employee_id.id,
                'date_start': suspension.date_from,
                'date_end': suspension.date_to,
            })
        preserved_employees = \
            self.line_ids.filtered('preserve_record').employee_id
        self.line_ids.filtered(
            lambda sub: not sub.preserve_record
            and sub.employee_id in preserved_employees).unlink()
        return notify_success(self.env._('Se calculó exitosamente.'))


class HrSubsidies(models.Model):
    """Subsidio individual (maternidad o enfermedad) de un empleado."""
    _name = 'hr.subsidies'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Subsidio'
    _rec_name = 'employee_id'
    _order = 'date_start desc'
    _check_company_auto = True

    subsidies_lot_id = fields.Many2one(
        'hr.subsidies.lot', string='Lote de subsidios',
        ondelete='cascade', index=True)
    company_id = fields.Many2one(
        related='subsidies_lot_id.company_id', string='Compañía',
        store=True, index=True)
    type = fields.Selection(
        selection=[('maternity', 'Subsidio por maternidad'),
                   ('illness', 'Subsidio por enfermedad')],
        string='Tipo de subsidio', required=True, default='maternity')
    # v18: leave_id (hr.leave). En v19 la contingencia viene de la
    # suspensión T21 (ver docstring del módulo).
    suspension_id = fields.Many2one(
        'hr.work.suspension', string='Suspensión (T21)',
        check_company=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', check_company=True)
    date_start = fields.Date(string='Fecha de inicio')
    date_end = fields.Date(string='Fecha final')
    subsidies_line_ids = fields.One2many(
        'hr.subsidies.line', 'subsidies_id',
        string='Histórico de remuneraciones')
    subsidies_total_ids = fields.One2many(
        'hr.subsidies.total', 'subsidies_id', string='Subsidio total')
    subsidies_periodo_ids = fields.One2many(
        'hr.subsidies.periodo', 'subsidies_id',
        string='Subsidio por periodos')
    state = fields.Selection(
        selection=[('draft', 'Borrador'), ('close', 'Hecho')],
        string='Estado', index=True, readonly=True, copy=False,
        default='draft')
    is_compute_20_days = fields.Boolean(
        string='Computar 20 días', default=False,
        help='Marcar si los primeros 20 días a cargo del empleador ya '
             'fueron cubiertos en un descanso médico anterior del año.')
    preserve_record = fields.Boolean(string='No recalcular')

    def set_draft(self):
        """Reabre el subsidio eliminando todas las líneas calculadas."""
        self.subsidies_line_ids.unlink()
        self.subsidies_total_ids.unlink()
        self.subsidies_periodo_ids.unlink()
        self.write({'state': 'draft'})

    @api.ondelete(at_uninstall=False)
    def _unlink_if_draft(self):
        """Borrar un subsidio cerrado rompería la trazabilidad del
        descuento aplicado a la boleta y del reporte a EsSalud."""
        if any(subsidy.state != 'draft' for subsidy in self):
            raise UserError(self.env._(
                'No puede eliminar este subsidio: no está en estado '
                'borrador.'))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _check_configuration(self, param):
        """Port de ``check_maternidad_values`` v18."""
        _check_param_config(param, [
            ('basic_sr_id', 'R.S. básico'),
            ('vacation_sr_id', 'R.S. vacaciones'),
            ('household_allowance_sr_id', 'R.S. asignación familiar'),
            ('commission_sr_ids', 'R.S. comisiones'),
            ('extra_hours_sr_id', 'R.S. sobretiempo'),
            ('otros_sr_ids', 'R.S. otros ingresos'),
            ('lack_sr_ids', 'R.S. descuentos por inasistencias'),
            ('maternidad_input_id', 'Input maternidad'),
            ('enfermedad_input_id', 'Input enfermedad'),
        ])

    def _get_dmed_history(self):
        """Días DMED por periodo en boletas BASE del año de la
        contingencia (sustituye al SQL ``_get_sql_wd_dmed`` v18)."""
        self.ensure_one()
        base_struct = self.env.ref('al_hr_pe.base_structure')
        slips = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('company_id', '=', self.company_id.id),
            ('struct_id', '=', base_struct.id),
            ('date_to', '>=', date(self.date_start.year, 1, 1)),
        ])
        history = []
        for slip in slips:
            days = sum(slip.worked_days_line_ids.filtered(
                lambda line: line.work_entry_type_id.code == 'DMED'
            ).mapped('number_of_days'))
            if days:
                history.append((slip.periodo_id, days))
        return history

    def _get_salary_history(self, param):
        """Histórico BASE de los 12 meses cerrados previos, agrupado por
        periodo (sustituye al SQL ``_get_sql_salary`` v18)."""
        self.ensure_one()
        base_struct = self.env.ref('al_hr_pe.base_structure')
        start_ref = self.date_start - relativedelta(months=12)
        date_from = date(start_ref.year, start_ref.month, 1)
        end_ref = self.date_start - relativedelta(months=1)
        date_to = date(end_ref.year, end_ref.month, calendar.monthrange(
            end_ref.year, end_ref.month)[1])
        slips = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('company_id', '=', self.company_id.id),
            ('struct_id', '=', base_struct.id),
            ('date_to', '>=', date_from),
            ('date_to', '<=', date_to),
        ], order='date_to')
        vacation_sr = getattr(param, 'vacation_sr_id')
        otros_srs = getattr(param, 'otros_sr_ids')
        lack_srs = getattr(param, 'lack_sr_ids')
        history = {}
        for slip in slips:
            bucket = history.setdefault(slip.periodo_id, {
                'wage': 0.0, 'vacation': 0.0, 'household_allowance': 0.0,
                'commission': 0.0, 'extra_hours': 0.0,
                'others_income': 0.0, 'lacks': 0.0,
            })
            for line in slip.line_ids:
                if not line.total:
                    continue
                rule = line.salary_rule_id
                if rule == param.basic_sr_id:
                    bucket['wage'] += line.total
                elif rule == vacation_sr:
                    bucket['vacation'] += line.total
                elif rule == param.household_allowance_sr_id:
                    bucket['household_allowance'] += line.total
                elif rule in param.commission_sr_ids:
                    bucket['commission'] += line.total
                elif rule == param.extra_hours_sr_id:
                    bucket['extra_hours'] += line.total
                elif rule in otros_srs:
                    bucket['others_income'] += line.total
                elif rule in lack_srs:
                    bucket['lacks'] += line.total
        return history

    # ------------------------------------------------------------------
    # Cálculo
    # ------------------------------------------------------------------
    def get_information(self):
        """Trae el histórico de remuneraciones de los 12 meses previos.

        Enfermedad: si el acumulado de días subsidiados del año (DMED
        en boletas + días de la contingencia) no supera los 20 días a
        cargo del empleador y no se marcó ``is_compute_20_days``, no
        genera líneas y lo informa (paridad v18).
        """
        self.ensure_one()
        if not (self.date_start and self.date_end):
            raise UserError(self.env._(
                'Debe indicar las fechas de contingencia.'))
        param = self.env['hr.main.parameter'].get_main_parameter(
            self.company_id)
        self._check_configuration(param)
        if self.type == 'illness' and not self.is_compute_20_days:
            contingency_days = (self.date_end - self.date_start).days + 1
            dmed_history = self._get_dmed_history()
            total_days = contingency_days + sum(
                days for _periodo, days in dmed_history)
            if total_days <= EMPLOYER_ILLNESS_DAYS:
                log = ''.join(
                    '%d días de DMED en la planilla %s\n'
                    % (int(days), periodo.display_name)
                    for periodo, days in dmed_history)
                log += '%d días de contingencia\n' % contingency_days
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'type': 'warning',
                        'sticky': True,
                        'message': self.env._(
                            'Este trabajador aún no superó los primeros '
                            '%(limit)d días para el cálculo del '
                            'subsidio:\n\n%(log)s\nTotal días = %(total)d',
                            limit=EMPLOYER_ILLNESS_DAYS, log=log,
                            total=int(total_days)),
                    },
                }
        Line = self.env['hr.subsidies.line']
        for periodo, amounts in self._get_salary_history(param).items():
            Line.create(dict(amounts, subsidies_id=self.id,
                             periodo_id=periodo.id))
        self.state = 'close'
        return notify_success(self.env._('Generación exitosa.'))

    def get_calculation(self):
        """Calcula el subsidio total y su reparto por periodos.

        * Base diaria = total de remuneraciones ÷ (30 × meses con
          boleta).
        * Maternidad: se subsidian todos los días de la contingencia.
        * Enfermedad: se descuentan los primeros 20 días del año a
          cargo del empleador (acumulando el DMED de boletas previas
          salvo ``is_compute_20_days``).
        """
        self.ensure_one()
        if any(line.validation == 'paid out'
               for line in self.subsidies_periodo_ids):
            raise UserError(self.env._(
                'No puede recalcular: ya fue importado desde la planilla '
                'mensual. Primero cambie a "No pagado" los subsidios por '
                'periodo.'))
        self.subsidies_total_ids.unlink()
        self.subsidies_periodo_ids.unlink()

        amount = sum(self.subsidies_line_ids.mapped('total'))
        months_count = len(self.subsidies_line_ids)
        divider_days = 30 * months_count if months_count else 1
        total_days = (self.date_end - self.date_start).days + 1
        if self.type == 'maternity':
            subsidized_days = total_days
            date_start = self.date_start
        else:
            contingency_days = (self.date_end - self.date_start).days
            if not self.is_compute_20_days:
                contingency_days += sum(
                    days for _periodo, days in self._get_dmed_history())
                subsidized_days = \
                    contingency_days - (EMPLOYER_ILLNESS_DAYS - 1)
                total_days = contingency_days + 1
            else:
                subsidized_days = contingency_days + 1
                total_days = contingency_days + EMPLOYER_ILLNESS_DAYS + 1
            date_start = self.date_end \
                - relativedelta(days=subsidized_days - 1)

        daily_amount = amount / divider_days
        self.env['hr.subsidies.total'].create({
            'subsidies_id': self.id,
            'total_rem': amount,
            'sub_dia': daily_amount,
            'days_total': total_days,
            'days': subsidized_days,
            'total_sub': custom_round(daily_amount, 2) * subsidized_days,
        })

        # Reparto mensual (paridad v18, incluidos los casos borde de
        # primer/último mes).
        if date_start.year == self.date_end.year:
            months = (self.date_end.month - date_start.month) + 1
        else:
            months = (13 - date_start.month) + self.date_end.month
        current = date_start
        Periodo = self.env['hr.subsidies.periodo']
        for count in range(1, months + 1):
            last_day = calendar.monthrange(current.year, current.month)[1]
            if count == 1 and count != months:
                period_days = last_day - date_start.day + 1
            elif count == months:
                current = self.date_end
                if self.type == 'illness' and count == 1:
                    period_days = self.date_end.day - date_start.day + 1
                else:
                    period_days = self.date_end.day
            else:
                period_days = last_day
            periodo = self.env['hr.period'].search([
                ('date_start', '<=', current),
                ('date_end', '>=', current),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
            Periodo.create({
                'subsidies_id': self.id,
                'periodo_id': periodo.id,
                'days': period_days,
                'sub_dia': daily_amount,
                'total_sub': custom_round(daily_amount, 2) * period_days,
            })
            current = current + relativedelta(months=1)
        return notify_success(self.env._('Se calculó correctamente.'))


class HrSubsidiesLine(models.Model):
    _name = 'hr.subsidies.line'
    _description = 'Línea de subsidio'
    _order = 'periodo_id'

    subsidies_id = fields.Many2one(
        'hr.subsidies', string='Subsidio', ondelete='cascade',
        required=True, index=True)
    company_id = fields.Many2one(
        related='subsidies_id.company_id', string='Compañía', store=True,
        index=True)
    periodo_id = fields.Many2one('hr.period', string='Periodo')
    wage = fields.Float(string='Básico')
    vacation = fields.Float(string='Vacaciones')
    household_allowance = fields.Float(string='Asignación familiar')
    commission = fields.Float(string='Comisiones')
    extra_hours = fields.Float(string='Horas extras')
    others_income = fields.Float(string='Otros ingresos')
    lacks = fields.Float(string='Dscto. inasistencias')
    total = fields.Float(
        string='Base imponible', compute='_compute_total', store=True)

    @api.depends('wage', 'vacation', 'household_allowance', 'commission',
                 'extra_hours', 'others_income', 'lacks')
    def _compute_total(self):
        for line in self:
            line.total = (line.wage + line.vacation
                          + line.household_allowance + line.commission
                          + line.extra_hours + line.others_income
                          - line.lacks)


class HrSubsidiesTotal(models.Model):
    _name = 'hr.subsidies.total'
    _description = 'Total de subsidio'

    subsidies_id = fields.Many2one(
        'hr.subsidies', string='Subsidio', ondelete='cascade',
        required=True, index=True)
    company_id = fields.Many2one(
        related='subsidies_id.company_id', string='Compañía', store=True,
        index=True)
    total_rem = fields.Float(string='Total rem.')
    sub_dia = fields.Float(string='Sub. por día')
    days_total = fields.Integer(string='Total días')
    days = fields.Integer(string='Días sub.')
    total_sub = fields.Float(string='Total subsidio')


class HrSubsidiesPeriodo(models.Model):
    _name = 'hr.subsidies.periodo'
    _description = 'Subsidio por periodo'
    _order = 'periodo_id'

    subsidies_id = fields.Many2one(
        'hr.subsidies', string='Subsidio', ondelete='cascade',
        required=True, index=True)
    company_id = fields.Many2one(
        related='subsidies_id.company_id', string='Compañía', store=True,
        index=True)
    employee_id = fields.Many2one(
        related='subsidies_id.employee_id', string='Empleado', store=True)
    periodo_id = fields.Many2one('hr.period', string='Periodo')
    days = fields.Integer(string='Días')
    sub_dia = fields.Float(string='Sub. por día')
    total_sub = fields.Float(string='Total subsidio')
    validation = fields.Selection(
        selection=[('not payed', 'NO PAGADO'), ('paid out', 'PAGADO')],
        string='Validación', default='not payed')

    def turn_paid_out(self):
        self.write({'validation': 'paid out'})

    def set_not_payed(self):
        self.write({'validation': 'not payed'})


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _set_pe_input_amount(self, input_type, amount):
        """Fija el importe de un input en la boleta, creándolo si falta
        (en v19 las líneas de input no se autogeneran como en v18).
        Helper compartido por subsidios, adelantos/préstamos y quincena.
        """
        self.ensure_one()
        line = self.input_line_ids.filtered(
            lambda inp: inp.input_type_id == input_type)
        if line:
            line[:1].amount = amount
        else:
            self.write({'input_line_ids': [(0, 0, {
                'input_type_id': input_type.id,
                'amount': amount,
            })]})

    def import_subsidies(self):
        """Vuelca los subsidios ``not payed`` del periodo de la boleta a
        los inputs de maternidad/enfermedad y los marca ``paid out``."""
        log = ''
        for slip in self:
            param = self.env['hr.main.parameter'].get_main_parameter(
                slip.company_id)
            _check_param_config(param, [
                ('maternidad_input_id', 'Input maternidad'),
                ('enfermedad_input_id', 'Input enfermedad'),
            ])
            periodo = slip.payslip_run_id.periodo_id or slip.periodo_id
            pending = self.env['hr.subsidies.periodo'].search([
                ('periodo_id', '=', periodo.id),
                ('employee_id', '=', slip.employee_id.id),
                ('company_id', '=', slip.company_id.id),
                ('validation', '=', 'not payed'),
            ])
            if not pending:
                continue
            for subsidy_type, input_field in (
                    ('maternity', 'maternidad_input_id'),
                    ('illness', 'enfermedad_input_id')):
                lines = pending.filtered(
                    lambda p: p.subsidies_id.type == subsidy_type)
                if lines:
                    slip._set_pe_input_amount(
                        getattr(param, input_field),
                        sum(lines.mapped('total_sub')))
            pending.turn_paid_out()
            log += '%s\n' % slip.employee_id.display_name
        if log:
            return notify_success(self.env._(
                'Se importaron los subsidios de los siguientes '
                'empleados:\n%(log)s', log=log))
        return notify_success(self.env._('No se importó ningún subsidio.'))


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    def import_subsidies_by_lot(self):
        return self.slip_ids.import_subsidies()
