# -*- coding: utf-8 -*-
"""Importación de datos laborales PE sobre la versión vigente del empleado.

Sustituye al importador de "contratos" de ``hr_importers`` v18
(veredicto D): en v19 ``hr.contract`` no existe y los campos PLAME de la
localización viven en ``hr.version`` (núcleo ``al_hr_pe``). Este wizard
actualiza la **versión vigente** (``employee.version_id``) del empleado
localizado por número de documento; las celdas vacías no tocan el valor
actual.

Plantilla de columnas:

    1  Nro documento         (identification_id — localiza al empleado)
    2  Régimen laboral       (clave o etiqueta: general / small / micro /
                              practicante / construccion)
    3  CUSPP                 (afiliados AFP)
    4  Tipo de comisión AFP  (flow / mixed)
    5  Afiliación AFP/ONP    (nombre de hr.membership)
    6  Seguro social         (nombre de hr.social.insurance)
    7  Tipo de trabajador    (código T08 o nombre de hr.worker.type)
    8  Situación             (código T15 o nombre de hr.situation)
    9  Excepción de jornada  (L/U/J/I/P/O — PLAME)
    10 Tipo de labor         (N/C/M/P — PLAME)

TODO(fase8-revisar): confirmar si además de la versión vigente debería
poder importarse sobre una versión histórica concreta (por fecha).
"""
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class AlImportHrVersionWizard(models.TransientModel):
    _name = 'al.import.hr.version.wizard'
    _inherit = 'al.import.payroll.mixin'
    _description = 'Importar datos PE de la versión del empleado'

    _target_model = 'hr.version'
    _sheet_keyword = 'version'

    # --------------------------------------------------------------------- #
    # Mapeo de columnas / plantilla                                          #
    # --------------------------------------------------------------------- #

    def _get_column_map(self):
        return {
            'identification': 1,
            'labor_regime': 2,
            'cuspp': 3,
            'commission_type': 4,
            'membership': 5,
            'social_insurance': 6,
            'worker_type': 7,
            'situation': 8,
            'exception': 9,
            'work_type': 10,
        }

    def _template_headers(self):
        return ['NRO DOCUMENTO', 'RÉGIMEN LABORAL', 'CUSPP',
                'TIPO COMISIÓN AFP', 'AFILIACIÓN (AFP/ONP)',
                'SEGURO SOCIAL', 'TIPO TRABAJADOR (T08)',
                'SITUACIÓN (T15)', 'EXCEPCIÓN JORNADA (PLAME)',
                'TIPO DE LABOR (PLAME)']

    def _template_example_rows(self):
        return [['46271883', 'general', '123456ABCDEF', 'flow',
                 'AFP Integra', 'EsSalud', '21', '11', '', 'N']]

    def _template_sheet_name(self):
        return 'VERSIONES'

    # --------------------------------------------------------------------- #
    # Helpers                                                                #
    # --------------------------------------------------------------------- #

    def _find_employee_by_doc(self, identification):
        return self.env['hr.employee'].sudo().search([
            ('identification_id', '=', identification),
            ('company_id', '=', self.company_id.id),
        ])

    def _parse_selection(self, field_name, value):
        """Acepta la clave técnica o la etiqueta (case-insensitive) de un
        campo Selection de ``hr.version``. ``None`` = no coincide."""
        text = ' '.join((str(value)).split()).lower()
        selection = self.env['hr.version']._fields[field_name].selection
        if callable(selection):
            selection = selection(self.env['hr.version'])
        for key, label in selection:
            if text == key.lower() or text == label.lower():
                return key
        return None

    def _find_by_code_or_name(self, model, value):
        """Catálogos T08/T15: primero por código exacto, luego por
        nombre (patrón global-o-de-la-compañía de al_hr_pe)."""
        text = ' '.join((str(value)).split())
        Model = self.env[model]
        rec = Model.search([('code', '=', text)], limit=1)
        if not rec:
            rec = Model.search([('name', '=ilike', text)], limit=1)
        return rec

    def _find_by_name(self, model, value):
        text = ' '.join((str(value)).split())
        return self.env[model].search([('name', '=ilike', text)], limit=1)

    # --------------------------------------------------------------------- #
    # Procesamiento de una fila                                             #
    # --------------------------------------------------------------------- #

    def _process_row(self, row, line_no, ctx):
        empty = self.env['hr.version']

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

        version = employee.version_id
        if not version:
            return 'error', self.env._(
                'el empleado %(e)s no tiene versión vigente') % {
                'e': employee.name}, empty

        vals = {}

        regime_raw = self._clean(row.get('labor_regime'))
        if regime_raw:
            regime = self._parse_selection(
                'l10n_pe_labor_regime', regime_raw)
            if regime is None:
                return 'error', self.env._(
                    'régimen laboral "%s" no reconocido (use general / '
                    'small / micro / practicante / construccion)'
                ) % regime_raw, empty
            vals['l10n_pe_labor_regime'] = regime

        cuspp = self._clean_code(row.get('cuspp'))
        if cuspp:
            vals['l10n_pe_cuspp'] = cuspp

        commission_raw = self._clean(row.get('commission_type'))
        if commission_raw:
            commission = self._parse_selection(
                'l10n_pe_commission_type', commission_raw)
            if commission is None:
                return 'error', self.env._(
                    'tipo de comisión AFP "%s" no reconocido (use flow / '
                    'mixed)') % commission_raw, empty
            vals['l10n_pe_commission_type'] = commission

        membership_raw = self._clean(row.get('membership'))
        if membership_raw:
            membership = self._find_by_name(
                'hr.membership', membership_raw)
            if not membership:
                return 'error', self.env._(
                    'afiliación "%s" no encontrada (hr.membership)'
                ) % membership_raw, empty
            vals['membership_id'] = membership.id

        insurance_raw = self._clean(row.get('social_insurance'))
        if insurance_raw:
            insurance = self._find_by_name(
                'hr.social.insurance', insurance_raw)
            if not insurance:
                return 'error', self.env._(
                    'seguro social "%s" no encontrado'
                ) % insurance_raw, empty
            vals['social_insurance_id'] = insurance.id

        worker_type_raw = self._clean_code(row.get('worker_type'))
        if worker_type_raw:
            worker_type = self._find_by_code_or_name(
                'hr.worker.type', worker_type_raw)
            if not worker_type:
                return 'error', self.env._(
                    'tipo de trabajador (T08) "%s" no encontrado'
                ) % worker_type_raw, empty
            vals['worker_type_id'] = worker_type.id

        situation_raw = self._clean_code(row.get('situation'))
        if situation_raw:
            situation = self._find_by_code_or_name(
                'hr.situation', situation_raw)
            if not situation:
                return 'error', self.env._(
                    'situación (T15) "%s" no encontrada'
                ) % situation_raw, empty
            vals['situation_id'] = situation.id

        exception_raw = self._clean(row.get('exception'))
        if exception_raw:
            exception = self._parse_selection(
                'l10n_pe_exception', exception_raw)
            if exception is None:
                return 'error', self.env._(
                    'excepción de jornada "%s" no reconocida '
                    '(L/U/J/I/P/O)') % exception_raw, empty
            vals['l10n_pe_exception'] = exception

        work_type_raw = self._clean(row.get('work_type'))
        if work_type_raw:
            work_type = self._parse_selection(
                'l10n_pe_work_type', work_type_raw)
            if work_type is None:
                return 'error', self.env._(
                    'tipo de labor "%s" no reconocido (N/C/M/P)'
                ) % work_type_raw, empty
            vals['l10n_pe_work_type'] = work_type

        if not vals:
            return 'skipped', self.env._(
                'fila sin datos PE que importar para %(e)s') % {
                'e': employee.name}, version

        version.write(vals)
        return 'updated', self.env._(
            'versión de %(e)s actualizada (%(n)d campos)') % {
            'e': employee.name, 'n': len(vals)}, version

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
                'del empleado.')
        if 't08' in msg or 't15' in msg or 'afiliación' in msg \
                or 'afiliacion' in msg or 'seguro' in msg:
            return self.env._(
                'Revise los catálogos en Nómina → Configuración → Perú '
                'y use el código o nombre exacto.')
        return self.env._(
            'Revise la fila en la plantilla y vuelva a importar.')
