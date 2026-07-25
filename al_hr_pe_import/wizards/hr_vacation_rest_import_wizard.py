# -*- coding: utf-8 -*-
"""Importación de saldos iniciales del récord vacacional.

Sustituye al módulo v18 ``hr_vacation_import`` (veredicto D: xlrd +
temporales en disco) con una plantilla del framework. Paridad funcional
v18:

* Cada fila crea un movimiento ``internal_motive='rest'`` (saldo
  anterior) en ``hr.vacation.rest`` (de ``al_hr_pe_benefits``); el
  recálculo (`get_vacation_employee`) parte de ese saldo y NUNCA lo
  borra.
* Si el empleado ya tiene saldo inicial, se reemplaza (v18 hacía
  unlink+create); con "Actualizar existentes" desmarcado se omite.
* Motivo automático según el signo de los días: «Saldo Ajuste
  Adelantos» si es negativo, «Saldo acumulado anterior» si no (v18).

Plantilla de columnas:

    1  Fecha de aplicación   (fecha del corte del saldo)
    2  Nro documento         (identification_id del empleado)
    3  Días de saldo         (puede ser negativo y con decimales)
    4  Importe de saldo      (opcional)
"""
import logging
from datetime import date, datetime

from odoo import models

from odoo.addons.al_hr_pe.tools import custom_round

_logger = logging.getLogger(__name__)


class AlImportVacationRestWizard(models.TransientModel):
    _name = 'al.import.vacation.rest.wizard'
    _inherit = 'al.import.payroll.mixin'
    _description = 'Importar saldos de récord vacacional desde Excel'

    _target_model = 'hr.vacation.rest'
    _sheet_keyword = 'vac'

    # --------------------------------------------------------------------- #
    # Mapeo de columnas / plantilla                                          #
    # --------------------------------------------------------------------- #

    def _get_column_map(self):
        return {
            'date_aplication': 1,
            'identification': 2,
            'days': 3,
            'amount': 4,
        }

    def _template_headers(self):
        return ['FECHA DE APLICACIÓN', 'NRO DOCUMENTO', 'DÍAS DE SALDO',
                'IMPORTE DE SALDO']

    def _template_example_rows(self):
        return [['2026-01-01', '46271883', 12.5, 1250.00]]

    def _template_sheet_name(self):
        return 'VACACIONES'

    # --------------------------------------------------------------------- #
    # Helpers                                                                #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _parse_date(value):
        """Celda → ``date``; ``False`` si está vacía, ``None`` si no es
        parseable."""
        if value in (None, '', False):
            return False
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            txt = value.strip()
            if not txt:
                return False
            try:
                return datetime.fromisoformat(txt).date()
            except ValueError:
                return None
        return None

    @staticmethod
    def _to_float(value):
        if value in (None, '', False):
            return None
        try:
            return float(str(value).replace(',', '.'))
        except (TypeError, ValueError):
            return None

    def _find_employee_by_doc(self, identification):
        # ``identification_id`` vive en hr.version; hr.employee lo expone
        # por _inherits sobre la versión vigente.
        return self.env['hr.employee'].sudo().search([
            ('identification_id', '=', identification),
            ('company_id', '=', self.company_id.id),
        ])

    # --------------------------------------------------------------------- #
    # Procesamiento de una fila                                             #
    # --------------------------------------------------------------------- #

    def _process_row(self, row, line_no, ctx):
        Rest = self.env['hr.vacation.rest'].with_company(self.company_id)
        empty = self.env['hr.vacation.rest']

        identification = self._clean_code(row.get('identification'))
        if not identification:
            return 'skipped', self.env._(
                'falta el número de documento'), empty

        date_aplication = self._parse_date(row.get('date_aplication'))
        if date_aplication is False:
            return 'error', self.env._(
                'falta la fecha de aplicación'), empty
        if date_aplication is None:
            return 'error', self.env._(
                'la fecha de aplicación "%s" no es válida'
            ) % (row.get('date_aplication'),), empty

        days = self._to_float(row.get('days'))
        if days is None:
            return 'error', self.env._(
                'los días de saldo "%s" no son numéricos'
            ) % (row.get('days'),), empty

        amount = self._to_float(row.get('amount'))
        amount = custom_round(amount, 2) if amount is not None else 0.0

        employee = self._find_employee_by_doc(identification)
        if not employee:
            return 'error', self.env._(
                'no existe empleado con documento %(d)s en la compañía '
                '"%(c)s"') % {'d': identification,
                              'c': self.company_id.name}, empty
        if len(employee) > 1:
            return 'error', self.env._(
                'hay %(k)d empleados con el documento %(d)s') % {
                'k': len(employee), 'd': identification}, empty

        existing = Rest.search([
            ('employee_id', '=', employee.id),
            ('internal_motive', '=', 'rest'),
            ('company_id', '=', self.company_id.id),
        ])
        if existing and not self.update_existing:
            return 'skipped', self.env._(
                '%(e)s ya tiene saldo inicial (actualización '
                'deshabilitada)') % {'e': employee.name}, existing[:1]
        # Paridad v18: el saldo inicial se reemplaza, no se acumula.
        existing.unlink()

        motive = ('Saldo Ajuste Adelantos' if days < 0
                  else 'Saldo acumulado anterior')
        record = Rest.create({
            'employee_id': employee.id,
            'date_aplication': date_aplication,
            'date_from': date_aplication,
            'date_end': date_aplication,
            'internal_motive': 'rest',
            'motive': motive,
            'days': 0,
            'days_rest': custom_round(days, 2),
            'amount': 0,
            'amount_rest': amount,
            'year': str(date_aplication.year),
            'company_id': self.company_id.id,
        })
        status = 'updated' if existing else 'created'
        return status, self.env._(
            'saldo inicial de %(e)s: %(d)s días / S/ %(a)s') % {
            'e': employee.name, 'd': days, 'a': amount}, record

    # --------------------------------------------------------------------- #
    # Sugerencias de corrección específicas                                 #
    # --------------------------------------------------------------------- #

    def _suggest_fix(self, status, message, row):
        if status != 'error':
            return ''
        msg = (message or '').lower()
        if 'documento' in msg:
            return self.env._(
                'Verifique el número de documento en la versión vigente '
                'del empleado (Empleados → ficha → pestaña RR. HH.).')
        if 'fecha' in msg:
            return self.env._(
                'Use formato de fecha de Excel o texto ISO '
                '(ej. 2026-01-01).')
        return self.env._(
            'Revise la fila en la plantilla y vuelva a importar.')
