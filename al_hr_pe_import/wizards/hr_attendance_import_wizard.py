# -*- coding: utf-8 -*-
"""Asistente de importación de ``hr.attendance`` desde Excel (port v18).

Plantilla de columnas (orden técnico esperado en la fila 1):

    1  employee      (nombre del empleado, se resuelve por ``name``)
    2  check_in      (fecha/hora de entrada)
    3  check_out     (fecha/hora de salida, opcional)

Datos por defecto desde la fila 2 (editable).

Las fechas del Excel se interpretan en la zona horaria configurada en el
asistente (por defecto la del usuario) y se convierten a UTC, que es como
``hr.attendance`` almacena ``check_in`` / ``check_out``.
"""
import logging
from datetime import date, datetime

import pytz

from odoo import fields, models

_logger = logging.getLogger(__name__)


def _tz_get(self):
    return [(tz, tz) for tz in sorted(pytz.all_timezones)]


class AlImportHrAttendanceWizard(models.TransientModel):
    _name = 'al.import.hr.attendance.wizard'
    _inherit = 'al.import.payroll.mixin'
    _description = 'Importar asistencias desde Excel'

    _target_model = 'hr.attendance'
    _sheet_keyword = ''  # sin keyword: se autoselecciona la primera hoja

    tz = fields.Selection(
        _tz_get,
        string='Zona horaria del archivo',
        default=lambda self: self.env.user.tz or 'America/Lima',
        required=True,
        help='Zona horaria en la que están expresadas las fechas del '
             'Excel. Se usa para convertir check_in/check_out a UTC.',
    )

    # --------------------------------------------------------------------- #
    # Mapeo de columnas / plantilla                                          #
    # --------------------------------------------------------------------- #

    def _get_column_map(self):
        return {
            'employee': 1,
            'check_in': 2,
            'check_out': 3,
        }

    def _template_headers(self):
        return ['EMPLEADO (nombre exacto)', 'ENTRADA (check_in)',
                'SALIDA (check_out)']

    def _template_example_rows(self):
        return [['GARCIA LOPEZ JUAN CARLOS', '2026-07-01 08:00:00',
                 '2026-07-01 17:00:00']]

    def _template_sheet_name(self):
        return 'ASISTENCIAS'

    # --------------------------------------------------------------------- #
    # Helpers                                                                #
    # --------------------------------------------------------------------- #

    def _import_tz(self):
        """Zona horaria efectiva para interpretar las fechas del Excel."""
        return self.tz or self.env.user.tz or 'America/Lima'

    def _parse_dt(self, value):
        """Convierte una celda de fecha a ``datetime`` naive en UTC.

        openpyxl devuelve ``datetime``/``date`` para celdas con formato de
        fecha; las cadenas se parsean en ISO. Las fechas naive se asumen
        en la zona horaria del asistente y se convierten a UTC.

        Devuelve ``False`` si la celda está vacía y ``None`` si el valor
        no es parseable (marca de error).
        """
        if value in (None, '', False):
            return False
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, date):
            dt = datetime(value.year, value.month, value.day)
        elif isinstance(value, str):
            txt = value.strip()
            if not txt:
                return False
            try:
                dt = datetime.fromisoformat(txt)
            except ValueError:
                return None  # marca de "valor no parseable"
        else:
            return None

        tz = pytz.timezone(self._import_tz())
        if dt.tzinfo is None:
            dt = tz.localize(dt)
        return dt.astimezone(pytz.utc).replace(tzinfo=None)

    def _find_employee(self, name):
        """Busca ``hr.employee`` por nombre dentro de la compañía del
        asistente. Devuelve el recordset (puede tener 0, 1 o varios). El
        multicompañía se respeta filtrando por ``company_id``."""
        normalized = ' '.join((name or '').split())
        if not normalized:
            return self.env['hr.employee']
        return self.env['hr.employee'].sudo().search([
            ('name', '=ilike', normalized),
            ('company_id', '=', self.company_id.id),
        ])

    # --------------------------------------------------------------------- #
    # Procesamiento de una fila                                             #
    # --------------------------------------------------------------------- #

    def _process_row(self, row, line_no, ctx):
        Attendance = self.env['hr.attendance'].with_company(self.company_id)
        empty = self.env['hr.attendance']

        emp_name = self._clean(row.get('employee'))
        if not emp_name:
            return 'skipped', self.env._(
                'falta el nombre del empleado'), empty

        check_in = self._parse_dt(row.get('check_in'))
        if check_in is False:
            return 'error', self.env._(
                'falta la fecha de entrada (check_in)'), empty
        if check_in is None:
            return 'error', self.env._(
                'check_in no es una fecha válida: %s'
            ) % (row.get('check_in'),), empty

        check_out = self._parse_dt(row.get('check_out'))
        if check_out is None:
            return 'error', self.env._(
                'check_out no es una fecha válida: %s'
            ) % (row.get('check_out'),), empty
        check_out = check_out or False

        if check_out and check_out < check_in:
            return 'error', self.env._(
                'la salida (check_out) es anterior a la entrada (check_in)'
            ), empty

        employee = self._find_employee(emp_name)
        if not employee:
            return 'error', self.env._(
                'empleado "%(n)s" no encontrado en la compañía "%(c)s"'
            ) % {'n': emp_name, 'c': self.company_id.name}, empty
        if len(employee) > 1:
            return 'error', self.env._(
                'hay %(k)d empleados que coinciden con "%(n)s"; precise '
                'el nombre') % {'k': len(employee), 'n': emp_name}, empty

        # Clave funcional: empleado + entrada exacta.
        existing = Attendance.search([
            ('employee_id', '=', employee.id),
            ('check_in', '=', check_in),
        ], limit=1)

        if existing:
            if not self.update_existing:
                return 'skipped', self.env._(
                    'ya existe asistencia de "%(n)s" en %(d)s '
                    '(actualización deshabilitada)'
                ) % {'n': emp_name, 'd': check_in}, existing
            existing.write({'check_out': check_out})
            return 'updated', self.env._(
                'actualizada asistencia de "%(n)s" (entrada %(d)s)'
            ) % {'n': emp_name, 'd': check_in}, existing

        record = Attendance.create({
            'employee_id': employee.id,
            'check_in': check_in,
            'check_out': check_out,
        })
        return 'created', self.env._(
            'creada asistencia de "%(n)s" (entrada %(d)s)'
        ) % {'n': emp_name, 'd': check_in}, record

    # --------------------------------------------------------------------- #
    # Sugerencias de corrección específicas de asistencias                  #
    # --------------------------------------------------------------------- #

    def _suggest_fix(self, status, message, row):
        if status != 'error':
            return ''
        msg = (message or '').lower()
        if 'no encontrado' in msg:
            return self.env._(
                'Verifique que el empleado exista con ese nombre exacto en '
                'la compañía seleccionada (Empleados → Empleados).')
        if 'coinciden' in msg:
            return self.env._(
                'Hay empleados homónimos. Use el nombre completo tal como '
                'aparece en Odoo o desactive los duplicados.')
        if 'check_in' in msg or 'entrada' in msg:
            return self.env._(
                'Revise el formato de fecha/hora de la columna check_in '
                '(ej. 2026-07-01 08:00:00).')
        if 'check_out' in msg or 'salida' in msg:
            return self.env._(
                'Revise el formato y que la salida sea posterior a la '
                'entrada.')
        if 'overlap' in msg or 'superpon' in msg or 'no puede tener' in msg:
            return self.env._(
                'El empleado ya tiene una asistencia que se solapa con '
                'este periodo. Ajuste las horas o elimine la asistencia '
                'existente.')
        return self.env._(
            'Revise la fila en la plantilla y vuelva a importar.')
