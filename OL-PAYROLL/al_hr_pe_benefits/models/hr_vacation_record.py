# -*- coding: utf-8 -*-
"""Récord vacacional por año de servicios (D.Leg. 713, art. 10 y 12).

El trabajador gana 30 días de vacaciones (15 en la pequeña y la
microempresa) por cada año completo de servicios SOLO si en ese año
cumple el récord:

a) jornada de 6 días a la semana: al menos 260 días efectivos;
b) jornada de 5 días: al menos 210 días efectivos;
c) jornada de menos de 5 días: no más de 10 inasistencias
   injustificadas (D.S. 012-92-TR, art. 11).

El año de récord se cuenta desde la fecha de ingreso del vínculo
(aniversario), no por año calendario. Cada ``hr.vacation.record`` es un
año de récord de un trabajador: días efectivos y faltas sumados desde
las líneas de días trabajados de sus boletas CERRADAS (validadas o
pagadas), umbral aplicado y resultado. El recálculo de saldos
(``hr.vacation.rest``) no genera los días del año que no cumple.

Días efectivos (art. 12) por código de tipo de entrada:

* DLAB (laborados), FER (feriado o descanso laborado: jornada cumplida
  en día de descanso), DVAC (vacaciones del año anterior), DPAT
  (licencia de paternidad, por ley), LCGH (licencia con goce: falta
  autorizada por ley, convenio o el empleador) y SMAR (descanso pre y
  postnatal).
* DMED (descanso médico) y SENF (subsidio por enfermedad): enfermedad
  común, accidente o enfermedad profesional, hasta 60 días por año de
  récord entre los dos; el exceso no cuenta.

No son efectivos: DOM (descanso semanal), LSGH (licencia sin goce),
FAL (falta: además es inasistencia injustificada), TAR, HTN y las horas
extra (no se puede saber de la boleta si sumaron 4 horas en un día que
no fue laborado; si fuera el caso, se corrige con el ajuste manual).
Los feriados no laborados tampoco: la norma no los lista.

Las vacaciones truncas del cese no exigen récord y no se tocan aquí.
"""
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.addons.al_hr_pe.models.display_name import pe_join, pe_range
from odoo.exceptions import ValidationError

from odoo.addons.al_hr_pe.tools import custom_round

# Códigos de días efectivos (D.Leg. 713, art. 12).
RECORD_EFFECTIVE_CODES = ('DLAB', 'FER', 'DVAC', 'DPAT', 'LCGH', 'SMAR')
# Enfermedad y accidente: efectivos hasta 60 días por año de récord.
RECORD_SICK_CODES = ('DMED', 'SENF')
RECORD_SICK_CAP = 60.0
# Inasistencia injustificada.
RECORD_ABSENCE_CODES = ('FAL',)
# Días del periodo que no son efectivos (solo para elegir la boleta
# más completa cuando dos cubren las mismas fechas).
RECORD_OTHER_CODES = ('DOM', 'LSGH')
# Regímenes con vacaciones del D.Leg. 713 (el practicante no tiene).
RECORD_REGIMES = ('general', 'small', 'micro', 'construccion')
RECORD_MAX_ABSENCES = 10


class HrVacationRecord(models.Model):
    _name = 'hr.vacation.record'
    _description = 'Récord vacacional anual'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'employee_id, date_from desc'
    _check_company_auto = True

    employee_id = fields.Many2one(
        'hr.employee', string='Trabajador', required=True, index=True,
        check_company=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        readonly=True, default=lambda self: self.env.company)
    version_id = fields.Many2one(
        'hr.version', string='Versión', readonly=True,
        help='Versión vigente al cierre del año de récord: de su calendario '
             'sale la jornada semanal.')
    date_from = fields.Date(
        string='Inicio del año de récord', required=True, readonly=True,
        help='Aniversario de la fecha de ingreso.')
    date_to = fields.Date(
        string='Fin del año de récord', required=True, readonly=True)
    weekly_days = fields.Float(
        string='Días de jornada a la semana', digits=(16, 2), readonly=True)
    workweek = fields.Selection(
        [('six', 'Seis días'), ('five', 'Cinco días'),
         ('less', 'Menos de cinco días')],
        string='Jornada semanal', readonly=True)
    threshold = fields.Integer(
        string='Umbral aplicado', readonly=True,
        help='260 días efectivos (jornada de 6 días), 210 (jornada de 5) '
             'o un máximo de 10 faltas injustificadas (menos de 5 días).')
    effective_days = fields.Float(
        string='Días efectivos', digits=(16, 2), readonly=True,
        help='Laborados + feriados o descansos laborados + vacaciones + '
             'licencias con goce, paternidad y maternidad + descanso '
             'médico hasta 60 días.')
    worked_days = fields.Float(
        string='Laborados', digits=(16, 2), readonly=True,
        help='DLAB + FER.')
    paid_leave_days = fields.Float(
        string='Vacaciones y licencias', digits=(16, 2), readonly=True,
        help='DVAC + DPAT + LCGH + SMAR.')
    sick_days = fields.Float(
        string='Descanso médico', digits=(16, 2), readonly=True,
        help='DMED + SENF del año (todos, también el exceso).')
    sick_days_counted = fields.Float(
        string='Descanso médico computable', digits=(16, 2), readonly=True,
        help='Hasta 60 días por año de récord.')
    absence_days = fields.Float(
        string='Faltas injustificadas', digits=(16, 2), readonly=True)
    covered_days = fields.Integer(
        string='Días con boleta', readonly=True,
        help='Días del año de récord cubiertos por boletas cerradas.')
    period_days = fields.Integer(string='Días del año', readonly=True)
    slip_count = fields.Integer(string='Boletas', readonly=True)
    computed_state = fields.Selection(
        [('meets', 'Cumple'), ('fails', 'No cumple'),
         ('no_data', 'Sin datos'), ('not_applicable', 'No aplica')],
        string='Resultado del cálculo', readonly=True, tracking=True)
    evaluation_note = fields.Text(string='Detalle del cálculo', readonly=True)
    evaluation_date = fields.Datetime(string='Evaluado el', readonly=True)
    # Ajuste manual: los días de las boletas pueden venir incompletos
    # (datos migrados) o el empleador puede reconocer el récord.
    manual_state = fields.Selection(
        [('meets', 'Cumple'), ('fails', 'No cumple')],
        string='Ajuste manual', tracking=True,
        help='Prevalece sobre el cálculo (p. ej. «cumple» por decisión del '
             'empleador). Exige una nota.')
    manual_note = fields.Text(string='Motivo del ajuste', tracking=True)
    manual_user_id = fields.Many2one(
        'res.users', string='Ajustado por', readonly=True)
    manual_date = fields.Datetime(string='Ajustado el', readonly=True)
    state = fields.Selection(
        [('meets', 'Cumple'), ('fails', 'No cumple'),
         ('no_data', 'Sin datos'), ('not_applicable', 'No aplica')],
        string='Récord', compute='_compute_state', store=True, index=True,
        tracking=True)

    _employee_year_unique = models.Constraint(
        'UNIQUE(employee_id, company_id, date_from)',
        'Ya existe el récord vacacional de ese año para el trabajador.')

    @api.depends('computed_state', 'manual_state')
    def _compute_state(self):
        for record in self:
            record.state = record.manual_state or record.computed_state \
                or 'no_data'

    @api.depends('employee_id', 'date_from', 'date_to')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = pe_join(
                rec.employee_id.name,
                pe_range(rec.env, rec.date_from, rec.date_to))

    @api.constrains('manual_state', 'manual_note')
    def _check_manual_note(self):
        for record in self:
            if record.manual_state and not (record.manual_note or '').strip():
                raise ValidationError(self.env._(
                    'Indique el motivo del ajuste manual del récord '
                    'vacacional de %(record)s.',
                    record=record.display_name))

    def write(self, vals):
        if 'manual_state' in vals:
            vals = dict(vals)
            if vals['manual_state']:
                vals.update({'manual_user_id': self.env.uid,
                             'manual_date': fields.Datetime.now()})
            else:
                vals.update({'manual_user_id': False, 'manual_date': False,
                             'manual_note': vals.get('manual_note', False)})
        return super().write(vals)

    # ------------------------------------------------------------------
    # Botones
    # ------------------------------------------------------------------
    def action_evaluate(self):
        """Recalcula el récord desde las boletas cerradas (el ajuste
        manual, si lo hay, se conserva y sigue prevaleciendo)."""
        for record in self:
            record._evaluate()
        return True

    def action_clear_manual(self):
        self.write({'manual_state': False, 'manual_note': False})
        return True

    # ------------------------------------------------------------------
    # Jornada semanal
    # ------------------------------------------------------------------
    @api.model
    def _l10n_pe_weekly_days(self, version):
        """Días de trabajo a la semana del calendario de la versión (o de
        la compañía). En un calendario fijo, los días distintos con
        jornada (sin contar las franjas DOM ni las que no son tiempo de
        trabajo); en uno variable o flexible, los «días por semana» que
        fija el usuario. 0 si no se puede saber."""
        calendar = version.resource_calendar_id \
            or version.company_id.resource_calendar_id
        if not calendar:
            return 0.0
        if calendar.calendar_type == 'fixed':
            attendances = calendar.attendance_ids.filtered(
                lambda att: att.work_entry_type_id.code != 'DOM'
                and att._is_work_period())
            return float(len(set(attendances.mapped('dayofweek'))))
        return calendar.days_per_week or 0.0

    @api.model
    def _l10n_pe_workweek(self, weekly_days):
        """(jornada, umbral) del art. 10 del D.Leg. 713."""
        if weekly_days >= 6:
            return 'six', 260
        if weekly_days >= 5:
            return 'five', 210
        return 'less', RECORD_MAX_ABSENCES

    # ------------------------------------------------------------------
    # Cálculo
    # ------------------------------------------------------------------
    @api.model
    def _l10n_pe_year_bounds(self, admission_date, on_date):
        """Años de récord COMPLETOS desde el ingreso hasta ``on_date``:
        lista de (inicio, fin)."""
        years = []
        start = admission_date
        while True:
            end = start + relativedelta(years=1) - timedelta(days=1)
            if end > on_date:
                return years
            years.append((start, end))
            start = end + timedelta(days=1)

    @api.model
    def _l10n_pe_get_record(self, employee, date_from, date_to,
                            evaluate=True):
        """Récord del año [date_from, date_to] del trabajador en la
        compañía activa, creado si no existe. Con ``evaluate`` se
        recalcula (el ajuste manual se respeta)."""
        company = self.env.company
        record = self.search([
            ('employee_id', '=', employee.id),
            ('company_id', '=', company.id),
            ('date_from', '=', date_from),
        ], limit=1)
        if not record:
            record = self.create({
                'employee_id': employee.id,
                'company_id': company.id,
                'date_from': date_from,
                'date_to': date_to,
            })
            evaluate = True
        elif record.date_to != date_to:
            record.date_to = date_to
            evaluate = True
        if evaluate:
            record._evaluate()
        return record

    def _l10n_pe_closed_slips(self):
        """Boletas cerradas del trabajador que tocan el año de récord,
        sin duplicar fechas: si dos boletas cubren los mismos días (dos
        lotes del mes, quincena y mensual) vale la más larga y, a igual
        periodo, la que tiene más días registrados."""
        self.ensure_one()
        codes = RECORD_EFFECTIVE_CODES + RECORD_SICK_CODES \
            + RECORD_ABSENCE_CODES + RECORD_OTHER_CODES
        slips = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('company_id', '=', self.company_id.id),
            ('state', 'in', ('validated', 'paid')),
            ('date_from', '<=', self.date_to),
            ('date_to', '>=', self.date_from),
        ])

        def registered_days(slip):
            return sum(slip.worked_days_line_ids.filtered(
                lambda line: line.work_entry_type_id.code in codes
            ).mapped('number_of_days'))

        candidates = [
            (slip, registered_days(slip)) for slip in slips
            if slip.date_from and slip.date_to]
        candidates = [(slip, days) for slip, days in candidates if days]
        candidates.sort(key=lambda item: (
            -(item[0].date_to - item[0].date_from).days, -item[1],
            item[0].id))
        taken_days = set()
        accepted = self.env['hr.payslip']
        for slip, _days in candidates:
            slip_days = {slip.date_from.toordinal() + offset for offset in
                         range((slip.date_to - slip.date_from).days + 1)}
            if slip_days & taken_days:
                continue
            taken_days |= slip_days
            accepted |= slip
        return accepted

    def _evaluate(self):
        """Suma los días del año de récord y decide si cumple.

        Una boleta que cruza el aniversario (mensual con ingreso a mitad
        de mes) aporta la parte proporcional a los días que caen dentro
        del año: las líneas de días no llevan fecha.
        """
        self.ensure_one()
        employee = self.employee_id
        version = employee._get_version(self.date_to) or employee.version_id
        period_days = (self.date_to - self.date_from).days + 1
        weekly_days = self._l10n_pe_weekly_days(version) if version else 0.0
        workweek, threshold = self._l10n_pe_workweek(weekly_days)

        totals = dict.fromkeys(
            RECORD_EFFECTIVE_CODES + RECORD_SICK_CODES
            + RECORD_ABSENCE_CODES, 0.0)
        covered = set()
        slips = self._l10n_pe_closed_slips()
        year_start = self.date_from.toordinal()
        year_end = self.date_to.toordinal()
        for slip in slips:
            slip_start = slip.date_from.toordinal()
            slip_end = slip.date_to.toordinal()
            overlap_start = max(slip_start, year_start)
            overlap_end = min(slip_end, year_end)
            if overlap_end < overlap_start:
                continue
            covered.update(range(overlap_start, overlap_end + 1))
            ratio = (overlap_end - overlap_start + 1) \
                / (slip_end - slip_start + 1)
            for line in slip.worked_days_line_ids:
                code = line.work_entry_type_id.code
                if code in totals:
                    totals[code] += line.number_of_days * ratio

        worked = totals['DLAB'] + totals['FER']
        paid_leave = sum(totals[code] for code in RECORD_EFFECTIVE_CODES
                         if code not in ('DLAB', 'FER'))
        sick = sum(totals[code] for code in RECORD_SICK_CODES)
        sick_counted = min(sick, RECORD_SICK_CAP)
        absences = sum(totals[code] for code in RECORD_ABSENCE_CODES)
        effective = custom_round(worked + paid_leave + sick_counted, 2)
        absences = custom_round(absences, 2)
        covered_days = len(covered)
        uncovered = period_days - covered_days

        _ = self.env._
        regime = version.l10n_pe_labor_regime if version else False
        if version and version.l10n_pe_less_than_four:
            state = 'not_applicable'
            note = _('Jornada menor a 4 horas diarias: no tiene vacaciones '
                     '(D.Leg. 713, art. 12).')
        elif regime and regime not in RECORD_REGIMES:
            state = 'not_applicable'
            note = _('El régimen laboral no tiene vacaciones del D.Leg. 713.')
        elif not weekly_days:
            state = 'no_data'
            note = _('No se pudo determinar la jornada semanal: revise el '
                     'calendario de la versión.')
        elif not slips:
            state = 'no_data'
            note = _('No hay boletas cerradas en el año de récord (p. ej. '
                     'datos migrados): no se puede evaluar. Los días del '
                     'año se generan; verifíquelo y, si corresponde, '
                     'ajústelo a mano.')
        elif workweek == 'less':
            if absences > RECORD_MAX_ABSENCES:
                state = 'fails'
                note = _('%(absences)s faltas injustificadas: supera el '
                         'máximo de %(max)s de la jornada de menos de cinco '
                         'días.', absences=absences, max=RECORD_MAX_ABSENCES)
            elif uncovered > 0:
                state = 'no_data'
                note = _('%(absences)s faltas, pero las boletas cerradas solo '
                         'cubren %(covered)s de %(days)s días del año.',
                         absences=absences, covered=covered_days,
                         days=period_days)
            else:
                state = 'meets'
                note = _('%(absences)s faltas injustificadas (máximo '
                         '%(max)s).', absences=absences,
                         max=RECORD_MAX_ABSENCES)
        elif effective >= threshold:
            state = 'meets'
            note = _('%(effective)s días efectivos (mínimo %(threshold)s).',
                     effective=effective, threshold=threshold)
        elif uncovered <= 0 or effective + uncovered < threshold:
            # Ni con todos los días sin boleta llegaría al umbral.
            state = 'fails'
            note = _('%(effective)s días efectivos: no alcanza el mínimo de '
                     '%(threshold)s.', effective=effective,
                     threshold=threshold)
        else:
            state = 'no_data'
            note = _('%(effective)s días efectivos (mínimo %(threshold)s), '
                     'pero las boletas cerradas solo cubren %(covered)s de '
                     '%(days)s días del año.', effective=effective,
                     threshold=threshold, covered=covered_days,
                     days=period_days)
        if sick > RECORD_SICK_CAP:
            note += ' ' + _('Descanso médico: %(sick)s días, computan '
                            '%(cap)s.', sick=custom_round(sick, 2),
                            cap=int(RECORD_SICK_CAP))
        self.write({
            'version_id': version.id if version else False,
            'weekly_days': weekly_days,
            'workweek': workweek if weekly_days else False,
            'threshold': threshold if weekly_days else 0,
            'effective_days': effective,
            'worked_days': custom_round(worked, 2),
            'paid_leave_days': custom_round(paid_leave, 2),
            'sick_days': custom_round(sick, 2),
            'sick_days_counted': custom_round(sick_counted, 2),
            'absence_days': absences,
            'covered_days': covered_days,
            'period_days': period_days,
            'slip_count': len(slips),
            'computed_state': state,
            'evaluation_note': note,
            'evaluation_date': fields.Datetime.now(),
        })

    # ------------------------------------------------------------------
    # Evaluación por trabajador y cron
    # ------------------------------------------------------------------
    @api.model
    def _l10n_pe_evaluate_employees(self, employees, on_date=None,
                                    last_only=False):
        """Evalúa los años de récord completos de los trabajadores en la
        compañía activa. Con ``last_only``, solo el último año cumplido
        (los anteriores que ya existan no se tocan)."""
        on_date = on_date or fields.Date.context_today(self)
        param = self.env['hr.main.parameter'].get_main_parameter(
            self.env.company)
        records = self.browse()
        for employee in employees:
            versions = employee.version_ids.filtered('contract_date_start')
            if not versions:
                continue
            admission = param.get_first_version(
                employee, on_date).contract_date_start
            # Hasta hoy o hasta el cese del contrato vigente.
            current = versions.filtered(
                lambda version: version.contract_date_start
                == max(versions.mapped('contract_date_start')))
            ends = current.mapped('contract_date_end')
            end = min(on_date, max(ends)) if all(ends) else on_date
            years = self._l10n_pe_year_bounds(admission, end)
            if last_only:
                years = years[-1:]
            for date_from, date_to in years:
                records |= self._l10n_pe_get_record(
                    employee, date_from, date_to)
        return records

    @api.model
    def _cron_evaluate_vacation_records(self):
        """Evalúa el año de récord recién cumplido de los trabajadores
        de las compañías peruanas (y reevalúa los que quedaron «sin
        datos», por si ya se cerraron sus boletas)."""
        companies = self.env['res.company'].search([]).filtered(
            lambda company: company.country_id.code == 'PE')
        for company in companies:
            Record = self.with_company(company).with_context(
                allowed_company_ids=company.ids)
            employees = self.env['hr.employee'].with_company(company).search([
                ('company_id', '=', company.id),
            ])
            Record._l10n_pe_evaluate_employees(employees, last_only=True)
            Record.search([
                ('company_id', '=', company.id),
                ('computed_state', '=', 'no_data'),
                ('manual_state', '=', False),
            ]).action_evaluate()


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    l10n_pe_vacation_record_ids = fields.One2many(
        'hr.vacation.record', 'employee_id', string='Récord vacacional',
        groups='hr_payroll.group_hr_payroll_user')
    l10n_pe_vacation_record_count = fields.Integer(
        compute='_compute_l10n_pe_vacation_record_count',
        groups='hr_payroll.group_hr_payroll_user')

    def _compute_l10n_pe_vacation_record_count(self):
        counts = dict(self.env['hr.vacation.record']._read_group(
            [('employee_id', 'in', self.ids)], ['employee_id'],
            ['__count']))
        for employee in self:
            employee.l10n_pe_vacation_record_count = counts.get(employee, 0)

    def action_l10n_pe_vacation_records(self):
        """Evalúa los años de récord cumplidos y los muestra."""
        self.ensure_one()
        self.env['hr.vacation.record'].with_company(
            self.company_id)._l10n_pe_evaluate_employees(self)
        return {
            'name': self.env._('Récord vacacional'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.vacation.record',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'create': False},
        }
