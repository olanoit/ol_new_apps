# -*- coding: utf-8 -*-
"""Asistente de importación de ``hr.salary.rule`` desde Excel (port v18).

Plantilla de columnas (orden técnico esperado en la fila 1):

    1  Categoría          (nombre o código de hr.salary.rule.category)
    2  Compañía           (informativa; las reglas salariales son globales)
    3  Código             (code de la regla)
    4  Nombre             (name de la regla)
    5  Secuencia          (sequence; entero)
    6  Código Python      (amount_python_compute → amount_select = 'code')
    7  Condición Python   (condition_python → condition_select = 'python')

Datos por defecto desde la fila 2 (editable).

``hr.salary.rule`` exige ``struct_id`` (estructura salarial), que no viene
en el Excel: se selecciona una sola estructura destino en el asistente y
se aplica a todas las reglas importadas. La clave funcional para detectar
duplicados es ``code`` + ``struct_id``.

v19: ``hr.salary.rule`` mantiene ``amount_python_compute`` /
``condition_python`` / ``amount_select='code'`` / ``condition_select=
'python'`` (verificado en ``hr_payroll`` v19), así que el port es fiel.
"""
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class AlImportHrSalaryRuleWizard(models.TransientModel):
    _name = 'al.import.hr.salary.rule.wizard'
    _inherit = 'al.import.payroll.mixin'
    _description = 'Importar reglas salariales desde Excel'

    _target_model = 'hr.salary.rule'
    _sheet_keyword = ''  # sin keyword: se autoselecciona la primera hoja

    struct_id = fields.Many2one(
        'hr.payroll.structure',
        string='Estructura salarial destino',
        required=True,
        help='Estructura a la que se asignarán todas las reglas '
             'importadas. El Excel no incluye estructura, por eso se '
             'elige aquí.',
    )

    # --------------------------------------------------------------------- #
    # Mapeo de columnas / plantilla                                          #
    # --------------------------------------------------------------------- #

    def _get_column_map(self):
        return {
            'category': 1,
            'company': 2,
            'code': 3,
            'name': 4,
            'sequence': 5,
            'amount_python': 6,
            'condition_python': 7,
        }

    def _template_headers(self):
        return ['CATEGORÍA (nombre o código)', 'COMPAÑÍA (informativa)',
                'CÓDIGO', 'NOMBRE', 'SECUENCIA', 'CÓDIGO PYTHON',
                'CONDICIÓN PYTHON']

    def _template_example_rows(self):
        return [['Básico', '', 'BAS', 'Sueldo básico', 1,
                 'result = version.wage', 'result = True']]

    def _template_sheet_name(self):
        return 'REGLAS'

    # --------------------------------------------------------------------- #
    # Helpers                                                                #
    # --------------------------------------------------------------------- #

    def _find_category(self, value):
        """Resuelve ``hr.salary.rule.category`` por nombre y luego por
        código."""
        text = ' '.join((str(value) if value not in (None, False) else
                         '').split())
        if not text:
            return self.env['hr.salary.rule.category']
        Category = self.env['hr.salary.rule.category'].sudo()
        cat = Category.search([('name', '=ilike', text)], limit=1)
        if not cat:
            cat = Category.search([('code', '=ilike', text)], limit=1)
        return cat

    @staticmethod
    def _to_int(value, default=5):
        if value in (None, '', False):
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    # --------------------------------------------------------------------- #
    # Procesamiento de una fila                                             #
    # --------------------------------------------------------------------- #

    def _process_row(self, row, line_no, ctx):
        Rule = self.env['hr.salary.rule'].with_company(self.company_id)
        empty = self.env['hr.salary.rule']

        code = self._clean_code(row.get('code'))
        name = self._clean(row.get('name'))
        if not code or not name:
            return 'skipped', self.env._(
                'falta el código o el nombre de la regla'), empty

        category = self._find_category(row.get('category'))
        if not category:
            return 'error', self.env._(
                'categoría "%s" no encontrada (por nombre ni código)'
            ) % (row.get('category'),), empty

        amount_python = self._clean(row.get('amount_python'))
        condition_python = self._clean(row.get('condition_python'))

        vals = {
            'code': code,
            'name': name,
            'sequence': self._to_int(row.get('sequence')),
            'category_id': category.id,
            'struct_id': self.struct_id.id,
            'amount_select': 'code',
        }
        if amount_python:
            vals['amount_python_compute'] = amount_python
        if condition_python:
            vals['condition_select'] = 'python'
            vals['condition_python'] = condition_python

        # Clave funcional: código + estructura. active_test=False para
        # recuperar también reglas archivadas con el mismo código.
        existing = Rule.with_context(active_test=False).search([
            ('code', '=', code),
            ('struct_id', '=', self.struct_id.id),
        ], limit=1)

        if existing:
            if not self.update_existing:
                return 'skipped', self.env._(
                    'la regla "%(c)s" ya existe en la estructura '
                    '(actualización deshabilitada)') % {'c': code}, existing
            existing.write(vals)
            return 'updated', self.env._(
                'actualizada regla "%(c)s" — %(n)s') % {
                'c': code, 'n': name}, existing

        record = Rule.create(vals)
        return 'created', self.env._(
            'creada regla "%(c)s" — %(n)s') % {
            'c': code, 'n': name}, record

    # --------------------------------------------------------------------- #
    # Sugerencias de corrección específicas                                 #
    # --------------------------------------------------------------------- #

    def _suggest_fix(self, status, message, row):
        if status != 'error':
            return ''
        msg = (message or '').lower()
        if 'categoría' in msg or 'categoria' in msg:
            return self.env._(
                'Cree la categoría en Nómina → Configuración → Categorías '
                'de regla salarial, o use el nombre/código exacto en el '
                'Excel.')
        return self.env._(
            'Revise la fila en la plantilla y vuelva a importar.')
