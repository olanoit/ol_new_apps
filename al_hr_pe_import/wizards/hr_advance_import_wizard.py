# -*- coding: utf-8 -*-
"""Importación masiva de adelantos (``hr.advance`` de al_hr_pe_benefits).

Plantilla nueva del framework (no existía importador en v18; los
adelantos se cargaban a mano). Cubre el alta inicial y las cargas
mensuales de adelantos de sueldo/gratificación/CTS.

Plantilla de columnas:

    1  Nro documento       (identification_id del empleado)
    2  Tipo de adelanto    (nombre de hr.advance.type de la compañía)
    3  Fecha de adelanto
    4  Fecha de descuento  (determina la boleta en la que se descuenta)
    5  Monto
    6  Observaciones       (opcional)

Clave funcional: empleado + tipo + fecha de descuento (en estado
``not payed``). Los adelantos ya aplicados (``paid out``) nunca se
tocan.

TODO(fase8-revisar): ¿se necesita también plantilla de préstamos
(``hr.loan`` + cronograma ``get_fees()``)? Se dejó fuera para no
duplicar el cronograma generado; confirmar con negocio.
"""
import logging
from datetime import date, datetime

from odoo import models

from odoo.addons.al_hr_pe.tools import custom_round

_logger = logging.getLogger(__name__)


class AlImportHrAdvanceWizard(models.TransientModel):
    _name = 'al.import.hr.advance.wizard'
    _inherit = 'al.import.payroll.mixin'
    _description = 'Importar adelantos desde Excel'

    _target_model = 'hr.advance'
    _sheet_keyword = 'adelanto'

    # --------------------------------------------------------------------- #
    # Mapeo de columnas / plantilla                                          #
    # --------------------------------------------------------------------- #

    def _get_column_map(self):
        return {
            'identification': 1,
            'advance_type': 2,
            'date': 3,
            'discount_date': 4,
            'amount': 5,
            'observations': 6,
        }

    def _template_headers(self):
        return ['NRO DOCUMENTO', 'TIPO DE ADELANTO', 'FECHA DE ADELANTO',
                'FECHA DE DESCUENTO', 'MONTO', 'OBSERVACIONES']

    def _template_example_rows(self):
        return [['46271883', 'Adelanto de sueldo', '2026-07-05',
                 '2026-07-31', 300.00, 'Solicitud del 04/07']]

    def _template_sheet_name(self):
        return 'ADELANTOS'

    # --------------------------------------------------------------------- #
    # Helpers                                                                #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _parse_date(value):
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
        return self.env['hr.employee'].sudo().search([
            ('identification_id', '=', identification),
            ('company_id', '=', self.company_id.id),
        ])

    def _find_advance_type(self, name):
        text = ' '.join((name or '').split())
        if not text:
            return self.env['hr.advance.type']
        return self.env['hr.advance.type'].search([
            ('name', '=ilike', text),
            ('company_id', '=', self.company_id.id),
        ], limit=1)

    # --------------------------------------------------------------------- #
    # Procesamiento de una fila                                             #
    # --------------------------------------------------------------------- #

    def _process_row(self, row, line_no, ctx):
        Advance = self.env['hr.advance'].with_company(self.company_id)
        empty = self.env['hr.advance']

        identification = self._clean_code(row.get('identification'))
        if not identification:
            return 'skipped', self.env._(
                'falta el número de documento'), empty

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

        type_name = self._clean(row.get('advance_type'))
        advance_type = self._find_advance_type(type_name)
        if not advance_type:
            return 'error', self.env._(
                'tipo de adelanto "%s" no encontrado en la compañía'
            ) % (type_name,), empty

        advance_date = self._parse_date(row.get('date'))
        if advance_date is None:
            return 'error', self.env._(
                'la fecha de adelanto "%s" no es válida'
            ) % (row.get('date'),), empty

        discount_date = self._parse_date(row.get('discount_date'))
        if discount_date is False:
            return 'error', self.env._(
                'falta la fecha de descuento'), empty
        if discount_date is None:
            return 'error', self.env._(
                'la fecha de descuento "%s" no es válida'
            ) % (row.get('discount_date'),), empty

        amount = self._to_float(row.get('amount'))
        if amount is None or amount <= 0:
            return 'error', self.env._(
                'el monto "%s" no es un número positivo'
            ) % (row.get('amount'),), empty
        amount = custom_round(amount, 2)

        observations = self._clean(row.get('observations')) or False

        vals = {
            'employee_id': employee.id,
            'advance_type_id': advance_type.id,
            'date': advance_date or discount_date,
            'discount_date': discount_date,
            'amount': amount,
            'observations': observations,
            'name': '%s %s' % (advance_type.name, employee.name),
            'company_id': self.company_id.id,
        }

        # Clave funcional: empleado + tipo + fecha de descuento, solo
        # sobre adelantos aún no aplicados.
        existing = Advance.search([
            ('employee_id', '=', employee.id),
            ('advance_type_id', '=', advance_type.id),
            ('discount_date', '=', discount_date),
            ('state', '=', 'not payed'),
        ], limit=1)

        if existing:
            if not self.update_existing:
                return 'skipped', self.env._(
                    '%(e)s ya tiene un adelanto %(t)s con descuento el '
                    '%(f)s (actualización deshabilitada)') % {
                    'e': employee.name, 't': advance_type.name,
                    'f': discount_date}, existing
            existing.write(vals)
            return 'updated', self.env._(
                'actualizado adelanto de %(e)s: %(t)s S/ %(a)s') % {
                'e': employee.name, 't': advance_type.name,
                'a': amount}, existing

        record = Advance.create(vals)
        return 'created', self.env._(
            'creado adelanto de %(e)s: %(t)s S/ %(a)s (descuento %(f)s)'
        ) % {'e': employee.name, 't': advance_type.name,
             'a': amount, 'f': discount_date}, record

    # --------------------------------------------------------------------- #
    # Sugerencias de corrección específicas                                 #
    # --------------------------------------------------------------------- #

    def _suggest_fix(self, status, message, row):
        if status != 'error':
            return ''
        msg = (message or '').lower()
        if 'tipo de adelanto' in msg:
            return self.env._(
                'Cree el tipo en Nómina → Adelantos y préstamos → Tipos '
                'de adelanto, o use el nombre exacto.')
        if 'documento' in msg:
            return self.env._(
                'Verifique el número de documento en la versión vigente '
                'del empleado.')
        if 'fecha' in msg:
            return self.env._(
                'Use formato de fecha de Excel o texto ISO '
                '(ej. 2026-07-31).')
        return self.env._(
            'Revise la fila en la plantilla y vuelva a importar.')
