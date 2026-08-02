# -*- coding: utf-8 -*-
"""Estructuras complementarias del T-Registro: E17, E29 y E30.

Las tres cuelgan del mismo trabajador de la E04/E05 y se envían solo
cuando aplican:

* **E17 — establecimientos** (`.est`): dónde labora. Obligatoria en el
  alta; un trabajador puede estar asignado a varios locales del RUC.
* **E29 — estudios concluidos** (`.edu`): solo si la situación educativa
  es superior completa (T09 11) o universitaria completa (T09 13).
* **E30 — cuenta de abono** (`.cta`): solo si cobra por depósito en
  cuenta (tipo de pago T16 = 2).

Los códigos vienen del Anexo 2: T34 (instituciones educativas y sus
carreras) y T36 (entidades del sistema financiero).
"""
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

#: T09: únicas situaciones educativas que admiten estudios concluidos.
HIGHER_EDUCATION_CODES = ('11', '13')
#: Largos de cuenta admitidos por entidad (manual del PVS, E30 campo 5).
ACCOUNT_LENGTHS = {
    '002': (13, 14, 20),   # Banco de Crédito del Perú
    '011': (18, 20),       # BBVA
    '003': (13, 20),       # Interbank
    '009': (10, 14, 20),   # Scotiabank
    '018': (11, 20),       # Banco de la Nación
    '038': (12, 20),       # BanBif
    '020': (13, 20),       # Banco Falabella
}
#: Entidades cuyo número de 20 dígitos es un CCI que empieza por su código.
CCI_ENTITIES = ('002', '003', '007', '009', '011', '018', '023', '035',
                '038', '043', '053', '056', '802', '803', '805')


class L10nPeHrEducationInstitution(models.Model):
    """TABLA 34 — Institución educativa."""
    _name = 'l10n_pe.hr.education.institution'
    _description = 'Institución educativa (T34)'
    _inherit = ['l10n_pe.hr.catalog.mixin']


class L10nPeHrEducationCareer(models.Model):
    """TABLA 34 — Carrera de una institución educativa."""
    _name = 'l10n_pe.hr.education.career'
    _description = 'Carrera (T34)'
    _inherit = ['l10n_pe.hr.catalog.mixin']

    _code_company_uniq = models.Constraint(
        'UNIQUE(code, company_id, institution_id)',
        'Esa carrera ya existe en la institución.')

    institution_id = fields.Many2one(
        'l10n_pe.hr.education.institution', string='Institución',
        ondelete='cascade', index=True)


class L10nPeHrFinancialEntity(models.Model):
    """TABLA 36 — Entidad del sistema financiero."""
    _name = 'l10n_pe.hr.financial.entity'
    _description = 'Entidad financiera (T36)'
    _inherit = ['l10n_pe.hr.catalog.mixin']


class ResBank(models.Model):
    _inherit = 'res.bank'

    l10n_pe_financial_entity_id = fields.Many2one(
        'l10n_pe.hr.financial.entity', string='Entidad SUNAT (T36)',
        help='Código de la entidad en la tabla 36 del Anexo 2, que es el '
             'que viaja en la estructura 30 del T-Registro.')


class HrWorkLocation(models.Model):
    _inherit = 'hr.work.location'

    l10n_pe_establishment_code = fields.Char(
        string='Código de establecimiento (SUNAT)', size=4,
        help='Código de 4 dígitos con el que el local está inscrito en el '
             'RUC del empleador (p. ej. 0001 para el domicilio fiscal).')

    @api.constrains('l10n_pe_establishment_code')
    def _check_l10n_pe_establishment_code(self):
        for location in self.filtered('l10n_pe_establishment_code'):
            code = location.l10n_pe_establishment_code.strip()
            if not (code.isdigit() and len(code) == 4):
                raise ValidationError(_(
                    'El código de establecimiento de %(name)s debe tener 4 '
                    'dígitos.', name=location.display_name))


class L10nPeHrEmployeeEducation(models.Model):
    """Estudios concluidos del trabajador (estructura 29)."""
    _name = 'l10n_pe.hr.employee.education'
    _description = 'Estudios concluidos (T-Registro E29)'
    _order = 'employee_id, graduation_year desc'
    _check_company_auto = True

    employee_id = fields.Many2one(
        'hr.employee', string='Trabajador', required=True, index=True,
        ondelete='cascade', check_company=True)
    company_id = fields.Many2one(
        related='employee_id.company_id', store=True, index=True)
    education_level_id = fields.Many2one(
        'l10n_pe.hr.education.level', string='Formación superior completa',
        required=True,
        domain=[('code', 'in', HIGHER_EDUCATION_CODES)],
        help='SUNAT solo admite aquí la situación educativa 11 (superior '
             'completa) o 13 (universitaria completa).')
    in_peru = fields.Boolean(
        string='Estudió en una institución del Perú', default=True,
        help='Si no, los datos de institución, carrera y año van vacíos '
             'en el archivo.')
    institution_id = fields.Many2one(
        'l10n_pe.hr.education.institution', string='Institución educativa')
    career_id = fields.Many2one(
        'l10n_pe.hr.education.career', string='Carrera',
        domain="[('institution_id', '=?', institution_id)]")
    graduation_year = fields.Integer(string='Año de egreso')

    @api.constrains('education_level_id')
    def _check_education_level(self):
        for record in self:
            if record.education_level_id.code not in HIGHER_EDUCATION_CODES:
                raise ValidationError(_(
                    'Los estudios concluidos solo se declaran con situación '
                    'educativa 11 o 13; %(level)s no aplica.',
                    level=record.education_level_id.display_name))

    @api.constrains('in_peru', 'institution_id', 'career_id',
                    'graduation_year')
    def _check_peruvian_studies(self):
        current_year = fields.Date.context_today(self).year
        for record in self.filtered('in_peru'):
            if not (record.institution_id and record.career_id):
                raise ValidationError(_(
                    'Indique la institución y la carrera de los estudios de '
                    '%(name)s.', name=record.employee_id.display_name))
            if not 1950 <= record.graduation_year <= current_year:
                raise ValidationError(_(
                    'El año de egreso debe estar entre 1950 y %(year)s.',
                    year=current_year))

    @api.constrains('institution_id', 'career_id')
    def _check_career_institution(self):
        """La carrera tiene que ser de la institución declarada.

        Va como constraint y no solo como onchange: el formulario no es el
        único camino, y una importación con la pareja cruzada la rechaza
        SUNAT (errores ETR23.3 / ETR23.4).
        """
        for record in self.filtered(lambda r: r.career_id and r.institution_id):
            if record.career_id.institution_id != record.institution_id:
                raise ValidationError(_(
                    'La carrera %(career)s no pertenece a %(institution)s.',
                    career=record.career_id.display_name,
                    institution=record.institution_id.display_name))

    @api.onchange('institution_id')
    def _onchange_institution_id(self):
        for record in self:
            if (record.career_id
                    and record.career_id.institution_id != record.institution_id):
                record.career_id = False


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    l10n_pe_extra_work_location_ids = fields.Many2many(
        'hr.work.location', string='Otros establecimientos',
        help='Locales adicionales del RUC donde también labora. El del '
             'campo «Lugar de trabajo» se declara siempre.')
    l10n_pe_education_ids = fields.One2many(
        'l10n_pe.hr.employee.education', 'employee_id',
        string='Estudios concluidos')

    def _l10n_pe_establishments(self):
        """Locales a declarar en la E17, sin repetir."""
        self.ensure_one()
        locations = self.work_location_id | self.l10n_pe_extra_work_location_ids
        return locations.filtered('l10n_pe_establishment_code')

    # ------------------------------------------------------------------
    # Estructuras
    # ------------------------------------------------------------------
    def _l10n_pe_e17_rows(self):
        """Estructura 17 — establecimientos donde labora (5 campos)."""
        self.ensure_one()
        doc_type, doc_number, country = self._l10n_pe_doc_pair()
        ruc = (self.company_id.vat or '').strip()
        return [[doc_type, doc_number, country, ruc,
                 location.l10n_pe_establishment_code]
                for location in self._l10n_pe_establishments()]

    def _l10n_pe_e29_rows(self):
        """Estructura 29 — estudios concluidos (8 campos).

        Con el indicador «estudió en el Perú» en 0, SUNAT exige que los
        tres campos siguientes vayan vacíos.
        """
        self.ensure_one()
        doc_type, doc_number, country = self._l10n_pe_doc_pair()
        rows = []
        for study in self.l10n_pe_education_ids:
            head = [doc_type, doc_number, country,
                    study.education_level_id.code or '']
            if study.in_peru:
                rows.append(head + ['1', study.institution_id.code or '',
                                    study.career_id.code or '',
                                    str(study.graduation_year or '')])
            else:
                rows.append(head + ['0', '', '', ''])
        return rows

    def _l10n_pe_e30_rows(self):
        """Estructura 30 — cuenta de abono de remuneraciones (5 campos)."""
        self.ensure_one()
        account = self.sudo().primary_bank_account_id
        if not account:
            return []
        doc_type, doc_number, country = self._l10n_pe_doc_pair()
        entity = account.bank_id.l10n_pe_financial_entity_id
        number = re.sub(r'\D', '', account.acc_number or '')
        return [[doc_type, doc_number, country, entity.code or '', number]]

    # ------------------------------------------------------------------
    # Validaciones propias de estas estructuras
    # ------------------------------------------------------------------
    def _l10n_pe_bank_account_issues(self):
        """Las reglas de la E30 campo 5, que son las que rechaza SUNAT."""
        self.ensure_one()
        issues = []
        account = self.sudo().primary_bank_account_id
        if not account:
            return [_('%s: sin cuenta de abono.', self.display_name)]
        entity = account.bank_id.l10n_pe_financial_entity_id
        number = re.sub(r'\D', '', account.acc_number or '')
        name = self.display_name
        if not entity:
            issues.append(_(
                '%(name)s: el banco %(bank)s no tiene código de la tabla 36.',
                name=name, bank=account.bank_id.display_name or '—'))
        if not 6 <= len(number) <= 20:
            issues.append(_('%s: la cuenta debe tener entre 6 y 20 dígitos.',
                            name))
            return issues
        if len(set(number)) == 1:
            issues.append(_('%s: la cuenta no puede ser un dígito repetido.',
                            name))
        if self.identification_id and self.identification_id in number:
            issues.append(_(
                '%s: la cuenta no puede contener el documento de identidad.',
                name))
        allowed = ACCOUNT_LENGTHS.get(entity.code)
        if allowed and len(number) not in allowed:
            issues.append(_(
                '%(name)s: %(bank)s admite cuentas de %(lengths)s dígitos, '
                'no de %(actual)s.', name=name,
                bank=account.bank_id.display_name,
                lengths=' o '.join(str(n) for n in allowed),
                actual=len(number)))
        if (len(number) == 20 and entity.code in CCI_ENTITIES
                and not number.startswith(entity.code)):
            issues.append(_(
                '%(name)s: el CCI de 20 dígitos debe empezar por el código '
                'de la entidad (%(code)s).', name=name, code=entity.code))
        return issues
