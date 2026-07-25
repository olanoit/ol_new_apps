# -*- coding: utf-8 -*-
"""Importación de inputs (novedades) sobre las boletas de un lote.

Decisión de migración: el wizard v18 de "reglas salariales" importaba
*definiciones* de reglas (eso se mantiene en
``al.import.hr.salary.rule.wizard``); lo que faltaba operativamente era
volcar *importes* mensuales a las boletas. En v19 eso son líneas
``hr.payslip.input`` (que ya no se autogeneran), así que este wizard
escribe con el helper ``hr.payslip._set_pe_input_amount`` de
``al_hr_pe_benefits`` (mismo camino que adelantos/préstamos/subsidios).

Plantilla de columnas:

    1  Nro documento     (identification_id del empleado / su versión)
    2  Código de input   (code de hr.payslip.input.type)
    3  Monto             (redondeado con custom_round, criterio SUNAT)

El asistente pide el lote (``hr.payslip.run``): cada fila se aplica a la
boleta del empleado dentro del lote. Clave funcional: boleta + input
(el helper actualiza el importe si la línea ya existe).
"""
import logging

from odoo import fields, models

from odoo.addons.al_hr_pe.tools import custom_round

_logger = logging.getLogger(__name__)


class AlImportPayslipInputWizard(models.TransientModel):
    _name = 'al.import.payslip.input.wizard'
    _inherit = 'al.import.payroll.mixin'
    _description = 'Importar inputs de boletas desde Excel'
    _check_company_auto = True

    _target_model = 'hr.payslip'
    _sheet_keyword = 'input'

    payslip_run_id = fields.Many2one(
        'hr.payslip.run',
        string='Lote de boletas',
        required=True,
        check_company=True,
        domain="[('company_id', '=', company_id)]",
        help='Lote destino: cada fila del Excel se aplica a la boleta '
             'del empleado dentro de este lote.',
    )

    # --------------------------------------------------------------------- #
    # Mapeo de columnas / plantilla                                          #
    # --------------------------------------------------------------------- #

    def _get_column_map(self):
        return {
            'identification': 1,
            'input_code': 2,
            'amount': 3,
        }

    def _template_headers(self):
        return ['NRO DOCUMENTO', 'CÓDIGO DE INPUT', 'MONTO']

    def _template_example_rows(self):
        return [['46271883', 'HEX25', 150.50]]

    def _template_sheet_name(self):
        return 'INPUTS'

    # --------------------------------------------------------------------- #
    # Helpers                                                                #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _to_float(value):
        """``None`` si no es numérico; float en caso contrario."""
        if value in (None, '', False):
            return None
        try:
            return float(str(value).replace(',', '.'))
        except (TypeError, ValueError):
            return None

    def _find_slip(self, identification):
        """Boleta del lote cuyo empleado tiene ese documento."""
        return self.payslip_run_id.slip_ids.filtered(
            lambda s: (s.employee_id.identification_id or '').strip()
            == identification)

    # --------------------------------------------------------------------- #
    # Procesamiento de una fila                                             #
    # --------------------------------------------------------------------- #

    def _process_row(self, row, line_no, ctx):
        empty = self.env['hr.payslip']

        identification = self._clean_code(row.get('identification'))
        if not identification:
            return 'skipped', self.env._(
                'falta el número de documento'), empty

        input_code = self._clean_code(row.get('input_code'))
        if not input_code:
            return 'error', self.env._(
                'falta el código de input'), empty

        amount = self._to_float(row.get('amount'))
        if amount is None:
            return 'error', self.env._(
                'el monto "%s" no es numérico') % (row.get('amount'),), empty
        amount = custom_round(amount, 2)

        slips = self._find_slip(identification)
        if not slips:
            return 'error', self.env._(
                'no hay boleta en el lote "%(l)s" para el documento '
                '%(d)s') % {'l': self.payslip_run_id.name,
                            'd': identification}, empty
        if len(slips) > 1:
            return 'error', self.env._(
                'hay %(k)d boletas en el lote para el documento %(d)s'
            ) % {'k': len(slips), 'd': identification}, empty
        slip = slips
        if slip.state not in ('draft', 'verify'):
            return 'error', self.env._(
                'la boleta de %(e)s no está en borrador (estado: %(s)s)'
            ) % {'e': slip.employee_id.name, 's': slip.state}, empty

        input_type = self.env['hr.payslip.input.type'].search([
            ('code', '=', input_code),
        ], limit=1)
        if not input_type:
            return 'error', self.env._(
                'no existe un tipo de input con código "%s"'
            ) % input_code, empty
        if slip.struct_id and input_type not in \
                slip.struct_id.input_line_type_ids:
            return 'error', self.env._(
                'el input "%(i)s" no está permitido en la estructura '
                '"%(s)s"') % {'i': input_code,
                              's': slip.struct_id.name}, empty

        existed = bool(slip.input_line_ids.filtered(
            lambda line: line.input_type_id == input_type))
        if existed and not self.update_existing:
            return 'skipped', self.env._(
                'la boleta de %(e)s ya tiene el input %(i)s '
                '(actualización deshabilitada)') % {
                'e': slip.employee_id.name, 'i': input_code}, slip

        # Helper compartido de la suite (crea o actualiza la línea).
        slip._set_pe_input_amount(input_type, amount)

        status = 'updated' if existed else 'created'
        return status, self.env._(
            'input %(i)s = %(a)s en la boleta de %(e)s') % {
            'i': input_code, 'a': amount,
            'e': slip.employee_id.name}, slip

    # --------------------------------------------------------------------- #
    # Sugerencias de corrección específicas                                 #
    # --------------------------------------------------------------------- #

    def _suggest_fix(self, status, message, row):
        if status != 'error':
            return ''
        msg = (message or '').lower()
        if 'documento' in msg and 'boleta' in msg:
            return self.env._(
                'Verifique que el empleado tenga boleta en el lote y que '
                'su documento coincida con el de su versión vigente.')
        if 'tipo de input' in msg or 'código de input' in msg:
            return self.env._(
                'Revise el código en Nómina → Configuración → Tipos de '
                'entrada de boleta.')
        if 'estructura' in msg:
            return self.env._(
                'Añada el tipo de input a los "Otros inputs" de la '
                'estructura salarial de la boleta.')
        if 'borrador' in msg:
            return self.env._(
                'Solo se importan inputs sobre boletas en borrador o por '
                'verificar.')
        return self.env._(
            'Revise la fila en la plantilla y vuelva a importar.')
