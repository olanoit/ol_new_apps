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
import re

from odoo import fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Condición que Odoo deja por defecto al crear una regla salarial: los
# exports de v18 la arrastran en TODAS las filas aunque la regla use
# "Siempre verdadero". Importarla tal cual dejaría casi toda la planilla
# sin calcular, así que se detecta y se descarta.
BOILERPLATE_CONDITION = (
    "result = rules['NET']['total'] > categories['NET'] * 0.10")

# Traducciones v18 → v19 del localdict de las reglas: v19 eliminó
# hr.contract (ahora hr.version), hr.payslip ya no expone ``wage`` y los
# campos peruanos se renombraron con el prefijo ``l10n_pe_`` al migrar.
# Los valores de selección del régimen laboral también cambiaron.
V18_TO_V19 = (
    (re.compile(r'\bpayslip\.wage\b'), 'version.wage',
     'payslip.wage→version.wage'),
    (re.compile(r'\bcontract\b'), 'version', 'contract→version'),
    (re.compile(r'(?<!l10n_pe_)\blabor_regime\b'), 'l10n_pe_labor_regime',
     'labor_regime→l10n_pe_labor_regime'),
    (re.compile(r'(?<!l10n_pe_)\bretirement_fund\b'),
     'l10n_pe_retirement_fund',
     'retirement_fund→l10n_pe_retirement_fund'),
    (re.compile(r"(['\"])practice\1"), r"\1practicante\1",
     "'practice'→'practicante'"),
    (re.compile(r"(['\"])reg_const_civil\1"), r"\1construccion\1",
     "'reg_const_civil'→'construccion'"),
    # Campos peruanos de la boleta y de la versión, renombrados al migrar.
    # El tipo de comisión, además, pasó de la boleta a la versión, y las
    # comisiones fija y mixta se unificaron en un solo campo calculado.
    (re.compile(r'\bpayslip\.commision_type\b'),
     'version.l10n_pe_commission_type',
     'payslip.commision_type→version.l10n_pe_commission_type'),
    (re.compile(r'\bpayslip\.(?:fixed|mixed)_commision\b'),
     'payslip.l10n_pe_commission',
     'payslip.*_commision→payslip.l10n_pe_commission'),
    (re.compile(r'\bpayslip\.prima_insurance\b'),
     'payslip.l10n_pe_prima_insurance',
     'payslip.prima_insurance→payslip.l10n_pe_prima_insurance'),
    (re.compile(r'\bpayslip\.insurable_remuneration\b'),
     'payslip.l10n_pe_insurable_remuneration',
     'payslip.insurable_remuneration→'
     'payslip.l10n_pe_insurable_remuneration'),
    (re.compile(r'\bversion\.exception\b'), 'version.l10n_pe_exception',
     'version.exception→version.l10n_pe_exception'),
    (re.compile(r'\bversion\.is_older\b'), 'version.l10n_pe_is_older',
     'version.is_older→version.l10n_pe_is_older'),
)


class AlImportHrSalaryRuleWizard(models.TransientModel):
    _name = 'al.import.hr.salary.rule.wizard'
    _inherit = 'al.import.payroll.mixin'
    _description = 'Importar reglas salariales desde Excel'

    _target_model = 'hr.salary.rule'
    _sheet_keyword = ''  # sin keyword: se autoselecciona la primera hoja

    # Obligatorio solo en el paso "Configurar" (la vista lo exige ahí): a
    # nivel de modelo bloquearía guardar el asistente en el paso 1, que es
    # cuando se sube el archivo o se descarga la plantilla.
    struct_id = fields.Many2one(
        'hr.payroll.structure',
        string='Estructura salarial destino',
        help='Estructura a la que se asignarán todas las reglas '
             'importadas. El Excel no incluye estructura, por eso se '
             'elige aquí.',
    )

    sanitize_v18 = fields.Boolean(
        string='Adaptar código v18 → v19',
        default=True,
        help='Traduce el código Python exportado de la v18 al dialecto '
             'v19 (contract → version, payslip.wage → version.wage) y '
             'descarta la condición por defecto de Odoo que los exports '
             'de v18 arrastran en todas las filas. Cada adaptación queda '
             'anotada en el registro de la importación.',
    )

    def _validate_config(self):
        super()._validate_config()
        if not self.struct_id:
            raise UserError(self.env._(
                'Seleccione la estructura salarial destino.'))
        return True

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
    def _effective_code(code):
        """Código Python sin comentarios ni líneas en blanco."""
        return '\n'.join(
            line.strip() for line in (code or '').splitlines()
            if line.strip() and not line.strip().startswith('#')).strip()

    @classmethod
    def _is_boilerplate_condition(cls, condition):
        """¿La condición es la que Odoo pone por defecto?"""
        effective = ' '.join(cls._effective_code(condition).split())
        return effective == ' '.join(BOILERPLATE_CONDITION.split())

    @staticmethod
    def _translate_v18(code):
        """Traduce el código al dialecto v19. Devuelve ``(código, notas)``."""
        notes = []
        result = code or ''
        for pattern, replacement, label in V18_TO_V19:
            result, count = pattern.subn(replacement, result)
            if count:
                notes.append('%s ×%d' % (label, count))
        return result, notes

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

        notes = []
        if self.sanitize_v18:
            if condition_python and self._is_boilerplate_condition(
                    condition_python):
                condition_python = ''
                notes.append(self.env._('condición por defecto descartada'))
            amount_python, changes = self._translate_v18(amount_python)
            condition_python, cond_changes = self._translate_v18(
                condition_python)
            changes += cond_changes
            if changes:
                notes.append(self.env._('adaptado v19: %s') % ', '.join(
                    sorted(set(changes))))

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
        else:
            # Explícito: al actualizar una regla existente hay que
            # devolverla a "Siempre verdadero" si el Excel no trae
            # condición (o si era la de por defecto).
            vals['condition_select'] = 'none'

        # Clave funcional: código + estructura. active_test=False para
        # recuperar también reglas archivadas con el mismo código.
        existing = Rule.with_context(active_test=False).search([
            ('code', '=', code),
            ('struct_id', '=', self.struct_id.id),
        ], limit=1)

        suffix = ' [%s]' % '; '.join(notes) if notes else ''

        if existing:
            if not self.update_existing:
                return 'skipped', self.env._(
                    'la regla "%(c)s" ya existe en la estructura '
                    '(actualización deshabilitada)') % {'c': code}, existing
            existing.write(vals)
            return 'updated', self.env._(
                'actualizada regla "%(c)s" — %(n)s') % {
                'c': code, 'n': name} + suffix, existing

        record = Rule.create(vals)
        return 'created', self.env._(
            'creada regla "%(c)s" — %(n)s') % {
            'c': code, 'n': name} + suffix, record

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
