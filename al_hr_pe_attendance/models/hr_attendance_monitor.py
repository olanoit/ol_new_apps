# -*- coding: utf-8 -*-
"""Monitor diario de asistencia: turno planificado vs. marcación real.

Port del ``hr_attendance_monitor.py`` v18 (vista SQL) recompuesto
sobre los modelos nativos v19:

* Turnos planificados: ``planning.slot`` publicados (antes el clon
  ``hr.assistance.planning.line``).
* Días de descanso del régimen atípico: derivados de
  ``l10n_pe.hr.shift.cycle.assignment`` (antes líneas con
  ``is_day_rest``; en v19 los descansos no generan slot porque un slot
  publicado se convierte en work entry vía ``hr_work_entry_planning``).
* Marcaciones: ``hr.attendance`` agregadas por día local del empleado
  (el campo nativo ``hr.attendance.date`` ya se calcula en la zona
  horaria del empleado). Con 4 marcaciones (salida/retorno de
  refrigerio) la suma de ``worked_hours`` descuenta sola el
  refrigerio, por lo que desaparecen las columnas ``ref_*`` del v18.
* Ausencias: ``hr.leave`` validadas; vacaciones se distinguen con la
  bandera configurable ``l10n_pe_is_vacation`` del tipo de ausencia
  (el v18 hardcodeaba el código '23' de la T21).
* Feriados: ``resource.calendar.leaves`` globales (festivos públicos:
  sin recurso ni calendario), filtrados por compañía.

Corrección TZ (plan §5): el v18 restaba el literal ``'5 hr'`` (Lima
UTC−5 cableado). Aquí toda conversión usa
``AT TIME ZONE 'UTC' AT TIME ZONE <tz del recurso>``, con el ``tz``
del ``resource.resource`` del empleado, así que la vista es correcta
para cualquier zona horaria y ante cambios normativos de hora.

Registro de control de asistencia: D.S. 004-2006-TR obliga al
empleador a registrar ingreso y salida del personal; este monitor es
la vista de fiscalización en tiempo real de ese registro.

TODO(fase6-revisar): el monitor solo cubre días con turno publicado o
descansos de ciclo atípico. El v18 generaba línea para *todos* los
días del rango planificado; si algún cliente planifica con horario
fijo sin publicar slots (work_entry_source = 'calendar'), evaluar una
tercera rama UNION desde ``resource.calendar.attendance``.
TODO(fase6-revisar): se eliminaron las columnas ``ref_*`` del régimen
de 4 marcaciones: con varias ``hr.attendance`` por día la suma de
``worked_hours`` ya descuenta el refrigerio; confirmar con el usuario
que no necesita ver el horario de refrigerio planificado por columna.
"""
from odoo import api, fields, models, tools


class HrLeaveType(models.Model):
    """Bandera configurable para clasificar vacaciones en el monitor."""
    _inherit = 'hr.leave.type'

    l10n_pe_is_vacation = fields.Boolean(
        string='Es vacaciones (Perú)',
        help='El monitor de asistencia clasifica las ausencias de este '
             'tipo como «Vacaciones» (D. Leg. 713); las demás ausencias '
             'validadas se muestran como «Justificada». Sustituye al '
             'código 23 de la Tabla 21 hardcodeado en v18.')


class L10nPeHrAttendanceMonitor(models.Model):
    """Vista SQL (``_auto = False``): una fila por empleado y día.

    Estados: ``ok``/``no_ok``/``descanso``/``feriado``/``vacaciones``/
    ``justificada``/``descansotrab``/``feriadotrab`` — mismas claves
    que en v18 para que el tareaje (Fase 6, otro módulo/archivo) pueda
    consumirlas sin traducción.
    """
    _name = 'l10n_pe.hr.attendance.monitor'
    _description = 'Monitor de asistencia (Perú)'
    _order = 'fecha desc, employee_id, hora_ing'
    _auto = False

    employee_id = fields.Many2one('hr.employee', string='Empleado')
    company_id = fields.Many2one('res.company', string='Compañía')
    work_location_id = fields.Many2one(
        'hr.work.location', string='Establecimiento')
    identification_type_id = fields.Many2one(
        'l10n_latam.identification.type', string='Tipo doc.')
    identification_id = fields.Char(string='N° documento')
    fecha = fields.Date(string='Fecha')
    dia_semana = fields.Selection(
        selection=[
            ('1', 'Lunes'), ('2', 'Martes'), ('3', 'Miércoles'),
            ('4', 'Jueves'), ('5', 'Viernes'), ('6', 'Sábado'),
            ('7', 'Domingo'),
        ],
        string='Día')
    slot_id = fields.Many2one('planning.slot', string='Turno planificado')
    role_id = fields.Many2one('planning.role', string='Tipo de turno')
    cycle_assignment_id = fields.Many2one(
        'l10n_pe.hr.shift.cycle.assignment', string='Ciclo atípico')
    is_day_rest = fields.Boolean(string='Día de descanso')

    hora_ing = fields.Float(string='Ingreso plan.')
    hora_sal = fields.Float(string='Salida plan.')
    duration_asis = fields.Float(string='Duración plan.')
    mar_hora_ing = fields.Float(string='Marc. ingreso')
    mar_hora_sal = fields.Float(string='Marc. salida')
    mar_duration_asis = fields.Float(
        string='Horas marcadas',
        help='Suma de las horas trabajadas del día: con 4 marcaciones '
             'el refrigerio queda descontado automáticamente.')
    marc_count = fields.Integer(string='N° marcaciones')

    state = fields.Selection(
        selection=[
            ('ok', 'Asistió'),
            ('no_ok', 'Falta'),
            ('descanso', 'Día de descanso'),
            ('feriado', 'Día feriado'),
            ('vacaciones', 'Vacaciones'),
            ('justificada', 'Justificada'),
            ('descansotrab', 'Descanso trabajado'),
            ('feriadotrab', 'Feriado trabajado'),
        ],
        string='Estado')
    leave_id = fields.Many2one('hr.leave', string='Registro de ausencia')
    work_entry_type_id = fields.Many2one(
        'hr.work.entry.type', string='Tipo de entrada')

    def _get_monitor_sql(self):
        """SELECT que materializa la vista.

        Dos ramas UNION: (1) una fila por ``planning.slot`` publicado;
        (2) los días de descanso de cada asignación de ciclo atípico
        (que no tienen slot). Marcaciones, ausencias y feriados se
        cuelgan con LATERAL para no duplicar filas. «Asistió» se marca
        desde el check-in (monitoreo en tiempo real: no espera la
        marcación de salida como hacía el v18).
        """
        return """
WITH att AS (
    SELECT ha.employee_id,
           ha.date AS fecha,
           MIN(ha.check_in) AS check_in_utc,
           MAX(ha.check_out) AS check_out_utc,
           COALESCE(SUM(ha.worked_hours), 0) AS worked_hours,
           COUNT(*) AS marc_count
      FROM hr_attendance ha
     GROUP BY ha.employee_id, ha.date
),
base AS (
    -- Rama 1: turnos planificados publicados
    SELECT s.employee_id,
           s.company_id,
           z.tz,
           (s.start_datetime AT TIME ZONE 'UTC' AT TIME ZONE z.tz)::date
               AS fecha,
           s.id AS slot_id,
           s.role_id,
           s.l10n_pe_cycle_assignment_id AS cycle_assignment_id,
           EXTRACT(EPOCH FROM (s.start_datetime AT TIME ZONE 'UTC'
                               AT TIME ZONE z.tz)::time) / 3600.0
               AS hora_ing,
           EXTRACT(EPOCH FROM (s.end_datetime AT TIME ZONE 'UTC'
                               AT TIME ZONE z.tz)::time) / 3600.0
               AS hora_sal,
           EXTRACT(EPOCH FROM (s.end_datetime - s.start_datetime))
               / 3600.0 AS duration_asis,
           FALSE AS is_day_rest
      FROM planning_slot s
      JOIN resource_resource rr ON rr.id = s.resource_id
     CROSS JOIN LATERAL (
           SELECT COALESCE(NULLIF(rr.tz, ''), 'UTC') AS tz) z
     WHERE s.state = 'published'
       AND s.employee_id IS NOT NULL

    UNION ALL

    -- Rama 2: descansos del ciclo atípico (sin slot planificado)
    SELECT a.employee_id,
           a.company_id,
           z.tz,
           d.fecha::date AS fecha,
           NULL::integer AS slot_id,
           NULL::integer AS role_id,
           a.id AS cycle_assignment_id,
           NULL::numeric AS hora_ing,
           NULL::numeric AS hora_sal,
           NULL::numeric AS duration_asis,
           TRUE AS is_day_rest
      FROM l10n_pe_hr_shift_cycle_assignment a
      JOIN l10n_pe_hr_shift_cycle c ON c.id = a.cycle_id
      JOIN hr_employee hea ON hea.id = a.employee_id
      LEFT JOIN resource_resource rra ON rra.id = hea.resource_id
     CROSS JOIN LATERAL (
           SELECT COALESCE(NULLIF(rra.tz, ''), 'UTC') AS tz) z
     CROSS JOIN LATERAL generate_series(
           a.date_start::timestamp, a.date_end::timestamp,
           interval '1 day') AS d(fecha)
     WHERE MOD((d.fecha::date - a.date_start),
               (c.days_work + c.days_rest)) >= c.days_work
       AND NOT EXISTS (
           SELECT 1
             FROM planning_slot s2
             JOIN resource_resource rr2 ON rr2.id = s2.resource_id
            WHERE s2.employee_id = a.employee_id
              AND s2.state = 'published'
              AND (s2.start_datetime AT TIME ZONE 'UTC' AT TIME ZONE
                   COALESCE(NULLIF(rr2.tz, ''), 'UTC'))::date
                  = d.fecha::date)
)
SELECT ROW_NUMBER() OVER (ORDER BY b.employee_id, b.fecha, b.hora_ing)
           AS id,
       b.employee_id,
       b.company_id,
       ver.work_location_id,
       he.l10n_latam_identification_type_id AS identification_type_id,
       ver.identification_id,
       b.fecha,
       EXTRACT(ISODOW FROM b.fecha)::text AS dia_semana,
       b.slot_id,
       b.role_id,
       b.cycle_assignment_id,
       b.is_day_rest,
       COALESCE(b.hora_ing, 0) AS hora_ing,
       COALESCE(b.hora_sal, 0) AS hora_sal,
       COALESCE(b.duration_asis, 0) AS duration_asis,
       CASE WHEN att.check_in_utc IS NOT NULL THEN
            EXTRACT(EPOCH FROM (att.check_in_utc AT TIME ZONE 'UTC'
                                AT TIME ZONE b.tz)::time) / 3600.0
       ELSE 0 END AS mar_hora_ing,
       CASE WHEN att.check_out_utc IS NOT NULL THEN
            EXTRACT(EPOCH FROM (att.check_out_utc AT TIME ZONE 'UTC'
                                AT TIME ZONE b.tz)::time) / 3600.0
       ELSE 0 END AS mar_hora_sal,
       COALESCE(att.worked_hours, 0) AS mar_duration_asis,
       COALESCE(att.marc_count, 0) AS marc_count,
       lv.leave_id,
       lv.work_entry_type_id,
       CASE WHEN att.check_in_utc IS NOT NULL THEN
                CASE WHEN fe.feriado_id IS NOT NULL THEN 'feriadotrab'
                     WHEN b.is_day_rest THEN 'descansotrab'
                     ELSE 'ok' END
            WHEN lv.leave_id IS NOT NULL THEN
                CASE WHEN lv.l10n_pe_is_vacation THEN 'vacaciones'
                     ELSE 'justificada' END
            WHEN fe.feriado_id IS NOT NULL THEN 'feriado'
            WHEN b.is_day_rest THEN 'descanso'
            ELSE 'no_ok' END AS state
  FROM base b
  JOIN hr_employee he ON he.id = b.employee_id
  LEFT JOIN LATERAL (
       -- versión vigente del trabajador (documento y establecimiento
       -- viven en hr.version en v19)
       SELECT v.identification_id, v.work_location_id
         FROM hr_version v
        WHERE v.employee_id = b.employee_id
        ORDER BY v.date_version DESC
        LIMIT 1) ver ON TRUE
  LEFT JOIN att
         ON att.employee_id = b.employee_id AND att.fecha = b.fecha
  LEFT JOIN LATERAL (
       SELECT hl.id AS leave_id,
              hlt.work_entry_type_id,
              hlt.l10n_pe_is_vacation
         FROM hr_leave hl
         JOIN hr_leave_type hlt ON hlt.id = hl.holiday_status_id
        WHERE hl.employee_id = b.employee_id
          AND hl.state = 'validate'
          AND b.fecha BETWEEN hl.request_date_from
                          AND hl.request_date_to
        ORDER BY hl.id
        LIMIT 1) lv ON TRUE
  LEFT JOIN LATERAL (
       -- feriados públicos: entradas globales del calendario (sin
       -- recurso ni calendario), de la compañía o compartidas
       SELECT rcl.id AS feriado_id
         FROM resource_calendar_leaves rcl
        WHERE rcl.resource_id IS NULL
          AND rcl.calendar_id IS NULL
          AND (rcl.company_id IS NULL
               OR rcl.company_id = b.company_id)
          AND b.fecha BETWEEN (rcl.date_from AT TIME ZONE 'UTC'
                               AT TIME ZONE b.tz)::date
                          AND (rcl.date_to AT TIME ZONE 'UTC'
                               AT TIME ZONE b.tz)::date
        ORDER BY rcl.id
        LIMIT 1) fe ON TRUE
"""

    def init(self):
        """Crea/recrea la vista SQL al instalar o actualizar el módulo."""
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            'CREATE OR REPLACE VIEW %s AS (%s)'
            % (self._table, self._get_monitor_sql()))

    def action_set_justificante(self):
        """Abre una ausencia nueva prellenada para justificar la falta."""
        self.ensure_one()
        return {
            'name': self.env._('Registrar ausencia'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.leave',
            'view_mode': 'form',
            'context': {
                'default_employee_id': self.employee_id.id,
                'default_request_date_from': self.fecha,
                'default_request_date_to': self.fecha,
            },
            'target': 'new',
        }

    def action_show_leave(self):
        """Muestra la ausencia que justifica el día."""
        self.ensure_one()
        return {
            'name': self.env._('Registro de ausencia'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.leave',
            'view_mode': 'form',
            'res_id': self.leave_id.id,
            'target': 'new',
        }
