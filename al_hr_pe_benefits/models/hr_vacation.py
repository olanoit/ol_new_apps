# -*- coding: utf-8 -*-
"""Liquidación vacacional (goce y venta de vacaciones).

Port de ``hr_leave/models/hr_vacation.py`` v18 (SOLO hr.vacation,
hr.vacation.line y hr.leave.vacation.line; los overrides de hr.leave /
hr.leave.type quedan para la integración con hr_payroll_holidays).

Adaptaciones v19:

* contrato → versión: el «contrato» del empleado es su ``hr.version``
  vigente; la fecha de ingreso es la versión con ``contract_date_start``
  más antigua. Tasas AFP desde el snapshot de la boleta
  (``l10n_pe_retirement_fund``…), tipo de comisión desde
  ``version.l10n_pe_commission_type``.
* Fuente del goce: v18 leía ``hr.leave`` con ``work_suspension_id`` tipo
  T21-23; ese override no existe aún en v19, así que se leen las
  suspensiones ``hr.work.suspension`` de tipo 23 (vacaciones) del
  periodo del lote.
  # TODO(fase3-revisar): al integrar hr_payroll_holidays, alimentar la
  # liquidación desde hr.leave validados (y poblar leave_id en
  # hr.work.suspension).
* ``account.fiscal.year`` desapareció en v19 → campo ``year``.
* Sin SQL ``.format()``: el histórico de 6 meses y el conteo de domingos
  del calendario se resuelven con ORM.
* Asignación familiar del snapshot de la boleta (10 % RMV de Parámetros
  Principales), nunca 102.5 literal.
"""
import io
from calendar import monthrange
from collections import Counter
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.al_hr_pe.tools import custom_round

LABOR_REGIMES_WITH_VACATION = ('general', 'small', 'micro')
VACATION_SUSPENSION_CODE = '23'  # T21-23: vacaciones


class HrVacation(models.Model):
    _name = 'hr.vacation'
    _description = 'Liquidación vacacional'
    _order = 'year desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Nombre')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    # v18: fiscal_year_id (account.fiscal.year, eliminado en v19).
    year = fields.Integer(
        string='Año', required=True,
        default=lambda self: fields.Date.context_today(self).year)
    payslip_run_id = fields.Many2one(
        'hr.payslip.run', string='Lote de nómina', required=True,
        check_company=True)
    line_ids = fields.One2many(
        'hr.vacation.line', 'vacation_id', string='Cálculo de vacaciones')
    state = fields.Selection(
        [('draft', 'Borrador'), ('exported', 'Exportado')],
        string='Estado', default='draft')

    @api.onchange('year', 'payslip_run_id')
    def _onchange_name(self):
        for record in self:
            if record.payslip_run_id:
                record.name = 'Vacaciones %s' % record.payslip_run_id.name

    def turn_draft(self):
        self.write({'state': 'draft'})

    def compute_vaca_line_all(self):
        self.line_ids.compute_vacation_line()
        return self._notify(self.env._('Se recalculó exitosamente.'))

    def compute_fifth(self):
        """Retención de 5ta proporcional a los días liquidados."""
        self.ensure_one()
        return self.line_ids.compute_quinta_line(self.payslip_run_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _notify(self, message):
        """Sustituye al ``popup.it`` v18 (no migrado)."""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'message': message, 'type': 'success'},
        }

    @api.model
    def _get_admission_date(self, employee):
        """Fecha de ingreso: versión con ``contract_date_start`` más
        antigua (regla del refactor contrato → versión)."""
        version = self.env['hr.version'].search(
            [('employee_id', '=', employee.id),
             ('contract_date_start', '!=', False)],
            order='contract_date_start asc, date_version asc', limit=1)
        return version.contract_date_start

    @api.model
    def _calculate_average(self, admission_date, date_from, months, lines):
        """Promedio de conceptos variables (port de
        ``hr.main.parameter.calculate_bonus`` v18): por código de regla,
        sólo si aparece en ≥3 boletas de la ventana de 6 meses; se divide
        entre 6 (o entre los meses laborados si ingresó dentro de la
        ventana)."""
        codes = Counter(lines.mapped('code'))
        total = 0.0
        for code, count in codes.items():
            if months >= 3 and count >= 3:
                amount = sum(lines.filtered(
                    lambda line: line.code == code).mapped('total'))
                if admission_date > date_from:
                    amount = custom_round(amount / months, 2)
                else:
                    amount = custom_round(amount / 6, 2)
                total += amount
        return total

    @api.model
    def _check_configuration(self, param):
        """Valida la configuración de promedios en Parámetros
        Principales (port de ``check_vacation_values`` v18). Si el campo
        aún no existe en el hr.main.parameter v19 (lo añade la fase de
        configuración de beneficios) se omite la validación y el promedio
        correspondiente vale 0 — mientras tanto todo se lee con
        ``getattr`` con guard."""
        missing = [
            label for field_name, label in [
                ('basic_sr_id', 'R.S. Básico'),
                ('household_allowance_sr_id', 'R.S. Asignación familiar'),
                ('commission_sr_ids', 'R.S. Comisiones'),
                ('bonus_sr_ids', 'R.S. Bonificaciones regulares'),
                ('extra_hours_sr_id', 'R.S. Sobretiempo'),
            ] if field_name in param._fields
            and not getattr(param, field_name, False)]
        if missing:
            raise UserError(self.env._(
                'Faltan configuraciones de vacaciones en los Parámetros '
                'Principales de Nómina: %(fields)s.',
                fields=', '.join(missing)))

    def _get_dom_record_days(self, version):
        """Récord vacacional según el calendario: 260 días si la jornada
        incluye descanso semanal DOM, 210 si no (v18 lo resolvía con SQL
        crudo sobre resource_calendar_attendance)."""
        dom_count = self.env['resource.calendar.attendance'].search_count([
            ('calendar_id', '=', version.resource_calendar_id.id),
            ('work_entry_type_id.code', '=', 'DOM'),
        ])
        return 260 if dom_count else 210

    # ------------------------------------------------------------------
    # Cálculo
    # ------------------------------------------------------------------
    def get_vacation(self):
        self.ensure_one()
        company = self.company_id
        param = self.env['hr.main.parameter'].get_main_parameter(company)
        self._check_configuration(param)
        Line = self.env['hr.vacation.line']
        Line.search([
            ('vacation_id', '=', self.id),
            ('preserve_record', '=', False),
        ]).unlink()

        lot = self.payslip_run_id
        if not lot.date_start or not lot.date_end:
            raise UserError(self.env._(
                'El lote %(lot)s no tiene fechas de inicio/fin.',
                lot=lot.display_name))
        suspension_type = self.env['hr.suspension.type'].search(
            [('code', '=', VACATION_SUSPENSION_CODE)], limit=1)
        if not suspension_type:
            raise UserError(self.env._(
                'No existe el tipo de suspensión T21 con código 23 '
                '(vacaciones).'))

        working_wd = getattr(param, 'working_wd_ids', False) or param.wd_dlab
        commission_rules = getattr(
            param, 'commission_sr_ids', self.env['hr.salary.rule'])
        bonus_rules = getattr(
            param, 'bonus_sr_ids', self.env['hr.salary.rule'])
        extra_hours_rule = getattr(
            param, 'extra_hours_sr_id', self.env['hr.salary.rule'])

        slips = lot.slip_ids.filtered(
            lambda s: s.version_id.l10n_pe_labor_regime
            in LABOR_REGIMES_WITH_VACATION
            and not s.version_id.l10n_pe_less_than_four)
        for employee in slips.mapped('employee_id'):
            month_slip = lot.slip_ids.filtered(
                lambda s: s.employee_id == employee)[:1]
            version = month_slip.version_id
            if version.situation_code == '0':
                continue
            admission_date = self._get_admission_date(employee)
            if not admission_date:
                continue

            # Goce del periodo: suspensiones T21-23 del lote.
            vacation_suspensions = self.env['hr.work.suspension'].search([
                ('employee_id', '=', employee.id),
                ('company_id', '=', company.id),
                ('suspension_type_id', '=', suspension_type.id),
                ('date_from', '>=', lot.date_start),
                ('date_from', '<=', lot.date_end),
            ])
            record_days = self._get_dom_record_days(version)

            for leave in vacation_suspensions:
                if not leave.date_from:
                    continue
                months = days = 0
                compute_date = date(
                    self.year, admission_date.month, admission_date.day)
                if (leave.date_from - admission_date).days <= 365:
                    compute_date = admission_date

                wage = version.wage
                compute_af = getattr(param, 'compute_af_vac', True)
                household_allowance = month_slip.family_allowance \
                    if compute_af and version.children > 0 else 0.0

                # Récord (meses/días trabajados) desde el cómputo.
                compute_payslip_date = date(
                    self.year, compute_date.month, 1)
                lots = self.env['hr.payslip.run'].search([
                    ('company_id', '=', company.id),
                    ('date_end', '>=', compute_payslip_date),
                    ('date_end', '<=', leave.date_from),
                ])
                total_days = 0
                for run in lots:
                    employee_slips = run.slip_ids.filtered(
                        lambda s: s.employee_id == employee)
                    worked = sum(employee_slips
                                 .mapped('worked_days_line_ids')
                                 .filtered(lambda w: w.work_entry_type_id
                                           in working_wd)
                                 .mapped('number_of_days'))
                    if worked >= (run.date_end - run.date_start).days + 1:
                        months += 1
                        total_days += worked
                    else:
                        days += worked
                days += leave.date_from.day

                # Ventana de 6 meses para promedios variables.
                date_limit_to = month_slip.date_to
                date_limit_from = date_limit_to - relativedelta(months=6)
                date_limit_from = date(
                    date_limit_from.year, date_limit_from.month, 1)
                date_limit_to = date_limit_to - relativedelta(months=1)
                date_limit_to = date(
                    date_limit_to.year, date_limit_to.month,
                    monthrange(date_limit_to.year, date_limit_to.month)[1])
                average_lots = self.env['hr.payslip.run'].search([
                    ('company_id', '=', company.id),
                    ('date_end', '>=', date_limit_from),
                    ('date_end', '<=', date_limit_to),
                ])
                average_slips = average_lots.mapped('slip_ids').filtered(
                    lambda s: s.employee_id == employee)
                bonus_months = len(average_slips)
                rule_lines = average_slips.mapped('line_ids').filtered(
                    lambda line: line.total > 0)
                commission = self._calculate_average(
                    admission_date, date_limit_from, bonus_months,
                    rule_lines.filtered(
                        lambda line: line.salary_rule_id
                        in commission_rules))
                bonus = self._calculate_average(
                    admission_date, date_limit_from, bonus_months,
                    rule_lines.filtered(
                        lambda line: line.salary_rule_id in bonus_rules))
                extra_hours = self._calculate_average(
                    admission_date, date_limit_from, bonus_months,
                    rule_lines.filtered(
                        lambda line: line.salary_rule_id
                        == extra_hours_rule))
                computable_remuneration = wage + household_allowance \
                    + commission + bonus + extra_hours

                total_days += days
                if days >= 30:
                    days, months = param.get_months_of_30_days(days, months)

                # v18 calculaba amount_per_month por régimen pero el goce
                # usa la computable directa (el ajuste por régimen sólo
                # aplica en el recálculo de línea) — se conserva EXACTO.
                advanced_vacation = computable_remuneration / 30.0 \
                    * leave.days
                total_vacation = custom_round(advanced_vacation, 2)

                membership = version.membership_id
                onp = afp_jub = afp_si = 0.0
                afp_mixed_com = afp_fixed_com = 0.0
                retirement = month_slip.l10n_pe_retirement_fund
                prima = month_slip.l10n_pe_prima_insurance
                cap = month_slip.l10n_pe_insurable_remuneration
                if membership.is_afp:
                    afp_jub = custom_round(
                        retirement / 100.0 * total_vacation, 2)
                    prima_base = min(total_vacation, cap) \
                        if cap else total_vacation
                    afp_si = 0.0 if version.l10n_pe_is_older \
                        else custom_round(prima / 100.0 * prima_base, 2)
                    if version.l10n_pe_commission_type == 'mixed':
                        afp_mixed_com = custom_round(
                            membership.mixed_commision / 100.0
                            * total_vacation, 2)
                    else:
                        afp_fixed_com = custom_round(
                            membership.fixed_commision / 100.0
                            * total_vacation, 2)
                else:
                    onp = custom_round(
                        retirement / 100.0 * total_vacation, 2)
                neto_total = custom_round(
                    total_vacation - afp_jub - afp_si - afp_mixed_com
                    - afp_fixed_com - onp, 2)

                Line.create({
                    'vacation_id': self.id,
                    'employee_id': employee.id,
                    'version_id': version.id,
                    'vacation_kind': 'rest',
                    'admission_date': admission_date,
                    'compute_date': compute_date,
                    'compute_date_ini': leave.date_from,
                    'compute_date_fin': leave.date_to,
                    'months': months,
                    'days': days,
                    'record_days': record_days,
                    'total_days': total_days,
                    'wage': wage,
                    'household_allowance': household_allowance,
                    'commission': commission,
                    'bonus': bonus,
                    'extra_hours': extra_hours,
                    'computable_remuneration': computable_remuneration,
                    'accrued_vacation': leave.days,
                    'total_vacation': total_vacation,
                    'onp': onp,
                    'afp_jub': afp_jub,
                    'afp_si': afp_si,
                    'afp_mixed_com': afp_mixed_com,
                    'afp_fixed_com': afp_fixed_com,
                    'neto_total': neto_total,
                    'total': neto_total,
                })

        # Si un empleado tiene líneas preservadas, se descartan las
        # recalculadas para no duplicar (port v18).
        preserved_employees = Line.search([
            ('vacation_id', '=', self.id),
            ('preserve_record', '=', True),
        ]).mapped('employee_id')
        self.line_ids.filtered(
            lambda line: not line.preserve_record
            and line.employee_id in preserved_employees).unlink()
        return self._notify(self.env._('Se calculó exitosamente.'))

    # ------------------------------------------------------------------
    # Exportación al lote de nóminas
    # ------------------------------------------------------------------
    def _set_input_amount(self, slip, input_type, amount):
        """Fija el importe del input en la boleta (creándolo si falta:
        en v19 las líneas de input no se autogeneran como en v18)."""
        line = slip.input_line_ids.filtered(
            lambda inp: inp.input_type_id == input_type)
        if line:
            line[:1].amount = amount
        else:
            slip.write({'input_line_ids': [(0, 0, {
                'input_type_id': input_type.id,
                'amount': amount,
            })]})

    def set_amounts(self, lines, lot):
        """Acumula por empleado y vuelca a los inputs de su boleta:
        VAC (goce), COMP_VAC (venta), ADE_VAC (adelanto neto) y QUINTA
        (retención proporcional). v18 leía los input types de Parámetros
        Principales; en v19 son data del módulo base."""
        inp_vacation = self.env.ref('al_hr_pe.input_type_VAC')
        inp_venta_vacation = self.env.ref('al_hr_pe.input_type_COMP_VAC')
        inp_ade_vacation = self.env.ref('al_hr_pe.input_type_ADE_VAC')
        inp_fifth = self.env.ref('al_hr_pe.input_type_QUINTA')

        total_vacation = total_venta_vacation = 0.0
        total_ade_vaca = total_quinta = 0.0
        previous_employee = self.env['hr.employee']
        for line in lines.sorted(key=lambda l: l.employee_id.id):
            slip = lot.slip_ids.filtered(
                lambda s: s.employee_id == line.employee_id)[:1]
            if not slip:
                continue
            if line.employee_id == previous_employee:
                if line.vacation_kind == 'rest':
                    total_vacation += line.total_vacation
                else:
                    total_venta_vacation += line.total_vacation
                total_ade_vaca += line.total
                total_quinta += line.quinta
            else:
                if line.vacation_kind == 'rest':
                    total_vacation = line.total_vacation
                    total_venta_vacation = 0.0
                else:
                    total_vacation = 0.0
                    total_venta_vacation = line.total_vacation
                total_ade_vaca = line.total
                total_quinta = line.quinta
            self._set_input_amount(slip, inp_vacation, total_vacation)
            self._set_input_amount(
                slip, inp_venta_vacation, total_venta_vacation)
            self._set_input_amount(slip, inp_ade_vacation, total_ade_vaca)
            self._set_input_amount(slip, inp_fifth, total_quinta)
            previous_employee = line.employee_id

    def export_vacation(self):
        self.ensure_one()
        self.set_amounts(self.line_ids, self.payslip_run_id)
        self.state = 'exported'
        return self._notify(self.env._('Se exportó exitosamente.'))

    # ------------------------------------------------------------------
    # Excel
    # ------------------------------------------------------------------
    def get_excel_vacation(self):
        """Excel de la liquidación. v18 escribía en ``dir_create_file``
        (eliminado); aquí se publica como adjunto y se descarga.
        # TODO(fase3-revisar): unificar formatos con el report.base
        # cuando se migre a al_hr_pe_reports.
        """
        self.ensure_one()
        import xlsxwriter  # noqa: PLC0415 — dependencia de Odoo
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('VACACIONES')
        bold = workbook.add_format(
            {'bold': True, 'border': 1, 'align': 'center',
             'text_wrap': True, 'bg_color': '#99CCFF'})
        date_fmt = workbook.add_format({'num_format': 'dd-mm-yyyy'})
        number = workbook.add_format({'num_format': '0.00'})
        headers = [
            'NRO. DOCUMENTO', 'APELLIDO PATERNO', 'APELLIDO MATERNO',
            'NOMBRES', 'FECHA INGRESO', 'INICIO VAC.', 'FIN VAC.',
            'AFILIACIÓN', 'MESES', 'DÍAS', 'SUELDO',
            'ASIGNACIÓN FAMILIAR', 'PROMEDIO COMISIÓN',
            'PROMEDIO BONIFICACIÓN', 'PROMEDIO HRS. EXTRAS',
            'REMUNERACIÓN COMPUTABLE', 'DÍAS LIQUIDADOS', 'TOTAL VAC.',
            'ONP', 'AFP JUB', 'AFP SI', 'AFP COM. MIXTA',
            'AFP COM. FIJA', 'NETO TOTAL', 'RETENCIÓN QUINTA',
            'TOTAL A PAGAR']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, bold)
        for row, line in enumerate(self.line_ids, 1):
            worksheet.write(row, 0, line.identification_id or '')
            worksheet.write(row, 1, line.last_name or '')
            worksheet.write(row, 2, line.m_last_name or '')
            worksheet.write(row, 3, line.names or '')
            for col, value in [(4, line.admission_date),
                               (5, line.compute_date_ini),
                               (6, line.compute_date_fin)]:
                if value:
                    worksheet.write_datetime(row, col, value, date_fmt)
            worksheet.write(row, 7, line.membership_id.name or '')
            worksheet.write(row, 8, line.months, number)
            worksheet.write(row, 9, line.days, number)
            for col, value in enumerate([
                    line.wage, line.household_allowance, line.commission,
                    line.bonus, line.extra_hours,
                    line.computable_remuneration, line.accrued_vacation,
                    line.total_vacation, line.onp, line.afp_jub,
                    line.afp_si, line.afp_mixed_com, line.afp_fixed_com,
                    line.neto_total, line.quinta, line.total], 10):
                worksheet.write(row, col, value, number)
        worksheet.set_column(0, len(headers) - 1, 14)
        workbook.close()
        attachment = self.env['ir.attachment'].create({
            'name': 'Vacaciones %s.xlsx' % (self.name or self.year),
            'type': 'binary',
            'raw': output.getvalue(),
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }


class HrVacationLine(models.Model):
    _name = 'hr.vacation.line'
    _description = 'Línea de liquidación vacacional'
    _order = 'employee_id'
    _check_company_auto = True

    vacation_id = fields.Many2one(
        'hr.vacation', string='Liquidación', ondelete='cascade',
        required=True, index=True)
    company_id = fields.Many2one(
        related='vacation_id.company_id', store=True, string='Compañía',
        index=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', required=True,
        check_company=True)
    version_id = fields.Many2one(
        'hr.version', string='Versión/contrato', check_company=True,
        domain="[('employee_id', '=', employee_id)]")
    identification_id = fields.Char(
        related='employee_id.identification_id', string='Nro. documento')
    last_name = fields.Char(
        related='employee_id.last_name', string='Apellido paterno')
    m_last_name = fields.Char(
        related='employee_id.m_last_name', string='Apellido materno')
    names = fields.Char(related='employee_id.names', string='Nombres')
    # v18 distinguía goce/venta por el work entry type del hr.leave.type;
    # sin el override de ausencias se marca directamente en la línea.
    vacation_kind = fields.Selection(
        [('rest', 'Goce de vacaciones'), ('sale', 'Venta de vacaciones')],
        string='Tipo', required=True, default='rest')
    admission_date = fields.Date(string='Fecha de ingreso')
    compute_date = fields.Date(string='Fecha de cómputo')
    compute_date_ini = fields.Date(string='Inicio vac.')
    compute_date_fin = fields.Date(string='Fin vac.')
    membership_id = fields.Many2one(
        related='version_id.membership_id', string='Afiliación')
    months = fields.Integer(string='Meses')
    days = fields.Integer(string='Días')
    lacks = fields.Integer(string='Faltas', default=0)
    record_days = fields.Integer(string='Récord vacacional')
    total_days = fields.Integer(string='Total días')
    wage = fields.Float(string='Sueldo')
    household_allowance = fields.Float(string='Asignación familiar')
    commission = fields.Float(string='Prom. comisión')
    bonus = fields.Float(string='Prom. bonificación')
    extra_hours = fields.Float(string='Prom. horas extras')
    computable_remuneration = fields.Float(
        string='Remuneración computable')
    accrued_vacation = fields.Integer(string='Días vac. liquidados')
    total_vacation = fields.Float(string='Total vacaciones')
    onp = fields.Float(string='(-) ONP')
    afp_jub = fields.Float(string='(-) AFP JUB')
    afp_si = fields.Float(string='(-) AFP SI')
    afp_mixed_com = fields.Float(string='(-) AFP com. mixta')
    afp_fixed_com = fields.Float(string='(-) AFP com. fija')
    neto_total = fields.Float(string='Neto vacaciones')
    quinta = fields.Float(string='(-) Retención quinta', default=0)
    total = fields.Float(string='Total a pagar')
    vacation_line_ids = fields.One2many(
        'hr.leave.vacation.line', 'leave_vacation_id',
        string='Detalle histórico')
    preserve_record = fields.Boolean(string='No recalcular')

    def compute_quinta_line(self, lot):
        """Retención de 5ta proporcional: toma la retención QUINTA del
        mes anterior al lote y la prorratea por los días liquidados."""
        date_from = lot.date_start - relativedelta(months=1)
        date_to = date(date_from.year, date_from.month,
                       monthrange(date_from.year, date_from.month)[1])
        Slip = self.env['hr.payslip']
        for line in self:
            past_slips = Slip.search([
                ('employee_id', '=', line.employee_id.id),
                ('company_id', '=', line.company_id.id),
                ('date_from', '=', date_from),
                ('date_to', '=', date_to),
            ])
            ret_quinta = sum(past_slips.mapped('line_ids').filtered(
                lambda pl: pl.salary_rule_id.code == 'QUINTA'
            ).mapped('total'))
            line.quinta = ret_quinta / 30.0 * line.accrued_vacation
            line.total = line.neto_total - line.quinta
        return self.env['hr.vacation']._notify(
            self.env._('Se importó la retención de quinta.'))

    def compute_vacation_line(self):
        """Recalcula la línea a partir de sus componentes editables
        (port EXACTO del v18: aquí sí se ajusta por régimen laboral y la
        prima AFP se topa a la remuneración máxima asegurable)."""
        for record in self:
            lot = record.vacation_id.payslip_run_id
            month_slip = lot.slip_ids.filtered(
                lambda s: s.employee_id == record.employee_id)[:1]
            version = record.version_id or month_slip.version_id
            record.total_days = (record.months * 30) + record.days \
                - record.lacks
            record.computable_remuneration = record.wage \
                + record.household_allowance + record.commission \
                + record.bonus + record.extra_hours
            amount_per_month = record.computable_remuneration \
                if version.l10n_pe_labor_regime == 'general' \
                else record.computable_remuneration / 2.0
            vacation = custom_round(amount_per_month, 2)
            advanced_vacation = vacation / 30.0 \
                * int(record.accrued_vacation)
            record.total_vacation = custom_round(advanced_vacation, 2)

            membership = version.membership_id
            onp = afp_jub = afp_si = 0.0
            afp_mixed_com = afp_fixed_com = 0.0
            retirement = month_slip.l10n_pe_retirement_fund \
                or membership.retirement_fund
            prima = month_slip.l10n_pe_prima_insurance \
                or membership.prima_insurance
            cap = month_slip.l10n_pe_insurable_remuneration \
                or membership.insurable_remuneration
            if membership.is_afp:
                afp_jub = custom_round(
                    retirement / 100.0 * record.total_vacation, 2)
                if cap and record.total_vacation >= cap:
                    afp_si = custom_round(prima / 100.0 * cap, 2)
                else:
                    afp_si = custom_round(
                        prima / 100.0 * record.total_vacation, 2)
                if version.l10n_pe_commission_type == 'mixed':
                    afp_mixed_com = custom_round(
                        membership.mixed_commision / 100.0
                        * record.total_vacation, 2)
                else:
                    afp_fixed_com = custom_round(
                        membership.fixed_commision / 100.0
                        * record.total_vacation, 2)
            else:
                onp = custom_round(
                    retirement / 100.0 * record.total_vacation, 2)
            afp_si = 0.0 if version.l10n_pe_is_older else afp_si
            record.afp_jub = afp_jub
            record.afp_si = afp_si
            record.afp_mixed_com = afp_mixed_com
            record.afp_fixed_com = afp_fixed_com
            record.onp = onp
            record.neto_total = custom_round(
                record.total_vacation - afp_jub - afp_si - afp_mixed_com
                - afp_fixed_com - onp, 2)
            record.total = record.neto_total - record.quinta
            if record.total <= 0 and not self.env.context.get('line_form'):
                record.unlink()

    def view_detail_vac(self):
        """Histórico de 6 meses por periodo (sueldo, asignación,
        comisiones, horas extras y bonificaciones). v18 lo armaba con SQL
        ``.format()``; aquí con ORM sobre las boletas BASE."""
        self.ensure_one()
        self.vacation_line_ids.unlink()
        param = self.env['hr.main.parameter'].get_main_parameter(
            self.company_id)
        structure = self.env.ref('al_hr_pe.base_structure')
        date_calculate = self.vacation_id.payslip_run_id.date_end
        date_from = date_calculate - relativedelta(months=6)
        date_from = date(date_from.year, date_from.month, 1)
        date_to = date_calculate - relativedelta(months=1)
        date_to = date(date_to.year, date_to.month,
                       monthrange(date_to.year, date_to.month)[1])

        basic_rule = getattr(param, 'basic_sr_id', False)
        af_rule = getattr(param, 'household_allowance_sr_id', False)
        commission_rules = getattr(
            param, 'commission_sr_ids', self.env['hr.salary.rule'])
        extra_hours_rule = getattr(param, 'extra_hours_sr_id', False)
        bonus_rules = getattr(
            param, 'bonus_sr_ids', self.env['hr.salary.rule'])

        slips = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('company_id', '=', self.company_id.id),
            ('struct_id', '=', structure.id),
            ('date_to', '>=', date_from),
            ('date_to', '<=', date_to),
        ])
        totals_by_period = {}
        for slip in slips:
            bucket = totals_by_period.setdefault(slip.periodo_id, {
                'wage': 0.0, 'household_allowance': 0.0,
                'commission': 0.0, 'extra_hours': 0.0,
                'others_income': 0.0})
            for line in slip.line_ids:
                if not line.total or not line.salary_rule_id.active:
                    continue
                rule = line.salary_rule_id
                if basic_rule and rule == basic_rule:
                    bucket['wage'] += line.total
                elif af_rule and rule == af_rule:
                    bucket['household_allowance'] += line.total
                elif rule in commission_rules:
                    bucket['commission'] += line.total
                elif extra_hours_rule and rule == extra_hours_rule:
                    bucket['extra_hours'] += line.total
                elif rule in bonus_rules:
                    bucket['others_income'] += line.total
        for periodo, values in totals_by_period.items():
            if not any(values.values()):
                continue
            self.env['hr.leave.vacation.line'].create(dict(
                values, leave_vacation_id=self.id,
                periodo_id=periodo.id or False))
        return {
            'name': self.env._('Detalle histórico de planillas'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.leave.vacation.line',
            'view_mode': 'list',
            'domain': [('leave_vacation_id', '=', self.id)],
            'target': 'new',
        }


class HrLeaveVacationLine(models.Model):
    _name = 'hr.leave.vacation.line'
    _description = 'Detalle de periodo de vacaciones'
    _order = 'periodo_id desc'

    leave_vacation_id = fields.Many2one(
        'hr.vacation.line', string='Línea de liquidación',
        ondelete='cascade', required=True, index=True)
    company_id = fields.Many2one(
        related='leave_vacation_id.company_id', store=True,
        string='Compañía', index=True)
    periodo_id = fields.Many2one('hr.period', string='Periodo')
    wage = fields.Float(string='Básico')
    household_allowance = fields.Float(string='Asignación familiar')
    commission = fields.Float(string='Comisiones')
    extra_hours = fields.Float(string='Horas extras')
    others_income = fields.Float(string='Bonificaciones')
    total = fields.Float(
        string='Base imponible', digits=(12, 2),
        compute='_compute_total', store=True)

    @api.depends('wage', 'household_allowance', 'commission',
                 'extra_hours', 'others_income')
    def _compute_total(self):
        for line in self:
            line.total = line.wage + line.household_allowance \
                + line.commission + line.extra_hours + line.others_income
