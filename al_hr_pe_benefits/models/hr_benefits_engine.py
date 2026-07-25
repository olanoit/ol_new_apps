# -*- coding: utf-8 -*-
"""Motor de cálculo de beneficios sociales (CTS y gratificación).

Portado de ``hr_social_benefits/models/hr_main_parameter.py`` (v18) con
paridad de fórmulas:

* Remuneración computable = sueldo + asignación familiar (10 % RMV vía
  ``family_allowance``) + promedios de variables (regla de las 3
  apariciones en 6 meses) + 1/6 de gratificación (solo CTS).
* CTS: computable/12 por mes (÷24 pequeña empresa); semestres tipo
  '11' (may-oct, depósito noviembre) y '05' (nov-abr, depósito mayo).
* Gratificación: computable/6 por mes (÷12 pequeña empresa); tipos
  '07' (Fiestas Patrias) y '12' (Navidad); bono extraordinario
  EsSalud = total × % del seguro de la versión (Ley 29351).

El motor queda preparado para la liquidación de cese (Fase 4): las
ramas ``liquidation`` se conservan y sólo se ejecutan cuando se pasa
el registro de liquidación (el modelo ``hr.liquidation`` llega en la
Fase 4 junto con el campo ``liquidation_id`` de las líneas).
"""
import calendar
from collections import Counter
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.al_hr_pe.tools import custom_round


def notify_success(message):
    """Notificación de éxito (sustituye al popup.it del v18)."""
    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {'type': 'success', 'message': message, 'sticky': False},
    }


class HrMainParameter(models.Model):
    _inherit = 'hr.main.parameter'

    # --- Gratificación (nombres v18 conservados) ---
    gratification_input_id = fields.Many2one(
        'hr.payslip.input.type', string='Input gratificación')
    bonus_nine_input_id = fields.Many2one(
        'hr.payslip.input.type', string='Input bonificación 9 %')
    bonus_sr_ids = fields.Many2many(
        'hr.salary.rule', 'sr_bonus_main_parameter_rel',
        'main_parameter_id', 'sr_id',
        string='R.S. bonificaciones regulares',
        help='Reglas cuyos importes promedian como bonificación variable '
             '(regla de las 3 apariciones en el semestre).')
    commission_sr_ids = fields.Many2many(
        'hr.salary.rule', 'sr_commission_main_parameter_rel',
        'main_parameter_id', 'sr_id', string='R.S. comisiones')
    extra_hours_sr_id = fields.Many2one(
        'hr.salary.rule', string='R.S. sobretiempo')
    basic_sr_id = fields.Many2one(
        'hr.salary.rule', string='R.S. básico')
    household_allowance_sr_id = fields.Many2one(
        'hr.salary.rule', string='R.S. asignación familiar')
    lack_wd_ids = fields.Many2many(
        'hr.work.entry.type', 'sr_lack_main_parameter_rel',
        'main_parameter_id', 'sr_id', string='W.D. faltas')
    working_wd_ids = fields.Many2many(
        'hr.work.entry.type', 'sr_working_main_parameter_rel',
        'main_parameter_id', 'sr_id',
        string='W.D. días laborados (beneficios)')

    # --- CTS ---
    cts_input_id = fields.Many2one(
        'hr.payslip.input.type', string='Input CTS')
    medical_rest_wd_ids = fields.Many2many(
        'hr.work.entry.type', 'wd_medical_rest_parameter_rel',
        'main_parameter_id', 'wd_id', string='W.D. descanso médico')
    employee_in_charge_id = fields.Many2one(
        'hr.employee', string='Encargado liquidación semestral',
        check_company=True)
    compute_af_vac = fields.Boolean(
        string='Calcular asignación familiar en vacaciones', default=True,
        help='Incluir la asignación familiar en la remuneración computable de la liquidación vacacional.')

    # --- Liquidación de cese (Fase 4) ---
    truncated_gratification_input_id = fields.Many2one(
        'hr.payslip.input.type', string='Input gratificación trunca')
    truncated_bonus_nine_input_id = fields.Many2one(
        'hr.payslip.input.type', string='Input bonificación 9 % trunca')
    truncated_cts_input_id = fields.Many2one(
        'hr.payslip.input.type', string='Input CTS trunca')
    vacation_input_id = fields.Many2one(
        'hr.payslip.input.type', string='Input vacaciones devengadas')
    truncated_vacation_input_id = fields.Many2one(
        'hr.payslip.input.type', string='Input vacaciones truncas')

    # --- Subsidios EsSalud (Fase 4) ---
    vacation_sr_id = fields.Many2one(
        'hr.salary.rule', string='R.S. vacaciones')
    otros_sr_ids = fields.Many2many(
        'hr.salary.rule', 'sr_otros_main_parameter_rel',
        'main_parameter_id', 'sr_id', string='R.S. otros ingresos')
    lack_sr_ids = fields.Many2many(
        'hr.salary.rule', 'lack_main_parameter_rel',
        'main_parameter_id', 'sr_id',
        string='R.S. descuentos por inasistencias')
    maternidad_input_id = fields.Many2one(
        'hr.payslip.input.type', string='Input maternidad')
    enfermedad_input_id = fields.Many2one(
        'hr.payslip.input.type', string='Input enfermedad')

    # --- Utilidades D.L. 892 (Fase 4) ---
    rule_total_income = fields.Many2one(
        'hr.salary.rule', string='R.S. rem. afecta a utilidades')
    wd_dtrab = fields.Many2many(
        'hr.work.entry.type', 'wd_dtrab_main_parameter_rel',
        'main_parameter_id', 'wd_id',
        string='W.D. días trabajados (utilidades)')
    wd_falt = fields.Many2many(
        'hr.work.entry.type', 'wd_falt_main_parameter_rel',
        'main_parameter_id', 'wd_id', string='W.D. faltas (utilidades)')
    hr_input_for_results = fields.Many2one(
        'hr.payslip.input.type', string='Input utilidades')

    # --- Adelantos/préstamos: tipos especiales BBSS + quincena ---
    grat_advance_id = fields.Many2one(
        'hr.advance.type', string='Adelanto de gratificación',
        check_company=True)
    cts_advance_id = fields.Many2one(
        'hr.advance.type', string='Adelanto de CTS', check_company=True)
    liqui_advance_id = fields.Many2one(
        'hr.advance.type', string='Adelanto de liquidación',
        check_company=True)
    vaca_advance_id = fields.Many2one(
        'hr.advance.type', string='Adelanto de vacaciones',
        check_company=True)
    quin_advance_id = fields.Many2one(
        'hr.advance.type', string='Adelanto de quincena',
        check_company=True)
    grat_loan_id = fields.Many2one(
        'hr.loan.type', string='Préstamo de gratificación',
        check_company=True)
    cts_loan_id = fields.Many2one(
        'hr.loan.type', string='Préstamo de CTS', check_company=True)
    liqui_loan_id = fields.Many2one(
        'hr.loan.type', string='Préstamo de liquidación',
        check_company=True)
    vaca_loan_id = fields.Many2one(
        'hr.loan.type', string='Préstamo de vacaciones', check_company=True)
    quin_loan_id = fields.Many2one(
        'hr.loan.type', string='Préstamo de quincena', check_company=True)

    # --- Adelanto quincenal ---
    fortnightly_input_id = fields.Many2one(
        'hr.payslip.input.type', string='Input quincena')
    net_fortnightly_sr_id = fields.Many2one(
        'hr.salary.rule', string='R.S. neto quincenal')

    # --- Criterio de cálculo de la quincena (reglas *_AQ) ---
    # Las reglas de quincena consultan estos campos: sin ellos, toda
    # regla *_AQ revienta al calcularse.
    fortnightly_type = fields.Selection(
        selection=[
            ('percentage', 'Porcentaje del sueldo'),
            ('days', 'Días efectivamente trabajados'),
        ],
        string='Modo de cálculo de la quincena',
        default='percentage',
        help='"Porcentaje del sueldo": el adelanto quincenal es una '
             'fracción fija de la remuneración (tasa de abajo). '
             '"Días efectivamente trabajados": se liquida la primera '
             'quincena con los días realmente laborados.')
    tasa = fields.Float(
        string='Tasa de la quincena',
        default=0.5,
        digits=(3, 4),
        help='Fracción del sueldo que se adelanta cuando el modo es '
             '"Porcentaje del sueldo" (0.5 = 50 %).')
    compute_af = fields.Boolean(
        string='Pagar asignación familiar en la quincena',
        default=False,
        help='Si está marcado, la asignación familiar se adelanta '
             'proporcionalmente en la boleta de quincena.')
    compute_afiliacion = fields.Boolean(
        string='Descontar aportes previsionales en la quincena',
        default=False,
        help='Si está marcado, AFP/ONP se descuentan ya en la quincena; '
             'lo habitual es descontarlos íntegros en la boleta '
             'mensual.')

    def check_gratification_values(self):
        self.ensure_one()
        if not (self.gratification_input_id and self.bonus_sr_ids
                and self.commission_sr_ids and self.extra_hours_sr_id
                and self.basic_sr_id and self.household_allowance_sr_id
                and self.bonus_nine_input_id and self.lack_wd_ids
                and self.working_wd_ids):
            raise UserError(self.env._(
                'Faltan configuraciones en la pestaña Beneficios sociales '
                '(Gratificación) de los Parámetros Principales.'))

    def check_cts_values(self):
        self.ensure_one()
        if not (self.cts_input_id and self.bonus_sr_ids
                and self.commission_sr_ids and self.extra_hours_sr_id
                and self.basic_sr_id and self.household_allowance_sr_id
                and self.lack_wd_ids and self.working_wd_ids):
            raise UserError(self.env._(
                'Faltan configuraciones en la pestaña Beneficios sociales '
                '(CTS) de los Parámetros Principales.'))

    def check_liquidation_values(self):
        self.ensure_one()
        if not (self.truncated_gratification_input_id
                and self.truncated_bonus_nine_input_id
                and self.truncated_cts_input_id
                and self.vacation_input_id
                and self.truncated_vacation_input_id
                and self.basic_sr_id and self.household_allowance_sr_id
                and self.commission_sr_ids and self.bonus_sr_ids
                and self.extra_hours_sr_id and self.lack_wd_ids
                and self.working_wd_ids):
            raise UserError(self.env._(
                'Faltan configuraciones en la pestaña Beneficios '
                'sociales (Liquidación) de los Parámetros Principales.'))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @api.model
    def get_first_version(self, employee):
        """Primer «contrato» del empleado: la versión con
        ``contract_date_start`` más antigua (v18: get_first_contract)."""
        versions = employee.version_ids.filtered('contract_date_start')
        if not versions:
            raise UserError(self.env._(
                'El empleado %(employee)s no tiene ninguna versión con '
                'fecha de inicio de contrato.',
                employee=employee.display_name))
        return min(versions, key=lambda v: v.contract_date_start)

    @api.model
    def calculate_bonus(self, admission_date, date_from, months, lines):
        """Promedio de variables (regla peruana de las 3 apariciones).

        Cada código de regla que aparezca >= 3 veces en el semestre (y
        con >= 3 meses laborados) promedia ÷6, o ÷meses trabajados si el
        empleado ingresó después del inicio del semestre. Idéntico al
        v18 (``calculate_bonus``).
        """
        codes = Counter(lines.mapped('code'))
        total = 0.0
        for key, value in codes.items():
            if months >= 3 and value >= 3:
                amount = sum(lines.filtered(
                    lambda line: line.code == key).mapped('total'))
                if admission_date > date_from:
                    amount = custom_round(amount / months, 2)
                else:
                    amount = custom_round(amount / 6, 2)
            else:
                amount = 0.0
            total += amount
        return total

    @api.model
    def calculate_excess_medical_rest(self, year, employee, company,
                                      cts_year=False):
        """(días subsidiados computables, exceso sobre 60) del año.

        El descanso médico computa para CTS hasta 60 días al año
        (D.S. 001-97-TR art. 8); el exceso se descuenta como falta.
        """
        param = self.get_main_parameter(company)
        if cts_year:
            date_from = date(year - 1, 11, 1)
            date_to = date(year, 11, 1)
        else:
            date_from = date(year, 1, 1)
            date_to = date(year, 12, 1)
        lots = self.env['hr.payslip.run'].search([
            ('date_start', '>=', date_from),
            ('date_start', '<=', date_to),
            ('company_id', '=', company.id),
        ])
        worked_days = lots.slip_ids.filtered(
            lambda slip: slip.employee_id == employee
        ).mapped('worked_days_line_ids')
        medical_rest = sum(worked_days.filtered(
            lambda line: line.work_entry_type_id in param.medical_rest_wd_ids
        ).mapped('number_of_days'))
        if medical_rest >= 60:
            return 60, medical_rest - 60
        return medical_rest, 0

    @api.model
    def get_salary_history(self, employee, company, date_calculate):
        """Histórico de nómina (estructura BASE) de los 6 meses previos.

        Devuelve ``{periodo(hr.period): {bucket: importe}}`` con los
        importes agrupados por concepto según las reglas configuradas.
        Sustituye al SQL con ``.format()`` del v18 por ORM puro (regla
        de migración: sin SQL formateado).
        """
        param = self.get_main_parameter(company)
        base_struct = self.env.ref('al_hr_pe.base_structure')
        start_ref = date_calculate - relativedelta(months=6)
        date_from = date(start_ref.year, start_ref.month, 1)
        end_ref = date_calculate - relativedelta(months=1)
        date_to = date(end_ref.year, end_ref.month,
                       calendar.monthrange(end_ref.year, end_ref.month)[1])
        slips = self.env['hr.payslip'].search([
            ('employee_id', '=', employee.id),
            ('company_id', '=', company.id),
            ('struct_id', '=', base_struct.id),
            ('date_to', '>=', date_from),
            ('date_to', '<=', date_to),
        ])
        history = {}
        for slip in slips:
            bucket = history.setdefault(slip.periodo_id, {
                'wage': 0.0, 'household_allowance': 0.0, 'commission': 0.0,
                'extra_hours': 0.0, 'others_income': 0.0,
            })
            for line in slip.line_ids:
                if not line.total:
                    continue
                rule = line.salary_rule_id
                if rule == param.basic_sr_id:
                    bucket['wage'] += line.total
                elif rule == param.household_allowance_sr_id:
                    bucket['household_allowance'] += line.total
                elif rule in param.commission_sr_ids:
                    bucket['commission'] += line.total
                elif rule == param.extra_hours_sr_id:
                    bucket['extra_hours'] += line.total
                elif rule in param.bonus_sr_ids:
                    bucket['others_income'] += line.total
        return history

    # ------------------------------------------------------------------
    # Motor principal
    # ------------------------------------------------------------------
    def compute_benefits(self, record, record_type, liquidation=False):
        """Genera las líneas de CTS ('11'/'05') o gratificación
        ('07'/'12') del lote ``record``. Paridad con el v18; toda
        búsqueda filtra por la compañía del lote."""
        company = record.company_id
        year = record.year
        param = self.get_main_parameter(company)
        if record_type in ('07', '12'):
            param.check_gratification_values()
        else:
            param.check_cts_values()
        payslip_month = False
        if liquidation:
            param.check_liquidation_values()
            payslip_month = record.payslip_run_id.date_end.month

        required_gratification = {}
        if record_type == '07':
            date_from, date_to = date(year, 1, 1), date(year, 6, 30)
            month_date_from, month_date_to = \
                date(year, 6, 1), date(year, 6, 30)
        elif record_type == '12':
            if liquidation:
                date_from, date_to = date(year, 7, 1), date(year, 12, 31)
            else:
                date_from, date_to = date(year, 6, 1), date(year, 11, 30)
            month_date_from, month_date_to = \
                date(year, 12, 1), date(year, 12, 31)
        elif record_type == '11':
            date_from, date_to = date(year, 5, 1), date(year, 10, 31)
            month_date_from, month_date_to = \
                date(year, 10, 1), date(year, 10, 31)
            required_gratification = {'year': year, 'type': '07'}
        else:  # '05'
            if liquidation and payslip_month in (11, 12):
                date_from, date_to = \
                    date(year, 11, 1), date(year + 1, 4, 30)
            else:
                date_from, date_to = \
                    date(year - 1, 11, 1), date(year, 4, 30)
            month_date_from, month_date_to = \
                date(year, 4, 1), date(year, 4, 30)
            required_gratification = {'year': year - 1, 'type': '12'}

        if liquidation:
            month_lot = record.payslip_run_id
            filtered_slips = month_lot.slip_ids
            if record_type in ('05', '11'):
                filtered_slips = filtered_slips.filtered(
                    lambda slip: not slip.version_id.l10n_pe_less_than_four)
            employees = filtered_slips.filtered(
                lambda slip:
                slip.version_id.l10n_pe_labor_regime in ('general', 'small')
                and slip.version_id.situation_code == '0'
                and slip.version_id.contract_date_end
                and slip.date_from <= slip.version_id.contract_date_end
                and slip.date_to >= slip.version_id.contract_date_end
            ).employee_id
        else:
            periodo = self.env['hr.period'].search([
                ('date_start', '>=', month_date_from),
                ('date_end', '<=', month_date_to),
                ('company_id', '=', company.id),
            ], limit=1)
            if not periodo:
                raise UserError(self.env._(
                    'No existe el periodo de nómina de cierre '
                    '(%(month)s/%(year)s) para la compañía %(company)s.',
                    month=month_date_from.month, year=month_date_from.year,
                    company=company.display_name))
            month_lot = self.env['hr.payslip.run'].search([
                ('periodo_id', '=', periodo.id),
                ('company_id', '=', company.id),
            ])
            filtered_slips = month_lot.slip_ids
            if record_type in ('05', '11'):
                filtered_slips = filtered_slips.filtered(
                    lambda slip: not slip.version_id.l10n_pe_less_than_four)
            employees = filtered_slips.filtered(
                lambda slip:
                slip.version_id.l10n_pe_labor_regime in ('general', 'small')
                and slip.version_id.situation_code != '0'
            ).employee_id

        lots = self.env['hr.payslip.run'].search([
            ('date_end', '>=', date_from),
            ('date_end', '<=', date_to),
            ('company_id', '=', company.id),
        ])

        for employee in employees:
            months = days = lacks = 0
            commissions = bonus_lines = extra_hours_lines = \
                self.env['hr.payslip.line']
            month_slip = filtered_slips.filtered(
                lambda slip: slip.employee_id == employee)
            if len(month_slip) > 1:
                # Desambiguación v18 (contrato vigente) → versión vigente.
                month_slip = month_slip.filtered(
                    lambda slip: slip.version_id == employee.version_id)[:1]
            version = month_slip.version_id
            admission_date = \
                self.get_first_version(employee).contract_date_start

            remaining_wage = 0.0
            if record_type in ('05', '11'):
                if record_type == '11':
                    last_date = {'year': year, 'type': '05'}
                elif liquidation and payslip_month in (11, 12):
                    last_date = {'year': year, 'type': '11'}
                else:
                    last_date = {'year': year - 1, 'type': '11'}
                # Saldo reservado del semestre anterior (trabajador con
                # menos de un mes: su CTS pasa al depósito siguiente).
                remaining_wage = sum(self.env['hr.cts.line'].search([
                    ('employee_id', '=', employee.id),
                    ('cts_id.year', '=', last_date['year']),
                    ('cts_id.type', '=', last_date['type']),
                    ('cts_id.company_id', '=', company.id),
                    ('less_than_one_month', '=', True),
                ]).mapped('total_cts'))

            wage = version.wage
            household_allowance = \
                param.family_allowance if version.children > 0 else 0.0
            bonus_months = len(lots.slip_ids.filtered(
                lambda slip: slip.employee_id == employee))
            admission_payslip_date = \
                date(admission_date.year, admission_date.month, 1)

            if record_type == '12':
                # Navidad: los días laborados se cuentan sobre jul-dic,
                # aunque los promedios de variables usan jun-nov (v18).
                lots_wd = self.env['hr.payslip.run'].search([
                    ('date_end', '>=', date(year, 7, 1)),
                    ('date_end', '<=', date(year, 12, 31)),
                    ('company_id', '=', company.id),
                ])
                for lot in lots_wd:
                    employee_slips = lot.slip_ids.filtered(
                        lambda slip: slip.employee_id == employee
                        and slip.date_to >= admission_payslip_date
                        and slip.date_to <= month_slip.date_to)
                    worked_days = employee_slips.mapped(
                        'worked_days_line_ids')
                    working_wd = sum(worked_days.filtered(
                        lambda line: line.work_entry_type_id
                        in param.working_wd_ids).mapped('number_of_days'))
                    if working_wd >= (lot.date_end - lot.date_start).days + 1:
                        months += 1
                    else:
                        days += working_wd
                    lacks += sum(worked_days.filtered(
                        lambda line: line.work_entry_type_id
                        in param.lack_wd_ids).mapped('number_of_days'))
                for lot in lots:
                    employee_slips = lot.slip_ids.filtered(
                        lambda slip: slip.employee_id == employee
                        and slip.date_to >= admission_payslip_date
                        and slip.date_to <= month_slip.date_to)
                    salary_rules = employee_slips.mapped('line_ids')
                    commissions += salary_rules.filtered(
                        lambda line: line.salary_rule_id
                        in param.commission_sr_ids and line.total > 0)
                    bonus_lines += salary_rules.filtered(
                        lambda line: line.salary_rule_id
                        in param.bonus_sr_ids and line.total > 0)
                    extra_hours_lines += salary_rules.filtered(
                        lambda line: line.salary_rule_id
                        == param.extra_hours_sr_id and line.total > 0)
            else:
                for lot in lots:
                    employee_slips = lot.slip_ids.filtered(
                        lambda slip: slip.employee_id == employee
                        and slip.date_to >= admission_payslip_date
                        and slip.date_to <= month_slip.date_to)
                    salary_rules = employee_slips.mapped('line_ids')
                    worked_days = employee_slips.mapped(
                        'worked_days_line_ids')
                    working_wd = sum(worked_days.filtered(
                        lambda line: line.work_entry_type_id
                        in param.working_wd_ids).mapped('number_of_days'))
                    if working_wd >= (lot.date_end - lot.date_start).days + 1:
                        months += 1
                    else:
                        days += working_wd
                    lacks += sum(worked_days.filtered(
                        lambda line: line.work_entry_type_id
                        in param.lack_wd_ids).mapped('number_of_days'))
                    commissions += salary_rules.filtered(
                        lambda line: line.salary_rule_id
                        in param.commission_sr_ids and line.total > 0)
                    bonus_lines += salary_rules.filtered(
                        lambda line: line.salary_rule_id
                        in param.bonus_sr_ids and line.total > 0)
                    extra_hours_lines += salary_rules.filtered(
                        lambda line: line.salary_rule_id
                        == param.extra_hours_sr_id and line.total > 0)

            if record_type in ('07', '12'):
                if days >= 30:
                    days, months = param.get_months_of_30_days(days, months)
                days = days if record.months_and_days else 0

            commission = self.calculate_bonus(
                admission_date, date_from, bonus_months, commissions)
            bonus = self.calculate_bonus(
                admission_date, date_from, bonus_months, bonus_lines)
            extra_hours = self.calculate_bonus(
                admission_date, date_from, bonus_months, extra_hours_lines)
            computable_remuneration = (wage + household_allowance
                                       + commission + bonus + extra_hours)
            divider = 6 if record_type in ('07', '12') else 12

            sixth_of_gratification = 0.0
            if record_type in ('05', '11'):
                if liquidation:
                    cessation_date = version.contract_date_end
                    grati_lines = self.env['hr.gratification.line'].search([
                        ('employee_id', '=', employee.id),
                        ('gratification_id.year', '=', year),
                        ('gratification_id.company_id', '=', company.id),
                    ]).sorted(
                        lambda line: line.gratification_id.deposit_date)
                    if len(grati_lines) == 0:
                        required_gratification = \
                            {'year': year - 1, 'type': '12'}
                    elif len(grati_lines) == 1:
                        if grati_lines.gratification_id.deposit_date \
                                <= cessation_date:
                            required_gratification = \
                                {'year': year, 'type': '07'}
                        else:
                            required_gratification = \
                                {'year': year - 1, 'type': '12'}
                    else:
                        if grati_lines[0].gratification_id.deposit_date \
                                <= cessation_date \
                                < grati_lines[1].gratification_id.deposit_date:
                            required_gratification = \
                                {'year': year, 'type': '07'}
                        if cessation_date >= \
                                grati_lines[1].gratification_id.deposit_date:
                            required_gratification = \
                                {'year': year, 'type': '12'}
                gratification_line = \
                    self.env['hr.gratification.line'].search([
                        ('employee_id', '=', employee.id),
                        ('gratification_id.year', '=',
                         required_gratification['year']),
                        ('gratification_id.type', '=',
                         required_gratification['type']),
                        ('gratification_id.company_id', '=', company.id),
                    ])
                if gratification_line:
                    sixth_of_gratification = custom_round(
                        sum(gratification_line.mapped('total_grat')) / 6, 2)
                computable_remuneration += sixth_of_gratification

            if version.l10n_pe_labor_regime == 'general':
                amount_per_month = computable_remuneration / divider
            else:
                amount_per_month = computable_remuneration / (divider * 2)
            amount_per_day = amount_per_month / 30
            vals = {
                'employee_id': employee.id,
                'version_id': version.id,
                'admission_date': admission_date,
                'months': months,
                'days': days,
                'lacks': lacks,
                'wage': wage,
                'household_allowance': household_allowance,
                'commission': commission,
                'bonus': bonus,
                'extra_hours': extra_hours,
                'computable_remuneration': computable_remuneration,
                'amount_per_month': custom_round(amount_per_month, 2),
                'amount_per_day': custom_round(amount_per_day, 2),
            }
            # TODO(fase3-revisar): distribution_id (distribución analítica
            # del contrato v18) sin equivalente en hr.version v19.

            if record_type in ('07', '12'):
                if admission_date > month_slip.date_from:
                    continue
                if liquidation:
                    vals['compute_date'] = max(admission_date, date_from)
                    vals['cessation_date'] = version.contract_date_end
                    vals['liquidation_id'] = record.id
                else:
                    vals['gratification_id'] = record.id
                amount_per_lack = amount_per_day * lacks
                grat_per_month = custom_round(amount_per_month * months, 2)
                grat_per_day = custom_round(amount_per_day * days, 2)
                total_grat = custom_round(
                    (grat_per_month + grat_per_day) - amount_per_lack, 2)
                percent = (version.social_insurance_id.percent or 0.0) \
                    if record.with_bonus else 0.0
                bonus_essalud = custom_round(total_grat * percent * 0.01, 2)
                vals.update({
                    'amount_per_lack': custom_round(amount_per_lack, 2),
                    'grat_per_month': grat_per_month,
                    'grat_per_day': grat_per_day,
                    'total_grat': total_grat,
                    'bonus_essalud': bonus_essalud,
                    'total': custom_round(total_grat + bonus_essalud, 2),
                })
                if liquidation:
                    grati = self.env['hr.gratification'].search([
                        ('payslip_run_id', '=',
                         liquidation.payslip_run_id.id),
                        ('year', '=', liquidation.year),
                        ('type', '=', record_type),
                        ('company_id', '=', liquidation.company_id.id),
                    ])
                    if grati and grati.line_ids.filtered(
                            lambda line: line.employee_id == employee):
                        continue
                self.env['hr.gratification.line'].create(vals)
            else:
                if liquidation:
                    vals['compute_date'] = max(admission_date, date_from)
                    vals['cessation_date'] = version.contract_date_end
                    vals['liquidation_id'] = record.id
                else:
                    vals['cts_id'] = record.id
                medical_days, excess_medical_rest = \
                    self.calculate_excess_medical_rest(
                        year, employee, company, cts_year=True)
                days += medical_days
                if days >= 30:
                    days, months = param.get_months_of_30_days(days, months)
                amount_per_lack = \
                    amount_per_day * (lacks + excess_medical_rest)
                cts_per_month = custom_round(amount_per_month * months, 2)
                cts_per_day = custom_round(amount_per_day * days, 2)
                total_cts = custom_round(
                    cts_per_month + cts_per_day - amount_per_lack
                    + remaining_wage, 2)
                exchange = record.exchange_type or 1.0
                vals.update({
                    'months': months,
                    'days': days,
                    'less_than_one_month': bool(months == 0 and days > 0),
                    'exchange_type': record.exchange_type,
                    'excess_medical_rest': excess_medical_rest,
                    'sixth_of_gratification': sixth_of_gratification,
                    'amount_per_lack': custom_round(amount_per_lack, 2),
                    'cts_per_month': cts_per_month,
                    'cts_per_day': cts_per_day,
                    'total_cts': total_cts,
                    'cts_soles': total_cts,
                    'cts_dollars': custom_round(total_cts / exchange, 2),
                })
                if liquidation:
                    if admission_date > month_slip.date_from:
                        continue
                    cts = self.env['hr.cts'].search([
                        ('payslip_run_id', '=',
                         liquidation.payslip_run_id.id),
                        ('year', '=', liquidation.year),
                        ('type', '=', record_type),
                        ('company_id', '=', liquidation.company_id.id),
                    ])
                    if cts and cts.line_ids.filtered(
                            lambda line: line.employee_id == employee):
                        continue
                self.env['hr.cts.line'].create(vals)
