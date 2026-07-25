# -*- coding: utf-8 -*-
"""Capa peruana sobre el planning nativo de Enterprise.

Sustituye al clon v18 ``hr_assistance_planning`` (~2 700 líneas que
duplicaban el gantt, las plantillas y las líneas de turno de
``planning``): en v19 los turnos son ``planning.slot`` /
``planning.slot.template`` nativos y las work entries las genera
``hr_work_entry_planning`` cuando la versión del trabajador tiene
``work_entry_source = 'planning'``. Aquí solo vive lo peruano:

* Clasificación PE del rol de planificación (mañana/tarde/noche) y
  detección de jornada nocturna: D.S. 007-2002-TR (TUO Ley de Jornada)
  art. 8 — el horario nocturno corre de 22:00 a 06:00 y no puede
  remunerarse por debajo de la RMV con sobretasa del 35 %.
* Régimen atípico/acumulativo (típico en minería): catálogo de ciclos
  N×M días de trabajo × descanso (p. ej. 14×7) con validador legal
  (Constitución art. 25; D.S. 007-2002-TR art. 4; D.S. 008-2002-TR
  art. 9: promedio ≤ 48 h semanales en el ciclo; STC 4635-2004-AA/TC:
  tope de 12 h diarias en jornadas atípicas mineras) y un generador
  que materializa los días de trabajo como ``planning.slot`` nativos.
  Los días de descanso NO generan slot (un slot publicado se convierte
  en work entry); el monitor de asistencia los reconstruye desde la
  asignación de ciclo.
* Trazabilidad de reemplazos sobre ``planning.slot``: el flujo v18
  ``hr.make.replace.wizard`` (duplicar la línea con otro empleado) lo
  cubre el planning nativo con turnos abiertos, reasignación en el
  gantt y solicitudes de cambio de turno; solo se conserva el rastro
  de a quién se reemplaza y por qué motivo.
"""
import math
from datetime import datetime, timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.date_utils import float_to_time


class PlanningRole(models.Model):
    """El rol nativo hace de «tipo de turno» v18 (``attendance.activity``)."""
    _inherit = 'planning.role'

    l10n_pe_shift_kind = fields.Selection(
        selection=[
            ('manana', 'Turno mañana'),
            ('tarde', 'Turno tarde'),
            ('noche', 'Turno noche'),
            ('rotativo', 'Rotativo'),
        ],
        string='Tipo de turno (Perú)',
        help='Clasificación peruana del rol de planificación; el turno '
             'noche identifica la jornada con sobretasa nocturna '
             '(D.S. 007-2002-TR art. 8).')


class PlanningSlotTemplate(models.Model):
    """Plantilla nativa + bandera de jornada nocturna peruana."""
    _inherit = 'planning.slot.template'

    l10n_pe_is_night = fields.Boolean(
        string='Jornada nocturna (Perú)',
        compute='_compute_l10n_pe_is_night', store=True,
        help='La plantilla pisa el horario nocturno de 22:00 a 06:00 '
             '(D.S. 007-2002-TR art. 8: sobretasa mínima del 35 % '
             'sobre la RMV).')

    @api.depends('start_time', 'end_time', 'duration_days')
    def _compute_l10n_pe_is_night(self):
        """Marca la plantilla si su intervalo toca la banda [22:00, 06:00).

        Casos: el turno cruza medianoche (fin < inicio o dura más de un
        día) → pasa por la banda; si no cruza, toca la banda cuando
        empieza antes de las 06:00 o termina después de las 22:00.
        """
        for template in self:
            wraps = (template.end_time <= template.start_time
                     or template.duration_days > 1)
            template.l10n_pe_is_night = bool(
                wraps
                or template.start_time < 6.0
                or template.end_time > 22.0)


class L10nPeHrShiftCycle(models.Model):
    """Ciclo de jornada atípica o acumulativa (régimen minero).

    D.S. 007-2002-TR (TUO de la Ley de Jornada de Trabajo) art. 4
    permite jornadas atípicas/acumulativas siempre que el promedio de
    horas trabajadas en el ciclo no supere los máximos del art. 1
    (8 h diarias / 48 h semanales); D.S. 008-2002-TR art. 9 fija cómo
    promediar dentro del ciclo. La STC 4635-2004-AA/TC (caso Southern,
    trabajo minero) añade el «test de protección»: máximo 12 horas
    diarias. El ciclo clásico minero es 14×7 (14 días de trabajo por
    7 de descanso) u otros como 4×3, 20×10.

    Catálogo «global con override» (patrón de ``al_hr_pe``): sin
    compañía el ciclo es compartido; con compañía es propio.
    """
    _name = 'l10n_pe.hr.shift.cycle'
    _description = 'Ciclo de jornada atípica (Perú)'
    _order = 'days_work desc, days_rest'

    name = fields.Char(string='Nombre', required=True,
                       help='Ej. «Atípico 14×7 — 12 horas».')
    days_work = fields.Integer(string='Días de trabajo', required=True)
    days_rest = fields.Integer(string='Días de descanso', required=True)
    hours_per_day = fields.Float(
        string='Horas por día', required=True, default=8.0,
        help='Jornada diaria efectiva del ciclo (sin refrigerio).')
    cycle_days = fields.Integer(
        string='Duración del ciclo (días)',
        compute='_compute_cycle_stats', store=True)
    avg_weekly_hours = fields.Float(
        string='Promedio semanal (h)',
        compute='_compute_cycle_stats', store=True,
        help='horas/día × días de trabajo × 7 ÷ días del ciclo; no '
             'puede exceder 48 h (D.S. 007-2002-TR art. 4).')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', index=True,
        help='Vacío: ciclo global compartido entre compañías. Con '
             'compañía: ciclo propio de esa compañía.')

    _days_positive = models.Constraint(
        'CHECK(days_work > 0 AND days_rest > 0)',
        'Los días de trabajo y de descanso del ciclo deben ser '
        'positivos.')
    _hours_positive = models.Constraint(
        'CHECK(hours_per_day > 0)',
        'Las horas por día del ciclo deben ser positivas.')

    @api.depends('days_work', 'days_rest', 'hours_per_day')
    def _compute_cycle_stats(self):
        for cycle in self:
            cycle.cycle_days = cycle.days_work + cycle.days_rest
            if cycle.cycle_days:
                cycle.avg_weekly_hours = (
                    cycle.hours_per_day * cycle.days_work * 7.0
                    / cycle.cycle_days)
            else:
                cycle.avg_weekly_hours = 0.0

    @api.constrains('days_work', 'days_rest', 'hours_per_day')
    def _check_legal_limits(self):
        """Valida los topes legales de la jornada atípica.

        * 12 h diarias máximo (STC 4635-2004-AA/TC, fund. 15: en el
          régimen minero atípico la jornada diaria no puede superar
          las 12 horas).
        * Promedio semanal en el ciclo ≤ 48 h (Constitución art. 25;
          D.S. 007-2002-TR art. 4; D.S. 008-2002-TR art. 9).
        """
        for cycle in self:
            if cycle.hours_per_day > 12.0:
                raise ValidationError(self.env._(
                    'La jornada diaria del ciclo atípico no puede '
                    'superar las 12 horas (STC 4635-2004-AA/TC).'))
            total_days = cycle.days_work + cycle.days_rest
            if total_days and (cycle.hours_per_day * cycle.days_work
                               * 7.0 / total_days) > 48.0:
                raise ValidationError(self.env._(
                    'El promedio semanal del ciclo (%(hours).2f h) '
                    'supera las 48 horas permitidas por el art. 4 del '
                    'D.S. 007-2002-TR.',
                    hours=cycle.hours_per_day * cycle.days_work * 7.0
                    / total_days))

    @api.depends('name', 'days_work', 'days_rest')
    def _compute_display_name(self):
        for cycle in self:
            cycle.display_name = '%s (%d×%d)' % (
                cycle.name, cycle.days_work, cycle.days_rest)


class L10nPeHrShiftCycleAssignment(models.Model):
    """Asignación de un ciclo atípico a un trabajador.

    Reemplaza al generador v18 (``hr.assistance.planning`` tipo
    «atipico» + ``make_detail``): en lugar de crear líneas propias,
    materializa los días de trabajo del ciclo como ``planning.slot``
    nativos en borrador (el jefe los publica desde el gantt del
    planning y ``hr_work_entry_planning`` los convierte en work
    entries). Los días de descanso no generan slot; el monitor de
    asistencia los deriva de esta asignación.

    El registro además documenta el ciclo pactado, exigencia del
    registro de control de asistencia (D.S. 004-2006-TR) y de la
    fiscalización de jornadas atípicas (SUNAFIL).
    """
    _name = 'l10n_pe.hr.shift.cycle.assignment'
    _description = 'Asignación de ciclo atípico (Perú)'
    _order = 'date_start desc, employee_id'
    _check_company_auto = True

    employee_id = fields.Many2one(
        'hr.employee', string='Trabajador', required=True, index=True,
        check_company=True)
    cycle_id = fields.Many2one(
        'l10n_pe.hr.shift.cycle', string='Ciclo atípico', required=True,
        check_company=True)
    template_id = fields.Many2one(
        'planning.slot.template', string='Plantilla de turno',
        required=True,
        help='Plantilla nativa que define el horario de los días de '
             'trabajo (hora de inicio, hora de fin y rol/turno).')
    date_start = fields.Date(string='Inicio del ciclo', required=True)
    cycles_count = fields.Integer(
        string='N° de ciclos', required=True, default=1,
        help='Cuántas repeticiones consecutivas del ciclo se '
             'planifican (14×7 × 2 ciclos = 42 días).')
    date_end = fields.Date(
        string='Fin', compute='_compute_date_end', store=True,
        help='Inicio + N ciclos × (días trabajo + días descanso) − 1.')
    slot_ids = fields.One2many(
        'planning.slot', 'l10n_pe_cycle_assignment_id',
        string='Turnos generados')
    slot_count = fields.Integer(
        string='Turnos', compute='_compute_slot_count')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)

    _cycles_count_positive = models.Constraint(
        'CHECK(cycles_count > 0)',
        'El número de ciclos debe ser positivo.')

    @api.depends('date_start', 'cycles_count', 'cycle_id.days_work',
                 'cycle_id.days_rest')
    def _compute_date_end(self):
        for assignment in self:
            if assignment.date_start and assignment.cycle_id:
                total = assignment.cycles_count * (
                    assignment.cycle_id.days_work
                    + assignment.cycle_id.days_rest)
                assignment.date_end = assignment.date_start + timedelta(
                    days=total - 1)
            else:
                assignment.date_end = False

    @api.depends('slot_ids')
    def _compute_slot_count(self):
        for assignment in self:
            assignment.slot_count = len(assignment.slot_ids)

    @api.depends('employee_id', 'cycle_id', 'date_start')
    def _compute_display_name(self):
        for assignment in self:
            parts = [assignment.cycle_id.display_name or '?',
                     assignment.employee_id.name or '?']
            if assignment.date_start:
                parts.append(fields.Date.to_string(assignment.date_start))
            assignment.display_name = ' — '.join(parts)

    @api.constrains('template_id', 'cycle_id')
    def _check_template_hours(self):
        """La plantilla no puede exceder la jornada declarada del ciclo.

        El validador legal vive en el ciclo (promedio ≤ 48 h, tope de
        12 h/día); si la plantilla durara más que las horas/día del
        ciclo, ese promedio quedaría subestimado y la planificación
        sería ilegal de facto.
        """
        for assignment in self:
            duration = assignment._template_duration_hours()
            if duration - assignment.cycle_id.hours_per_day > 0.01:
                raise ValidationError(self.env._(
                    'La plantilla «%(template)s» dura %(duration).2f h, '
                    'más que las %(hours).2f h/día declaradas en el '
                    'ciclo «%(cycle)s».',
                    template=assignment.template_id.display_name,
                    duration=duration,
                    hours=assignment.cycle_id.hours_per_day,
                    cycle=assignment.cycle_id.display_name))

    @api.constrains('employee_id', 'date_start', 'date_end')
    def _check_overlap(self):
        for assignment in self:
            overlap = self.search_count([
                ('id', '!=', assignment.id),
                ('employee_id', '=', assignment.employee_id.id),
                ('date_start', '<=', assignment.date_end),
                ('date_end', '>=', assignment.date_start),
            ], limit=1)
            if overlap:
                raise ValidationError(self.env._(
                    'El trabajador %(employee)s ya tiene otra '
                    'asignación de ciclo que se superpone con el '
                    'periodo %(start)s – %(end)s.',
                    employee=assignment.employee_id.name,
                    start=assignment.date_start,
                    end=assignment.date_end))

    def _template_duration_hours(self):
        """Duración en horas de la plantilla, tolerando el cruce de medianoche."""
        self.ensure_one()
        template = self.template_id
        duration = (template.end_time - template.start_time) % 24.0
        return duration or 24.0

    def _iter_work_dates(self):
        """Genera las fechas de trabajo del ciclo (omite los descansos)."""
        self.ensure_one()
        cycle_len = self.cycle_id.days_work + self.cycle_id.days_rest
        total_days = self.cycles_count * cycle_len
        for offset in range(total_days):
            if offset % cycle_len < self.cycle_id.days_work:
                yield self.date_start + timedelta(days=offset)

    def action_generate_slots(self):
        """Materializa los días de trabajo como ``planning.slot`` borrador.

        Conversión TZ-aware (corrige el ``+ timedelta(hours=5)``
        hardcodeado del generador v18): la hora de la plantilla se
        interpreta en la zona horaria del trabajador
        (``employee._get_tz()``) y se almacena en UTC naive, como
        exige el ORM.
        """
        for assignment in self:
            if not assignment.employee_id.resource_id:
                raise UserError(self.env._(
                    'El trabajador %s no tiene recurso de planificación '
                    '(¿está archivado?).', assignment.employee_id.name))
            if assignment.slot_ids:
                raise UserError(self.env._(
                    'La asignación ya tiene turnos generados; elimine '
                    'los borradores antes de regenerar.'))
            tz = pytz.timezone(assignment.employee_id._get_tz()
                               or 'UTC')
            template = assignment.template_id
            duration = assignment._template_duration_hours()
            start_time = float_to_time(template.start_time)
            vals_list = []
            conflicts = []
            for work_date in assignment._iter_work_dates():
                start_local = tz.localize(
                    datetime.combine(work_date, start_time))
                start_utc = start_local.astimezone(pytz.utc).replace(
                    tzinfo=None)
                end_utc = start_utc + timedelta(
                    hours=int(duration),
                    minutes=round(math.modf(duration)[0] * 60))
                existing = self.env['planning.slot'].search_count([
                    ('employee_id', '=', assignment.employee_id.id),
                    ('start_datetime', '<', end_utc),
                    ('end_datetime', '>', start_utc),
                ], limit=1)
                if existing:
                    conflicts.append(fields.Date.to_string(work_date))
                    continue
                vals_list.append({
                    'resource_id': assignment.employee_id.resource_id.id,
                    'company_id': assignment.company_id.id,
                    'start_datetime': start_utc,
                    'end_datetime': end_utc,
                    'role_id': template.role_id.id,
                    'l10n_pe_cycle_assignment_id': assignment.id,
                })
            if conflicts:
                raise UserError(self.env._(
                    'El trabajador %(employee)s ya tiene turnos que se '
                    'superponen en: %(dates)s. Resuélvalos en el '
                    'planning antes de generar el ciclo.',
                    employee=assignment.employee_id.name,
                    dates=', '.join(conflicts)))
            self.env['planning.slot'].create(vals_list)
        return self.action_view_slots()

    def unlink(self):
        """Al borrar la asignación se limpian sus turnos borrador.

        Si algún turno ya está publicado se bloquea: un slot publicado
        genera work entries (``hr_work_entry_planning``) y borrarlo por
        arrastre rompería la nómina; primero hay que despublicarlo en
        el planning.
        """
        published = self.slot_ids.filtered(
            lambda slot: slot.state == 'published')
        if published:
            raise UserError(self.env._(
                'La asignación tiene %d turno(s) publicados; '
                'despublíquelos en el planning antes de eliminarla.',
                len(published)))
        self.slot_ids.unlink()
        return super().unlink()

    def action_view_slots(self):
        """Abre los turnos del ciclo en las vistas nativas del planning."""
        self.ensure_one()
        return {
            'name': self.env._('Turnos del ciclo'),
            'type': 'ir.actions.act_window',
            'res_model': 'planning.slot',
            'views': [(False, 'list'), (False, 'gantt'), (False, 'form')],
            'domain': [('l10n_pe_cycle_assignment_id', '=', self.id)],
            'context': {
                'default_l10n_pe_cycle_assignment_id': self.id,
                'default_resource_id': self.employee_id.resource_id.id,
            },
        }


class PlanningSlot(models.Model):
    """Rastro peruano sobre el slot nativo (ciclo y reemplazos)."""
    _inherit = 'planning.slot'
    _check_company_auto = True

    l10n_pe_cycle_assignment_id = fields.Many2one(
        'l10n_pe.hr.shift.cycle.assignment',
        string='Asignación de ciclo atípico', index='btree_not_null',
        ondelete='set null', check_company=True,
        help='Asignación de ciclo atípico que generó este turno.')
    # Gap conservado del wizard v18 hr.make.replace.wizard: la
    # reasignación en sí la hace el planning nativo (turno abierto,
    # arrastre en el gantt o solicitud de cambio); aquí solo queda el
    # rastro de la cobertura para reportes/fiscalización.
    l10n_pe_replaced_employee_id = fields.Many2one(
        'hr.employee', string='Reemplaza a', check_company=True,
        help='Trabajador titular al que este turno cubre.')
    l10n_pe_replacement_reason = fields.Selection(
        selection=[
            ('vacaciones', 'Vacaciones'),
            ('descanso', 'Día de descanso'),
            ('falta', 'Falta'),
            ('otro', 'Otro'),
        ],
        string='Motivo del reemplazo')
