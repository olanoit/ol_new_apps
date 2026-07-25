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
        for attendance in self:
            if not attendance.employee_id or not attendance.check_in:
                continue
            check_in = attendance.check_in
            slots = slot_model.search([
                ('employee_id', '=', attendance.employee_id.id),
                ('state', '=', 'published'),
                ('start_datetime', '>=', fields.Datetime.subtract(
                    check_in, hours=_MATCH_WINDOW_HOURS)),
                ('start_datetime', '<=', fields.Datetime.add(
                    check_in, hours=_MATCH_WINDOW_HOURS)),
            ])
            if slots:
                nearest = min(slots, key=lambda slot: abs(
                    slot.start_datetime - check_in))
                attendance.l10n_pe_planning_slot_id = nearest
