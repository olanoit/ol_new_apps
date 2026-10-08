# -*- coding: utf-8 -*-
"""Tareaje peruano: clasificación de horas de asistencia para la boleta.

Clasifica las marcaciones (`hr.attendance`) del periodo en los conceptos
peruanos de la boleta:

* **Horas extras** — D.S. 007-2002-TR (TUO de la Ley de jornada de
  trabajo, horario y trabajo en sobretiempo), art. 10: sobretasa mínima
  del 25 % por las dos primeras horas de sobretiempo del día y 35 % por
  las restantes (``HE25`` / ``HE35``).
* **Jornada nocturna** — D.S. 007-2002-TR, art. 8: trabajo entre las
  22:00 y las 06:00 (ventana parametrizable); el trabajador nocturno no
  puede percibir menos de la RMV + sobretasa del 35 %. El tareaje separa
  las horas/días nocturnos (``htn`` / ``dlabn``) para que la regla
  salarial de sobretasa nocturna los pague.
* **Descanso semanal y feriados** — D.Leg. 713, arts. 3-4 (descanso
  semanal obligatorio) y arts. 5-9 (feriados): el trabajo en día de
  descanso o feriado sin descanso sustitutorio se paga con sobretasa
  del 100 % (``FER`` computa el día laborado; ``HE100`` las horas que
  exceden la jornada de referencia).
* **Tardanzas** (``TAR``): minutos de ingreso posteriores al horario
  más la tolerancia configurada; fuera de tolerancia se computa la
  tardanza completa desde la hora programada (criterio v18).

Port de ``hr_attendance_payslip`` (v18). Cambios v19:

* El cálculo dejó de ser SQL sobre ``hr_attendance_monitor``: ahora son
  métodos puros (:meth:`HrTareajeManager._split_night_hours`,
  :meth:`~HrTareajeManager._split_overtime_hours`,
  :meth:`~HrTareajeManager._classify_day`) alimentados directamente por
  ``hr.attendance`` + ``resource.calendar`` — testeables sin marcaciones.
* Las ausencias (DVAC/DMED/DPAT/LCGH/LSGH/SMAR/SENF) ya NO las clasifica
  el tareaje: en v19 fluyen nativamente de ``hr.leave`` → work entries.
  El tareaje solo marca el día como «ausencia» y no lo toca.
* El volcado a boleta ya no reescribe ``worked_days_line_ids`` a mano:
  se engancha en ``hr.payslip._get_worked_day_lines`` DESPUÉS del
  remapeo DLAB/DOM de ``al_hr_pe`` (llama a ``super()`` y solo pisa los
  valores de los conceptos que el tareaje gestiona).
* ``hr.contract.is_overtime`` (v18) → ``hr.version.l10n_pe_is_overtime``.
* Ventana nocturna, umbral de HE 25 %, tolerancia y redondeo de minutos
  (hardcodeados en v18) ahora viven en ``hr.main.parameter``.

Veredicto ``make_replace_vig`` (wizard v18 de reemplazo de vigilante en
la planificación): NO se porta. Operaba sobre ``resource.calendar.line.it``
(la planificación propia v18, sustituida por planning EE — capa del otro
módulo de esta app) y el versionado de vigencias que insinuaba su nombre
lo cubre nativamente ``hr.version`` en v19.
"""
from collections import defaultdict
from datetime import timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.al_hr_pe.tools import custom_round

#: Jornada ordinaria máxima legal: 8 horas diarias (Const. art. 25;
#: D.S. 007-2002-TR art. 1). Referencia de HE100 cuando el día de
#: descanso/feriado laborado no tiene turno programado.
LEGAL_WORKDAY_HOURS = 8.0

#: Frontera para reconocer un turno que cruza la medianoche: los tramos
#: que terminan antes de esta hora se consideran la madrugada del turno
#: iniciado la víspera, y los que empiezan después, su parte nocturna.
NIGHT_SPLIT_HOUR = 12.0

#: Claves de clasificación que produce ``_classify_day``.
TAREAJE_KEYS = ('dlab', 'dlabn', 'htd', 'htn', 'dom', 'fer', 'fal',
                'tar', 'he25', 'he35', 'he100', 'incos')


class HrMainParameter(models.Model):
    """Parámetros del tareaje (v18 los hardcodeaba en el SQL)."""
    _inherit = 'hr.main.parameter'

    tareaje_night_from = fields.Float(
        string='Inicio de horario nocturno', default=22.0,
        help='Hora de inicio de la jornada nocturna (22:00 según el '
             'art. 8 del D.S. 007-2002-TR).')
    tareaje_night_to = fields.Float(
        string='Fin de horario nocturno', default=6.0,
        help='Hora de fin de la jornada nocturna (06:00 según el art. 8 '
             'del D.S. 007-2002-TR).')
    tareaje_he25_hours = fields.Float(
        string='Horas extra al 25 %', default=2.0,
        help='Número de horas extra diarias pagadas con sobretasa del '
             '25 %; el exceso se paga al 35 % (art. 10 del '
             'D.S. 007-2002-TR).')
    tareaje_late_tolerance = fields.Float(
        string='Tolerancia de tardanza (horas)', default=0.0,
        help='Retraso de ingreso no computado como tardanza. Superada '
             'la tolerancia se computa la tardanza completa desde la '
             'hora programada (criterio v18).')
    tareaje_round_minutes = fields.Integer(
        string='Redondeo de minutos', default=0,
        help='Redondea tardanzas y sobretiempo al múltiplo de N minutos '
             'más cercano (0 = sin redondeo).')

    # Tipos de work entry destino de cada concepto del tareaje.
    # Configurables por compañía; el default busca por código PE
    # (convención del proyecto: sin códigos hardcodeados en la lógica).
    tareaje_wet_dlab_id = fields.Many2one(
        'hr.work.entry.type', string='W.E. días laborados (tareaje)',
        default=lambda self: self._default_tareaje_wet('DLAB'))
    tareaje_wet_noct_id = fields.Many2one(
        'hr.work.entry.type', string='W.E. jornada nocturna (tareaje)',
        help='Tipo destino de las horas nocturnas (htn). Por defecto, '
             'HTN de al_hr_pe: sustenta la sobretasa mínima NOCT '
             '(RMV + 35 %).',
        default=lambda self: self._default_tareaje_wet('HTN'))
    tareaje_wet_dom_id = fields.Many2one(
        'hr.work.entry.type', string='W.E. días de descanso (tareaje)',
        default=lambda self: self._default_tareaje_wet('DOM'))
    tareaje_wet_fer_id = fields.Many2one(
        'hr.work.entry.type',
        string='W.E. feriado/descanso laborado (tareaje)',
        default=lambda self: self._default_tareaje_wet('FER'))
    tareaje_wet_fal_id = fields.Many2one(
        'hr.work.entry.type', string='W.E. faltas (tareaje)',
        default=lambda self: self._default_tareaje_wet('FAL'))
    tareaje_wet_tar_id = fields.Many2one(
        'hr.work.entry.type', string='W.E. tardanzas (tareaje)',
        default=lambda self: self._default_tareaje_wet('TAR'))
    tareaje_wet_he25_id = fields.Many2one(
        'hr.work.entry.type', string='W.E. horas extra 25 % (tareaje)',
        default=lambda self: self._default_tareaje_wet('HE25'))
    tareaje_wet_he35_id = fields.Many2one(
        'hr.work.entry.type', string='W.E. horas extra 35 % (tareaje)',
        default=lambda self: self._default_tareaje_wet('HE35'))
    tareaje_wet_he100_id = fields.Many2one(
        'hr.work.entry.type', string='W.E. horas extra 100 % (tareaje)',
        default=lambda self: self._default_tareaje_wet('HE100'))

    @api.model
    def _default_tareaje_wet(self, code):
        return self.env['hr.work.entry.type'].search(
            [('code', '=', code), ('country_id.code', '=', 'PE')], limit=1)

    def get_tareaje_wet_map(self):
        """Mapa concepto del tareaje → ``hr.work.entry.type`` destino.

        Usa el M2O configurado y, en su defecto, el tipo PE por código.
        ``noct`` va a HTN: solo horas (el día ya está en DLAB), que la
        regla NOCT de al_hr_pe usa para la sobretasa mínima del art. 8
        del D.S. 007-2002-TR.
        """
        self.ensure_one()
        return {
            'dlab': self.tareaje_wet_dlab_id
            or self._default_tareaje_wet('DLAB'),
            'noct': self.tareaje_wet_noct_id
            or self._default_tareaje_wet('HTN'),
            'dom': self.tareaje_wet_dom_id or self._default_tareaje_wet('DOM'),
            'fer': self.tareaje_wet_fer_id or self._default_tareaje_wet('FER'),
            'fal': self.tareaje_wet_fal_id or self._default_tareaje_wet('FAL'),
            'tar': self.tareaje_wet_tar_id or self._default_tareaje_wet('TAR'),
            'he25': self.tareaje_wet_he25_id
            or self._default_tareaje_wet('HE25'),
            'he35': self.tareaje_wet_he35_id
            or self._default_tareaje_wet('HE35'),
            'he100': self.tareaje_wet_he100_id
            or self._default_tareaje_wet('HE100'),
        }


class HrVersion(models.Model):
    """Port de ``hr.contract.is_overtime`` (v18) al versionado v19."""
    _inherit = 'hr.version'

    l10n_pe_is_overtime = fields.Boolean(
        string='Sujeto a horas extras (PE)', default=False, tracking=True,
        groups='hr.group_hr_user',
        help='El tareaje calcula sobretiempo (HE 25/35/100 %) para este '
             'trabajador. Desmarcar para personal de dirección y no '
             'sujeto a fiscalización inmediata, excluidos de la jornada '
             'máxima (art. 5 del D.S. 007-2002-TR; concordante con la '
             'excepción de jornada PLAME).')


class HrTareajeManager(models.Model):
    """Tareaje del periodo: generar desde asistencias → revisar → aplicar.

    Flujo (port del v18):

    1. **Procesar** (borrador): lee ``hr.attendance`` del periodo, lo
       clasifica día a día con los métodos puros y crea las líneas por
       empleado (editables para el ajuste manual previo al cierre).
    2. **Revisar/editar**: el responsable corrige horas o registra horas
       a compensar por día.
    3. **Aplicar al periodo** (→ hecho): las boletas del periodo leen el
       tareaje al refrescar sus días trabajados
       (``hr.payslip._get_worked_day_lines``). Solo los tareajes en
       estado «Aplicado» alimentan la boleta.
    """
    _name = 'hr.tareaje.manager'
    _description = 'Gestión de tareaje'
    _order = 'date_start desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Nombre', required=True)
    state = fields.Selection(
        selection=[('draft', 'Borrador'), ('done', 'Aplicado')],
        string='Estado', readonly=True, copy=False, default='draft')
    date_start = fields.Date(
        string='Desde', required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1))
    date_end = fields.Date(
        string='Hasta', required=True,
        default=lambda self: (fields.Date.context_today(self).replace(day=1)
                              + timedelta(days=32)).replace(day=1)
        - timedelta(days=1))
    time_tolerancia = fields.Float(
        string='Tolerancia de tardanza (horas)',
        default=lambda self: self._default_time_tolerancia(),
        help='Default desde los Parámetros Principales; editable por '
             'tareaje.')
    is_compute_he = fields.Boolean(
        string='Calcular horas extras', default=False,
        help='Interruptor global del sobretiempo del tareaje; se cruza '
             'con «Sujeto a horas extras» de la ficha del trabajador.')
    tareaje_line_ids = fields.One2many(
        'hr.tareaje.manager.line', 'tareaje_id', string='Detalle de tareaje')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)

    _tareaje_dates_check = models.Constraint(
        'CHECK(date_end >= date_start)',
        'La fecha final del tareaje debe ser posterior o igual a la '
        'inicial.')

    @api.model
    def _default_time_tolerancia(self):
        param = self.env['hr.main.parameter'].search(
            [('company_id', '=', self.env.company.id)], limit=1)
        return param.tareaje_late_tolerance if param else 0.0

    # ------------------------------------------------------------------
    # Flujo
    # ------------------------------------------------------------------
    def action_close(self):
        """Aplica el tareaje al periodo (las boletas lo leen al
        refrescar los días trabajados).

        La boleta suma TODOS los tareajes aplicados del periodo: dos
        tareajes aplicados que se solapan en fechas y comparten
        trabajadores duplicarían días, horas extra y faltas.
        """
        for record in self:
            employees = record.tareaje_line_ids.employee_id
            if not employees:
                continue
            overlapping = self.search([
                ('id', '!=', record.id),
                ('state', '=', 'done'),
                ('company_id', '=', record.company_id.id),
                ('date_start', '<=', record.date_end),
                ('date_end', '>=', record.date_start),
                ('tareaje_line_ids.employee_id', 'in', employees.ids),
            ], limit=1)
            if overlapping:
                raise UserError(self.env._(
                    'El tareaje «%(other)s» ya está aplicado en fechas que '
                    'se solapan con «%(name)s» para los mismos '
                    'trabajadores. Reabra uno de los dos antes de aplicar.',
                    other=overlapping.name, name=record.name))
        self.write({'state': 'done'})

    def action_reopen(self):
        """Vuelve a borrador si ninguna boleta cerrada lo consumió."""
        for record in self.filtered(lambda t: t.state == 'done'):
            employees = record.tareaje_line_ids.employee_id
            if not employees:
                continue
            closed = self.env['hr.payslip'].search_count([
                ('employee_id', 'in', employees.ids),
                ('company_id', '=', record.company_id.id),
                ('state', 'in', ('validated', 'paid')),
                ('date_from', '<=', record.date_end),
                ('date_to', '>=', record.date_start),
            ], limit=1)
            if closed:
                raise UserError(self.env._(
                    'No puede reabrir «%(name)s»: hay boletas validadas o '
                    'pagadas del periodo que ya usaron este tareaje.',
                    name=record.name))
        self.write({'state': 'draft'})

    @api.ondelete(at_uninstall=False)
    def _unlink_if_draft(self):
        if any(tareaje.state != 'draft' for tareaje in self):
            raise UserError(self.env._(
                'No puede eliminar tareajes que no estén en estado '
                'borrador.'))

    # ------------------------------------------------------------------
    # Métodos puros de clasificación (testeables sin marcaciones)
    # Convención: las horas son flotantes relativos a la medianoche del
    # día tareado; una salida posterior a medianoche supera 24.0.
    # ------------------------------------------------------------------
    @api.model
    def _round_to_minutes(self, hours, minutes=0):
        """Redondea una duración al múltiplo de ``minutes`` más cercano
        (0 = sin redondeo). Parametriza el criterio de minutos que v18
        no contemplaba."""
        if not minutes or minutes <= 0:
            return hours
        step = minutes / 60.0
        return round(hours / step) * step

    @api.model
    def _split_night_hours(self, start, stop, night_from=22.0, night_to=6.0):
        """Divide el intervalo trabajado en horas diurnas y nocturnas.

        Jornada nocturna: entre las 22:00 y las 06:00 (art. 8 del
        D.S. 007-2002-TR), ventana parametrizable. Soporta turnos que
        cruzan la medianoche: si ``stop`` <= ``start`` se asume salida
        al día siguiente (se normaliza a ``stop + 24``).

        :return: tupla ``(horas_diurnas, horas_nocturnas)``.
        """
        if stop <= start:
            stop += 24.0

        def _overlap(a0, a1, b0, b1):
            return max(0.0, min(a1, b1) - max(a0, b0))

        night = 0.0
        for base in (0.0, 24.0, 48.0):
            night += _overlap(start, stop, base, base + night_to)
            night += _overlap(start, stop, base + night_from, base + 24.0)
        total = stop - start
        return custom_round(total - night), custom_round(night)

    @api.model
    def _split_overtime_hours(self, extra_hours, he25_limit=2.0):
        """Reparte el sobretiempo del día entre HE 25 % y HE 35 %.

        Art. 10 del D.S. 007-2002-TR: las dos primeras horas extra del
        día se pagan con sobretasa mínima del 25 % y las siguientes con
        35 % (umbral parametrizable).

        :return: tupla ``(he25, he35)``.
        """
        extra = max(extra_hours, 0.0)
        he25 = min(extra, he25_limit)
        he35 = max(extra - he25_limit, 0.0)
        return custom_round(he25), custom_round(he35)

    @api.model
    def _classify_day(self, marks_in, marks_out, sched_in=None, sched_out=None,
                      break_hours=0.0, day_kind='workday', night_from=22.0,
                      night_to=6.0, he25_limit=2.0, tolerance=0.0,
                      round_minutes=0, compute_overtime=True):
        """Clasifica un día de marcaciones en los conceptos del tareaje.

        Método puro: sin acceso a registros. Entradas en horas flotantes
        relativas a la medianoche del día (``marks_out``/``sched_out``
        pueden superar 24 si el turno cruza la medianoche; también se
        normalizan si llegan menores que la hora de entrada).

        :param marks_in/marks_out: marcaciones reales (``None`` = sin
            marcación).
        :param sched_in/sched_out: horario programado del día (``None``
            = sin turno programado).
        :param break_hours: refrigerio no computable dentro del turno.
        :param day_kind: ``workday`` | ``descanso`` | ``feriado``.
        :param compute_overtime: si es falso, el sobretiempo no se
            computa (trabajador no sujeto a HE — art. 5 del
            D.S. 007-2002-TR — o tareaje sin HE).
        :return: dict con las claves de :data:`TAREAJE_KEYS`.

        Reglas (con su norma):

        * Sin marcación: día laborable → falta (``fal``); descanso o
          feriado → día de descanso (``dom``) — D.Leg. 713 arts. 1 y 5.
        * Marcación incompleta (solo entrada o solo salida) →
          inconsistencia (``incos``), sin clasificar horas.
        * Descanso/feriado trabajado: ``dom`` conserva el día de
          descanso (su remuneración ya está en el sueldo mensual) y
          ``fer`` computa ADEMÁS el día laborado, que la regla salarial
          FER paga con la sobretasa (D.Leg. 713 arts. 3-4 y 9: se paga
          «adicionalmente» la labor con sobretasa del 100 %). Sin
          ``dom`` el Básico perdía el día y FER solo lo reponía, con lo
          que la sobretasa salía en cero. ``he100`` computa las horas que
          exceden la salida
          programada o, sin turno de referencia, la jornada legal de
          8 h (:data:`LEGAL_WORKDAY_HOURS`).
          TODO(fase6-revisar): validar con contabilidad el reparto
          FER (día) + HE100 (exceso) — v18 además sumaba estos días a
          htd/dlab, lo que duplicaba el concepto y aquí se corrigió.
        * Día laborable trabajado: ``tar`` = retraso de ingreso si
          supera la tolerancia (se computa completo desde la hora
          programada, criterio v18); las horas dentro del turno se
          reparten día/noche (``htd``/``htn`` — art. 8 D.S. 007-2002-TR)
          y ``dlab``/``dlabn`` prorratean el día asistido en la misma
          proporción (``dlab + dlabn = 1``, criterio v18); el
          sobretiempo tras la salida programada se reparte en
          ``he25``/``he35`` (art. 10 D.S. 007-2002-TR).
        """
        result = dict.fromkeys(TAREAJE_KEYS, 0.0)
        has_in = marks_in is not None
        has_out = marks_out is not None

        if not has_in and not has_out:
            if day_kind == 'workday':
                result['fal'] = 1.0
            else:
                result['dom'] = 1.0
            return result
        if not (has_in and has_out):
            result['incos'] = 1.0
            return result

        out = marks_out + 24.0 if marks_out <= marks_in else marks_out
        worked = max(0.0, out - marks_in - break_hours)
        if worked <= 0:
            result['incos'] = 1.0
            return result

        has_schedule = sched_in is not None and sched_out is not None
        if has_schedule:
            sout = sched_out + 24.0 if sched_out <= sched_in else sched_out

        if day_kind in ('descanso', 'feriado'):
            # D.Leg. 713 arts. 3-4 y 9: labor en día de descanso o feriado
            # sin descanso sustitutorio → se paga ADEMÁS del descanso
            # (dom, ya incluido en el sueldo) con sobretasa del 100 %.
            result['dom'] = 1.0
            result['fer'] = 1.0
            if compute_overtime:
                if has_schedule:
                    he100 = max(0.0, out - sout)
                else:
                    he100 = max(0.0, worked - LEGAL_WORKDAY_HOURS)
                result['he100'] = custom_round(
                    self._round_to_minutes(he100, round_minutes))
            return result

        # Día laborable con marcación.
        if not has_schedule:
            # Sin turno de referencia (calendario incompleto): las horas
            # marcadas se toman como jornada ordinaria, sin tardanza ni
            # sobretiempo. TODO(fase6-revisar): ¿computar HE sobre la
            # jornada legal de 8 h en este caso?
            sched_in, sout = marks_in, out

        delay = max(0.0, marks_in - sched_in)
        after = max(0.0, out - sout)
        # Quien llega tarde y se queda después de la salida primero
        # completa su jornada: ese tiempo compensa la tardanza y no es
        # sobretiempo (solo es HE lo que excede la jornada, art. 9-10).
        compensated = min(delay, after) if delay > tolerance else 0.0
        delay -= compensated
        after -= compensated
        if delay > tolerance:
            result['tar'] = custom_round(
                self._round_to_minutes(delay, round_minutes))

        if compute_overtime:
            extra = self._round_to_minutes(after, round_minutes)
            result['he25'], result['he35'] = self._split_overtime_hours(
                extra, he25_limit=he25_limit)

        # Horas dentro del turno (base sin sobretiempo), partidas en
        # diurnas/nocturnas. El refrigerio se descuenta de las horas
        # diurnas (aproximación: el refrigerio cae de día; el remanente,
        # si lo hubiera, se descuenta de las nocturnas).
        base_start = max(marks_in, sched_in)
        base_stop = min(out, sout)
        if base_stop > base_start:
            htd, htn = self._split_night_hours(
                base_start, base_stop, night_from=night_from,
                night_to=night_to)
            rest_break = max(0.0, break_hours - htd)
            htd = max(0.0, htd - break_hours)
            htn = max(0.0, htn - rest_break)
            result['htd'], result['htn'] = \
                custom_round(htd), custom_round(htn)
            total = htd + htn
            if total:
                result['dlab'] = custom_round(htd / total, 4)
                result['dlabn'] = custom_round(1.0 - result['dlab'], 4)
        return result

    # ------------------------------------------------------------------
    # Generación desde hr.attendance
    # ------------------------------------------------------------------
    def action_generate(self):
        """Genera las líneas del tareaje desde las marcaciones.

        Consolida ``hr.attendance`` por empleado y día local (zona
        horaria del trabajador), determina el contexto del día (turno
        del calendario, feriado, ausencia aprobada) y delega la
        clasificación en :meth:`_classify_day`.

        Solo tarea a los empleados con al menos una marcación en el
        periodo: la detección de faltas de trabajadores planificados sin
        marcación alguna corresponde al monitor de asistencia (capa
        planning de este mismo módulo).
        """
        for record in self:
            if record.state != 'draft':
                raise UserError(self.env._(
                    'Solo puede procesar tareajes en borrador.'))
            record.tareaje_line_ids.unlink()
            param = self.env['hr.main.parameter'].get_main_parameter(
                record.company_id)
            marks_by_emp_day = record._get_marks_by_employee_day()
            holidays = record._get_public_holidays()
            employees = self.env['hr.employee'].browse(
                [emp.id for emp in marks_by_emp_day])
            leaves_by_emp = record._get_leave_days(employees)
            Line = self.env['hr.tareaje.manager.line']
            for employee in employees:
                day_vals = []
                calendar = employee.resource_calendar_id \
                    or record.company_id.resource_calendar_id
                # Versión vigente al cierre del periodo tareado, no la
                # actual (el flag puede haber cambiado después).
                version = employee._get_version(record.date_end)
                compute_he = record.is_compute_he and bool(
                    version.l10n_pe_is_overtime)
                day = record.date_start
                while day <= record.date_end:
                    schedule = record._get_day_schedule(calendar, day)
                    if day in holidays.get(calendar.id, set()) \
                            or day in holidays.get(False, set()):
                        day_kind = 'feriado'
                    elif schedule is None:
                        day_kind = 'descanso'
                    else:
                        day_kind = 'workday'
                    marks = marks_by_emp_day[employee].get(day)
                    if day in leaves_by_emp.get(employee.id, set()) \
                            and not marks:
                        # Ausencia aprobada: la cubre hr.leave → work
                        # entries nativas; el tareaje no la clasifica.
                        day_vals.append(record._prepare_day_vals(
                            employee, day, None, schedule, 'ausencia',
                            dict.fromkeys(TAREAJE_KEYS, 0.0)))
                        day = day + timedelta(days=1)
                        continue
                    sched_in, sched_out, break_hours = \
                        schedule or (None, None, 0.0)
                    values = record._classify_day(
                        marks[0] if marks else None,
                        marks[1] if marks else None,
                        sched_in=sched_in, sched_out=sched_out,
                        break_hours=break_hours, day_kind=day_kind,
                        night_from=param.tareaje_night_from,
                        night_to=param.tareaje_night_to,
                        he25_limit=param.tareaje_he25_hours,
                        tolerance=record.time_tolerancia,
                        round_minutes=param.tareaje_round_minutes,
                        compute_overtime=compute_he)
                    state = record._day_state(marks, day_kind, values)
                    day_vals.append(record._prepare_day_vals(
                        employee, day, marks, schedule, state, values))
                    day = day + timedelta(days=1)
                totals = defaultdict(float)
                for vals in day_vals:
                    for key in TAREAJE_KEYS:
                        totals[key] += vals.get(key, 0.0)
                Line.create({
                    'tareaje_id': record.id,
                    'employee_id': employee.id,
                    'attendance_line_ids': [(0, 0, vals)
                                            for vals in day_vals],
                    **{key: custom_round(totals[key])
                       for key in TAREAJE_KEYS},
                })
        return True

    def _prepare_day_vals(self, employee, day, marks, schedule, state,
                          values):
        self.ensure_one()
        return {
            'employee_id': employee.id,
            'fecha': day,
            'day_name': day.strftime('%A'),
            'horario': '%05.2f - %05.2f' % (schedule[0], schedule[1])
            if schedule else '',
            'mar_hora_ing': marks[0] if marks else 0.0,
            # Sin salida (marcación abierta u olvidada) → 0.
            'mar_hora_sal': marks[1] if marks and marks[1] is not None
            else 0.0,
            'worked_hours': custom_round(
                max(0.0, (marks[1] if marks[1] > marks[0]
                          else marks[1] + 24.0) - marks[0]))
            if marks and marks[1] is not None else 0.0,
            'state': state,
            **{key: values.get(key, 0.0) for key in TAREAJE_KEYS},
        }

    @api.model
    def _day_state(self, marks, day_kind, values):
        if values.get('incos'):
            return 'incompleto'
        if not marks:
            if day_kind == 'feriado':
                return 'feriado'
            return 'descanso' if day_kind == 'descanso' else 'falta'
        if day_kind == 'feriado':
            return 'feriado_trab'
        if day_kind == 'descanso':
            return 'descanso_trab'
        return 'ok'

    def _get_marks_by_employee_day(self):
        """Consolida las marcaciones del periodo por empleado y día
        local: ``{empleado: {fecha: (hora_ing, hora_sal)}}`` con horas
        flotantes relativas a la medianoche del día de ingreso (la
        salida puede superar 24 si cruza la medianoche)."""
        self.ensure_one()
        start_dt = fields.Datetime.to_datetime(self.date_start) \
            - timedelta(hours=14)
        end_dt = fields.Datetime.to_datetime(self.date_end) \
            + timedelta(days=1, hours=14)
        # Las marcaciones sin salida también entran: sin ellas, quien
        # olvidó marcar la salida quedaba como falta en vez de como
        # marcación incompleta.
        attendances = self.env['hr.attendance'].search([
            ('employee_id.company_id', '=', self.company_id.id),
            ('check_in', '<=', end_dt),
            '|', ('check_out', '=', False), ('check_out', '>=', start_dt),
        ])
        raw = defaultdict(lambda: defaultdict(list))
        for att in attendances:
            tz = pytz.timezone(att.employee_id.tz or 'America/Lima')
            local_in = pytz.utc.localize(att.check_in).astimezone(tz)
            day = local_in.date()
            if not (self.date_start <= day <= self.date_end):
                continue
            hour_in = local_in.hour + local_in.minute / 60.0 \
                + local_in.second / 3600.0
            hour_out = None
            if att.check_out:
                local_out = pytz.utc.localize(att.check_out).astimezone(tz)
                hour_out = (local_out.date() - day).days * 24.0 \
                    + local_out.hour + local_out.minute / 60.0 \
                    + local_out.second / 3600.0
            raw[att.employee_id][day].append((hour_in, hour_out))
        result = defaultdict(dict)
        for employee, days in raw.items():
            for day, pairs in days.items():
                # Varias marcaciones el mismo día: primera entrada y
                # última salida (consolidación v18). Si alguna quedó sin
                # salida, el día es una marcación incompleta.
                outs = [pair[1] for pair in pairs]
                result[employee][day] = (
                    min(pair[0] for pair in pairs),
                    None if None in outs else max(outs))
        return result

    @api.model
    def _get_day_schedule(self, calendar, day):
        """Turno del calendario para la fecha: ``(entrada, salida,
        refrigerio)`` o ``None`` si el día no tiene turno (descanso).
        El refrigerio son los huecos entre tramos de trabajo.
        TODO(fase6-revisar): calendarios de dos semanas (week_type) se
        tratan como de una semana."""
        if not calendar:
            return None
        if self._night_shift_on_next_day(calendar):
            # Convención estándar de Odoo: el turno del lunes 22:00-06:00
            # es lunes 22-24 + martes 00-06. La madrugada del día es la
            # cola del turno de la víspera y no un turno propio; la del
            # día siguiente completa el turno nocturno de hoy.
            def day_tramos(weekday):
                return [(att.hour_from, att.hour_to)
                        for att in calendar.attendance_ids.sorted('hour_from')
                        if att.dayofweek == str(weekday)
                        and att.day_period != 'lunch']
            today = [t for t in day_tramos(day.weekday())
                     if not self._is_dawn_tramo(t)]
            if not today:
                return None
            if today[-1][1] == 24.0:
                today += [(desde + 24.0, hasta + 24.0)
                          for desde, hasta in day_tramos((day.weekday() + 1) % 7)
                          if self._is_dawn_tramo((desde, hasta))]
            break_hours = sum(
                max(0.0, today[i + 1][0] - today[i][1])
                for i in range(len(today) - 1))
            return (today[0][0], today[-1][1], break_hours)
        segments = calendar.attendance_ids.filtered(
            lambda att: att.dayofweek == str(day.weekday())
            and att.day_period != 'lunch')
        if not segments:
            return None
        segments = segments.sorted('hour_from')
        tramos = [(seg.hour_from, seg.hour_to) for seg in segments]

        # Turno nocturno: Odoo no admite hour_to > 24, así que un turno
        # que cruza la medianoche se modela con un tramo que cierra a las
        # 24:00 y otro que abre a las 00:00 del mismo día de la semana
        # (p. ej. 22:00-24:00 + 00:00-06:00). Se reordena como un único
        # turno continuo 22:00 → 30:00; sin esto, el turno se leería
        # como 00:00-24:00 con 16 h de "refrigerio" y el día quedaría
        # descartado como marcación incompleta.
        if len(tramos) > 1 and tramos[0][0] == 0.0 and tramos[-1][1] == 24.0:
            madrugada = [t for t in tramos if t[1] <= NIGHT_SPLIT_HOUR]
            noche = [t for t in tramos if t[0] >= NIGHT_SPLIT_HOUR]
            if madrugada and noche and len(madrugada) + len(noche) == len(
                    tramos):
                tramos = noche + [(desde + 24.0, hasta + 24.0)
                                  for desde, hasta in madrugada]

        break_hours = sum(
            max(0.0, tramos[i + 1][0] - tramos[i][1])
            for i in range(len(tramos) - 1))
        return (tramos[0][0], tramos[-1][1], break_hours)

    @staticmethod
    def _is_dawn_tramo(tramo):
        """Tramo de madrugada: empieza a las 00:00 y acaba antes del corte
        nocturno (la cola de un turno que cruzó la medianoche)."""
        return tramo[0] == 0.0 and tramo[1] <= NIGHT_SPLIT_HOUR

    @api.model
    def _night_shift_on_next_day(self, calendar):
        """¿El calendario pone la madrugada del turno nocturno en el día
        siguiente (convención estándar de Odoo)?

        Es así cuando los días con tramo hasta las 24:00 y los días con
        tramo de madrugada no coinciden, pero sí coinciden desplazando un
        día (lunes noche → martes madrugada). Si coinciden tal cual, el
        calendario sigue la convención de un solo día de la semana.
        """
        night_days, dawn_days = set(), set()
        for att in calendar.attendance_ids:
            if att.day_period == 'lunch':
                continue
            if att.hour_to == 24.0 and att.hour_from >= NIGHT_SPLIT_HOUR:
                night_days.add(int(att.dayofweek))
            elif self._is_dawn_tramo((att.hour_from, att.hour_to)):
                dawn_days.add(int(att.dayofweek))
        return bool(night_days) and night_days != dawn_days \
            and {(d + 1) % 7 for d in night_days} == dawn_days

    @api.model
    def _to_local_date(self, value, tz_name):
        """Fecha local (``tz_name``) de un datetime UTC ingenuo."""
        tz = pytz.timezone(tz_name or 'America/Lima')
        return pytz.utc.localize(value).astimezone(tz).date()

    def _get_public_holidays(self):
        """Feriados (D.Leg. 713 arts. 5-9): descansos globales de los
        calendarios — ``{calendar_id o False: {fechas}}``.

        Con los feriados PE instalados solo cuentan los descansos que
        vienen de un feriado (``pe_public_holiday_id``): un cierre de la
        compañía también es un descanso global y no da sobretasa del
        100 %. El medio feriado (el del módulo dura de 00:00 a 13:00)
        tampoco convierte el día entero en feriado: solo cuentan los
        descansos de 20 h o más.
        """
        self.ensure_one()
        Leaves = self.env['resource.calendar.leaves']
        domain = [
            ('resource_id', '=', False),
            ('company_id', 'in', (False, self.company_id.id)),
            ('date_from', '<=', fields.Datetime.to_datetime(self.date_end)
             + timedelta(days=1)),
            ('date_to', '>=', fields.Datetime.to_datetime(self.date_start)),
        ]
        if 'pe_public_holiday_id' in Leaves._fields:
            domain.append(('pe_public_holiday_id', '!=', False))
        leaves = Leaves.search(domain).filtered(
            lambda leave: leave.date_to - leave.date_from
            >= timedelta(hours=20))
        holidays = defaultdict(set)
        default_tz = self.company_id.resource_calendar_id.tz \
            or 'America/Lima'
        for leave in leaves:
            # Las fechas se guardan en UTC: un feriado de 00:00 a 23:59
            # hora de Lima termina a las 04:59 UTC del día siguiente, así
            # que .date() en UTC marcaba también ese día como feriado.
            tz = leave.calendar_id.tz or default_tz
            day = max(self._to_local_date(leave.date_from, tz),
                      self.date_start)
            last = min(self._to_local_date(leave.date_to, tz),
                       self.date_end)
            while day <= last:
                holidays[leave.calendar_id.id or False].add(day)
                day += timedelta(days=1)
        return holidays

    def _get_leave_days(self, employees):
        """Días cubiertos por ausencias aprobadas: ``{employee_id:
        {fechas}}``."""
        self.ensure_one()
        leaves = self.env['hr.leave'].search([
            ('employee_id', 'in', employees.ids),
            ('state', '=', 'validate'),
            ('date_from', '<=', fields.Datetime.to_datetime(self.date_end)
             + timedelta(days=1)),
            ('date_to', '>=', fields.Datetime.to_datetime(self.date_start)),
        ])
        days = defaultdict(set)
        for leave in leaves:
            # Fechas locales de la solicitud (no la conversión UTC de
            # date_from/date_to, que corre un día en ausencias de día
            # completo).
            tz = leave.employee_id.tz or 'America/Lima'
            day = max(leave.request_date_from
                      or self._to_local_date(leave.date_from, tz),
                      self.date_start)
            last = min(leave.request_date_to
                       or self._to_local_date(leave.date_to, tz),
                       self.date_end)
            while day <= last:
                days[leave.employee_id.id].add(day)
                day += timedelta(days=1)
        return days

    # ------------------------------------------------------------------
    # Volcado a boleta
    # ------------------------------------------------------------------
    @api.model
    def _get_payslip_totals(self, employee, date_from, date_to,
                            company=None):
        """Totales del tareaje aplicado para un empleado y periodo.

        Suma los días de los tareajes en estado «Aplicado» cuyo detalle
        cae dentro del periodo de la boleta (soporta quincenas y
        tareajes que abarcan más de un periodo). Las horas a compensar
        de cada día descuentan primero HE 25 % y luego HE 35 %
        (criterio v18 del volcado a boleta).

        :return: dict ``{concepto: total}`` o ``{}`` si no hay tareaje
            aplicado (la boleta conserva entonces el cálculo nativo).
        """
        company = company or employee.company_id
        day_lines = self.env['hr.tareaje.manager.line.attendance'].search([
            ('tareaje_line_id.tareaje_id.state', '=', 'done'),
            ('tareaje_line_id.employee_id', '=', employee.id),
            ('company_id', '=', company.id),
            ('fecha', '>=', date_from),
            ('fecha', '<=', date_to),
        ])
        if not day_lines:
            return {}
        totals = defaultdict(float)
        for day in day_lines:
            he25, he35 = day.he25, day.he35
            compensate = day.hours_compensate
            taken = min(compensate, he25)
            he25 -= taken
            he35 = max(0.0, he35 - (compensate - taken))
            totals['he25'] += he25
            totals['he35'] += he35
            for key in TAREAJE_KEYS:
                if key in ('he25', 'he35'):
                    continue
                totals[key] += day[key]
        return {key: custom_round(value) for key, value in totals.items()}


class HrTareajeManagerLine(models.Model):
    _name = 'hr.tareaje.manager.line'
    _description = 'Tareaje por empleado'
    _rec_name = 'employee_id'
    _order = 'employee_id'
    _check_company_auto = True

    tareaje_id = fields.Many2one(
        'hr.tareaje.manager', string='Tareaje', required=True,
        ondelete='cascade', index=True,
        check_company=True)
    company_id = fields.Many2one(
        related='tareaje_id.company_id', store=True, index=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', required=True, index=True,
        check_company=True)
    incos = fields.Float(string='Inconsistencias')
    dlab = fields.Float(string='Días laborados')
    dlabn = fields.Float(string='Días nocturnos')
    htd = fields.Float(string='Horas diurnas')
    htn = fields.Float(string='Horas nocturnas')
    dom = fields.Float(string='Días de descanso')
    fer = fields.Float(string='Feriado/descanso laborado')
    fal = fields.Float(string='Faltas')
    tar = fields.Float(string='Tardanzas (h)')
    he25 = fields.Float(string='HE 25 %')
    he35 = fields.Float(string='HE 35 %')
    he100 = fields.Float(string='HE 100 %')
    attendance_line_ids = fields.One2many(
        'hr.tareaje.manager.line.attendance', 'tareaje_line_id',
        string='Detalle diario')

    def action_show_details(self):
        self.ensure_one()
        return {
            'name': self.env._('Detalle diario del tareaje'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.tareaje.manager.line.attendance',
            'view_mode': 'list',
            'domain': [('tareaje_line_id', '=', self.id)],
            'target': 'current',
        }


class HrTareajeManagerLineAttendance(models.Model):
    """Día tareado de un empleado (nombre v18 conservado para facilitar
    la migración de datos)."""
    _name = 'hr.tareaje.manager.line.attendance'
    _description = 'Detalle diario del tareaje'
    _rec_name = 'employee_id'
    _order = 'fecha'
    _check_company_auto = True

    tareaje_line_id = fields.Many2one(
        'hr.tareaje.manager.line', string='Línea de tareaje',
        required=True, ondelete='cascade', index=True,
        check_company=True)
    company_id = fields.Many2one(
        related='tareaje_line_id.company_id', store=True, index=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', check_company=True)
    fecha = fields.Date(string='Fecha')
    day_name = fields.Char(string='Día')
    horario = fields.Char(string='Horario')
    state = fields.Selection(
        selection=[
            ('ok', 'Asistió'),
            ('falta', 'Falta'),
            ('incompleto', 'Marcación incompleta'),
            ('descanso', 'Día de descanso'),
            ('feriado', 'Feriado'),
            ('descanso_trab', 'Descanso trabajado'),
            ('feriado_trab', 'Feriado trabajado'),
            ('ausencia', 'Ausencia aprobada'),
        ], string='Estado')
    mar_hora_ing = fields.Float(string='Marcación de ingreso')
    mar_hora_sal = fields.Float(string='Marcación de salida')
    worked_hours = fields.Float(string='Horas marcadas')
    incos = fields.Float(string='Inconsistencia')
    dlab = fields.Float(string='Día laborado')
    dlabn = fields.Float(string='Día nocturno')
    htd = fields.Float(string='Horas diurnas')
    htn = fields.Float(string='Horas nocturnas')
    dom = fields.Float(string='Descanso')
    fer = fields.Float(string='Feriado/descanso laborado')
    fal = fields.Float(string='Falta')
    tar = fields.Float(string='Tardanza (h)')
    he25 = fields.Float(string='HE 25 %')
    he35 = fields.Float(string='HE 35 %')
    he100 = fields.Float(string='HE 100 %')
    hours_compensate = fields.Float(
        string='Horas a compensar',
        help='Horas extra compensadas con descanso (convenio de '
             'compensación, art. 10 in fine del D.S. 007-2002-TR): '
             'descuentan primero HE 25 % y luego HE 35 % al volcar a '
             'la boleta.')


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _get_worked_day_lines(self, domain=None, check_out_of_version=True):
        """Vuelca el tareaje aplicado a los días trabajados de la boleta.

        Llama SIEMPRE a ``super()`` (motor nativo + capa al_hr_pe, que
        remapea la asistencia nativa a DLAB, completa con líneas a cero
        todos los conceptos PE y calcula el complemento DOM) y después
        SOLO sustituye los valores de los conceptos que el tareaje
        gestiona (DLAB, nocturnidad, DOM, FER, FAL, TAR, HE25/35/100),
        cuando existe un tareaje «Aplicado» que cubra el periodo del
        empleado. Sin tareaje aplicado, la boleta queda intacta.

        Nota: al aplicar tareaje, DLAB/DOM del cálculo nativo se
        sustituyen por los del tareaje (asistencia real manda sobre el
        calendario — comportamiento v18 del modo «Asistencias»).
        """
        res = super()._get_worked_day_lines(
            domain=domain, check_out_of_version=check_out_of_version)
        if self.struct_id.country_id.code != 'PE' or not self.employee_id \
                or not self.date_from or not self.date_to:
            return res
        totals = self.env['hr.tareaje.manager']._get_payslip_totals(
            self.employee_id, self.date_from, self.date_to,
            company=self.company_id)
        if not totals:
            return res
        param = self.env['hr.main.parameter'].search(
            [('company_id', '=', self.company_id.id)], limit=1)
        if not param:
            return res
        wet_map = param.get_tareaje_wet_map()
        assignments = self._l10n_pe_tareaje_assignments(totals)
        for bucket, (days, hours) in assignments.items():
            wet = wet_map.get(bucket)
            if not wet:
                continue  # p. ej. nocturnidad sin tipo configurado
            if bucket == 'noct' and wet == wet_map.get('dlab'):
                continue  # mismo tipo que DLAB: ya lleva esas horas
            found = False
            for vals in res:
                if vals.get('work_entry_type_id') == wet.id:
                    vals['number_of_days'] = days
                    vals['number_of_hours'] = hours
                    found = True
            if not found:
                res.append({
                    'sequence': wet.sequence,
                    'work_entry_type_id': wet.id,
                    'number_of_days': days,
                    'number_of_hours': hours,
                })
        return res

    @api.model
    def _l10n_pe_tareaje_assignments(self, totals):
        """Concepto del tareaje → ``(días, horas)`` para la boleta.

        DLAB lleva el día COMPLETO asistido (parte diurna + nocturna): el
        Básico solo cuenta DLAB, así que un turno de 22 a 06 dejaba el
        Básico en cero. La nocturnidad queda solo informativa (horas, sin
        días) hasta que exista la regla de sobretasa nocturna.
        """
        return {
            'dlab': (totals.get('dlab', 0.0) + totals.get('dlabn', 0.0),
                     totals.get('htd', 0.0) + totals.get('htn', 0.0)),
            'noct': (0.0, totals.get('htn', 0.0)),
            'dom': (totals.get('dom', 0.0), 0.0),
            'fer': (totals.get('fer', 0.0), 0.0),
            'fal': (totals.get('fal', 0.0), 0.0),
            'tar': (0.0, totals.get('tar', 0.0)),
            'he25': (0.0, totals.get('he25', 0.0)),
            'he35': (0.0, totals.get('he35', 0.0)),
            'he100': (0.0, totals.get('he100', 0.0)),
        }
