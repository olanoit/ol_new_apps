# -*- coding: utf-8 -*-
"""Enlace marcación real → turno planificado.

Único delta real del ``hr_attendance.py`` v18 (125 líneas): al marcar,
buscar la línea de turno planificada más cercana y colgarla de la
asistencia para que el monitor compare planificado vs. real. Se
descarta del v18:

* La selección manual de «tipo de asistencia» en el kiosco
  (``activity_id`` + controlador + parches JS del kiosco): el kiosco
  nativo v19 ya cubre el check in/out y el turno se deduce solo con el
  emparejamiento por cercanía — no hace falta preguntarle al operario.
* ``work_location_id``/``department_id`` duplicados: en v19 el
  establecimiento vive en ``hr.version.work_location_id`` y el slot ya
  expone ``work_location_id`` related.
* El parser del char ``horario`` («HH:MM - HH:MM») con ``- '5 hr'``
  hardcodeado: aquí se comparan datetimes naive-UTC directamente
  (ambos lados se almacenan en UTC), sin aritmética de zona horaria
  manual — corrige el bug TZ señalado en el plan (§5).
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError

# Ventana de búsqueda alrededor del check-in: cubre el turno nocturno
# más largo posible (12 h, STC 4635-2004-AA/TC) con margen de tardanza.
_MATCH_WINDOW_HOURS = 14


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    l10n_pe_planning_slot_id = fields.Many2one(
        'planning.slot', string='Turno planificado',
        index='btree_not_null', ondelete='set null',
        domain="[('employee_id', '=', employee_id)]",
        help='Turno publicado del planning contra el que el monitor de '
             'asistencia compara esta marcación. Se asigna solo al '
             'turno más cercano al check-in; puede corregirse a mano.')
    l10n_pe_analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Centro de costo',
        index='btree_not_null', ondelete='restrict',
        help='Obra o centro de costo donde trabajó ese día. El tareaje lo '
             'copia al detalle diario y la planilla reparte el costo del '
             'trabajador entre sus obras. Vacío: el de la ficha del trabajador.')

    @api.constrains('l10n_pe_analytic_account_id', 'employee_id')
    def _check_l10n_pe_analytic_account_company(self):
        """hr.attendance no tiene compañía (no hay check_company): el centro
        de costo debe ser compartido o de la compañía del trabajador."""
        for attendance in self:
            analytic = attendance.l10n_pe_analytic_account_id
            if analytic.company_id \
                    and analytic.company_id != attendance.employee_id.company_id:
                raise ValidationError(self.env._(
                    'El centro de costo «%(analytic)s» es de %(company)s, no '
                    'de la compañía de %(employee)s.',
                    analytic=analytic.name, company=analytic.company_id.name,
                    employee=attendance.employee_id.name))

    @api.model
    def _l10n_pe_real_work_domain(self):
        """Marcaciones que son trabajo real para el tareaje.

        Odoo 20 guarda en ``hr.attendance`` registros que no son jornada:

        * la asistencia técnica de 00:00:00 a 00:00:01 que el cron de
          ``absence_management`` crea por cada ausente (``in_mode`` =
          ``technical``);
        * las salidas de **déficit** de las reglas de tiempo
          (``threshold_operator`` = ``less_than``), que se colocan en los
          huecos libres del día para contar lo que faltó;
        * las asistencias rechazadas, y las que esperan aprobación cuando
          la compañía exige validarlas (la nómina nativa solo cuenta las
          validadas, ``hr_payroll_attendance``).

        Las salidas de **exceso** y los restos de la fuente sí son tiempo
        trabajado (la regla recorta la fuente y cuelga el exceso contiguo):
        se conservan, y la consolidación «primera entrada / última salida»
        recompone el día. Una marcación abierta (sin salida) en borrador se
        conserva para que el día quede como marcación incompleta y no como
        falta.
        """
        return [
            ('in_mode', '!=', 'technical'),
            '|', ('time_rule_id', '=', False),
            ('time_rule_id.threshold_operator', '!=', 'less_than'),
            '|', ('state', '=', 'validated'),
            '&', ('state', '=', 'draft'), ('check_out', '=', False),
        ]

    @api.model
    def _l10n_pe_day_cost_fields(self):
        """Campos de la marcación que el tareaje copia al día tareado
        (los módulos de obra añaden la obra)."""
        return ['l10n_pe_analytic_account_id']

    @api.model_create_multi
    def create(self, vals_list):
        attendances = super().create(vals_list)
        attendances.filtered(
            lambda att: not att.l10n_pe_planning_slot_id
        )._l10n_pe_match_planning_slot()
        return attendances

    def write(self, vals):
        res = super().write(vals)
        # Reempareja si cambió la marcación de entrada o el empleado,
        # salvo que el usuario haya fijado el turno explícitamente.
        if ('check_in' in vals or 'employee_id' in vals) \
                and 'l10n_pe_planning_slot_id' not in vals:
            self._l10n_pe_match_planning_slot()
        return res

    def _l10n_pe_match_planning_slot(self):
        """Asigna a cada marcación el turno publicado más cercano.

        «Más cercano» = menor |inicio del turno − check-in| dentro de
        una ventana de ±14 h. La comparación se hace entre datetimes
        naive-UTC (los dos campos se guardan así), por lo que es
        correcta en cualquier zona horaria del recurso.
        """
        slot_model = self.env['planning.slot']
        todo = self.filtered(lambda att: att.employee_id and att.check_in)
        if not todo:
            return
        # Una sola consulta para todas las marcaciones (antes, un search
        # por marcación: importar miles era miles de consultas).
        window_start = fields.Datetime.subtract(
            min(todo.mapped('check_in')), hours=_MATCH_WINDOW_HOURS)
        window_end = fields.Datetime.add(
            max(todo.mapped('check_in')), hours=_MATCH_WINDOW_HOURS)
        all_slots = slot_model.search([
            ('employee_ids', 'in', todo.employee_id.ids),
            ('state', '=', '2_published'),
            ('start_datetime', '>=', window_start),
            ('start_datetime', '<=', window_end),
        ])
        # Odoo 20: un turno puede tener varios empleados (employee_ids).
        slots_by_employee = {}
        for slot in all_slots:
            for employee in slot.employee_ids:
                slots_by_employee[employee] = slots_by_employee.get(employee, slot_model) | slot
        for attendance in todo:
            check_in = attendance.check_in
            low = fields.Datetime.subtract(
                check_in, hours=_MATCH_WINDOW_HOURS)
            high = fields.Datetime.add(check_in, hours=_MATCH_WINDOW_HOURS)
            slots = slots_by_employee.get(
                attendance.employee_id, slot_model).filtered(
                lambda slot: low <= slot.start_datetime <= high)
            if slots:
                nearest = min(slots, key=lambda slot: abs(
                    slot.start_datetime - check_in))
                attendance.l10n_pe_planning_slot_id = nearest
