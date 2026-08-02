# -*- coding: utf-8 -*-
"""Derechohabientes del trabajador (T-Registro, D.S. 015-2010-TR).

El empleador debe registrar en el T-Registro a los familiares que acceden
a las prestaciones de EsSalud por el vínculo con el trabajador: cónyuge o
concubino, hijos menores de edad, hijos mayores incapacitados y la madre
gestante del hijo extramatrimonial. El alta se hace dentro del primer día
del vínculo y la baja al día siguiente de terminado.

Los derechohabientes cumplen aquí dos funciones:

* **acreditación ante EsSalud** — el alta y la baja se exportan para la
  carga masiva del T-Registro, y
* **asignación familiar** (Ley 25129) — el derecho nace de tener hijos
  menores de 18 años, o de hasta 24 que cursen estudios superiores. Antes
  se decidía por el campo nativo ``children`` escrito a mano, que no
  caduca solo: aquí se deriva de los hijos registrados y su edad.

Los códigos SUNAT no se incrustan en el código: viven en catálogos con el
patrón «global con override» del resto de tablas PLAME, y la semántica
que el motor necesita (¿es hijo?, ¿es cónyuge?) se marca con banderas en
el propio catálogo.
"""
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

#: Ley 25129 y D.S. 035-90-TR: hijos menores de 18, o hasta 24 si cursan
#: estudios superiores o universitarios.
FAMILY_ALLOWANCE_AGE = 18
FAMILY_ALLOWANCE_AGE_STUDYING = 24


class L10nPeHrDependentType(models.Model):
    """TABLA 19 — Vínculo familiar."""
    _name = 'l10n_pe.hr.dependent.type'
    _description = 'Vínculo familiar (T19)'
    _inherit = ['l10n_pe.hr.catalog.mixin']

    is_child = fields.Boolean(
        string='Es hijo',
        help='Los hijos son los que dan derecho a la asignación familiar '
             '(Ley 25129), según su edad.')
    is_partner = fields.Boolean(
        string='Es cónyuge o concubino',
        help='Solo puede haber uno vigente por trabajador.')
    is_unborn = fields.Boolean(
        string='Hijo por nacer (gestante)',
        help='La madre gestante se registra antes del nacimiento: no lleva '
             'documento de identidad del hijo ni fecha de nacimiento.')
    requires_disability = fields.Boolean(
        string='Exige resolución de incapacidad',
        help='Los hijos mayores de edad incapacitados acreditan la '
             'condición con la resolución de EsSalud.')


class L10nPeHrDependentEndReason(models.Model):
    """TABLA 20 — Motivo de baja como derechohabiente."""
    _name = 'l10n_pe.hr.dependent.end.reason'
    _description = 'Motivo de baja de derechohabiente (T20)'
    _inherit = ['l10n_pe.hr.catalog.mixin']


class L10nPeHrDependentProof(models.Model):
    """TABLA 27 — Documento que sustenta el vínculo familiar."""
    _name = 'l10n_pe.hr.dependent.proof'
    _description = 'Documento que sustenta el vínculo (T27)'
    _inherit = ['l10n_pe.hr.catalog.mixin']


class L10nPeHrDependent(models.Model):
    _name = 'l10n_pe.hr.dependent'
    _description = 'Derechohabiente'
    _order = 'employee_id, date_start desc, id desc'
    _check_company_auto = True
    _rec_names_search = ['name', 'identification_id']

    # ------------------------------------------------------------------
    # Vínculo
    # ------------------------------------------------------------------
    employee_id = fields.Many2one(
        'hr.employee', string='Trabajador', required=True, index=True,
        ondelete='cascade', check_company=True)
    company_id = fields.Many2one(
        related='employee_id.company_id', store=True, index=True)
    type_id = fields.Many2one(
        'l10n_pe.hr.dependent.type', string='Tipo de derechohabiente',
        required=True, ondelete='restrict')
    is_child = fields.Boolean(related='type_id.is_child')
    is_unborn = fields.Boolean(related='type_id.is_unborn')

    # ------------------------------------------------------------------
    # Identificación
    # ------------------------------------------------------------------
    name = fields.Char(
        string='Nombre completo', compute='_compute_name', store=True,
        help='Apellidos y nombres, en el orden que usa SUNAT.')
    last_name = fields.Char(string='Apellido paterno')
    m_last_name = fields.Char(string='Apellido materno')
    names = fields.Char(string='Nombres')
    l10n_latam_identification_type_id = fields.Many2one(
        'l10n_latam.identification.type', string='Tipo de documento',
        domain="[('country_id.code', '=', 'PE')]")
    identification_id = fields.Char(string='N° de documento')
    country_id = fields.Many2one(
        'res.country', string='País emisor del documento',
        help='Obligatorio para carné de extranjería y pasaporte.')
    birthday = fields.Date(string='Fecha de nacimiento')
    gender = fields.Selection(
        selection=[('male', 'Masculino'), ('female', 'Femenino')],
        string='Sexo')
    age = fields.Integer(string='Edad', compute='_compute_age')

    # ------------------------------------------------------------------
    # Vigencia
    # ------------------------------------------------------------------
    date_start = fields.Date(
        string='Inicio del vínculo', required=True,
        default=fields.Date.context_today,
        help='Fecha desde la que el familiar es derechohabiente. Es la que '
             'se declara como alta en el T-Registro.')
    date_end = fields.Date(
        string='Fin del vínculo',
        help='Fecha en la que termina la condición de derechohabiente. La '
             'baja se declara al día siguiente.')
    end_reason_id = fields.Many2one(
        'l10n_pe.hr.dependent.end.reason', string='Motivo de baja',
        ondelete='restrict')
    active = fields.Boolean(default=True)
    state = fields.Selection(
        selection=[('draft', 'Por declarar'), ('current', 'Vigente'),
                   ('ended', 'De baja')],
        string='Situación', compute='_compute_state', store=True)
    is_declared = fields.Boolean(
        string='Declarado en T-Registro', copy=False,
        help='Marcado cuando el alta se incluyó en una exportación para '
             'SUNAT. Sirve para no volver a declarar lo ya cargado.')

    # ------------------------------------------------------------------
    # Acreditación
    # ------------------------------------------------------------------
    proof_type_id = fields.Many2one(
        'l10n_pe.hr.dependent.proof', string='Tipo de documento que acredita',
        ondelete='restrict',
        help='Tabla 27 de SUNAT. Los tipos 01-03 aplican a la gestante, el '
             '04 al hijo mayor incapacitado, los 05-07 al cónyuge, los '
             '08, 09 y 11 al concubino y el 10 al hijo menor cuyo documento '
             'no sea DNI.')
    proof_document = fields.Char(
        string='N° del documento que acredita',
        help='Número o referencia del acta, partida, escritura o '
             'resolución que sustenta el vínculo.')
    disability_resolution = fields.Char(
        string='Resolución de incapacidad',
        help='Resolución de EsSalud que acredita la incapacidad del hijo '
             'mayor de edad.')
    gestation_due_date = fields.Date(
        string='Fecha probable de parto',
        help='Solo para la madre gestante del hijo por nacer.')
    is_studying = fields.Boolean(
        string='Cursa estudios superiores',
        help='Prolonga la asignación familiar hasta los 24 años '
             '(Ley 25129 y D.S. 035-90-TR).')

    # ------------------------------------------------------------------
    # Asignación familiar
    # ------------------------------------------------------------------
    gives_family_allowance = fields.Boolean(
        string='Da asignación familiar', compute='_compute_family_allowance',
        store=True,
        help='Hijo menor de 18 años, o de hasta 24 que cursa estudios '
             'superiores, con el vínculo vigente.')

    _identification_uniq = models.Constraint(
        'UNIQUE(employee_id, identification_id)',
        'El trabajador ya tiene un derechohabiente con ese documento.')

    # ------------------------------------------------------------------
    # Cálculos
    # ------------------------------------------------------------------
    @api.depends('last_name', 'm_last_name', 'names', 'type_id')
    def _compute_name(self):
        for dependent in self:
            parts = [dependent.last_name, dependent.m_last_name,
                     dependent.names]
            full = ' '.join(part.strip() for part in parts if part)
            dependent.name = full or (dependent.type_id.name or '')

    @api.depends('birthday')
    def _compute_age(self):
        today = fields.Date.context_today(self)
        for dependent in self:
            if dependent.birthday:
                dependent.age = relativedelta(today, dependent.birthday).years
            else:
                dependent.age = 0

    @api.depends('date_start', 'date_end', 'is_declared')
    def _compute_state(self):
        today = fields.Date.context_today(self)
        for dependent in self:
            if dependent.date_end and dependent.date_end < today:
                dependent.state = 'ended'
            elif dependent.is_declared:
                dependent.state = 'current'
            else:
                dependent.state = 'draft'

    @api.depends('type_id.is_child', 'birthday', 'is_studying', 'date_end')
    def _compute_family_allowance(self):
        today = fields.Date.context_today(self)
        for dependent in self:
            dependent.gives_family_allowance = (
                dependent._is_family_allowance_source(today))

    def _is_family_allowance_source(self, on_date):
        """¿Este derechohabiente da derecho a asignación familiar en esa fecha?

        Se evalúa por fecha y no una sola vez porque el derecho **caduca
        solo**: el día que el hijo cumple 18 (o 24 si estudia) deja de
        contar sin que nadie tenga que tocar el registro.
        """
        self.ensure_one()
        if not self.type_id.is_child or not self.birthday:
            return False
        if self.date_start and self.date_start > on_date:
            return False
        if self.date_end and self.date_end < on_date:
            return False
        limit = (FAMILY_ALLOWANCE_AGE_STUDYING if self.is_studying
                 else FAMILY_ALLOWANCE_AGE)
        return relativedelta(on_date, self.birthday).years < limit

    # ------------------------------------------------------------------
    # Validaciones
    # ------------------------------------------------------------------
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for dependent in self:
            if (dependent.date_end and dependent.date_start
                    and dependent.date_end < dependent.date_start):
                raise ValidationError(_(
                    'El fin del vínculo de %(name)s es anterior a su inicio.',
                    name=dependent.display_name))

    @api.constrains('type_id', 'birthday', 'identification_id')
    def _check_identity(self):
        for dependent in self:
            if dependent.type_id.is_unborn:
                # El hijo por nacer aún no tiene documento ni fecha de
                # nacimiento: se registra por la madre gestante.
                continue
            if not dependent.birthday:
                raise ValidationError(_(
                    'Falta la fecha de nacimiento de %(name)s.',
                    name=dependent.display_name))
            if not dependent.identification_id:
                raise ValidationError(_(
                    'Falta el documento de identidad de %(name)s.',
                    name=dependent.display_name))

    @api.constrains('type_id', 'employee_id', 'date_end', 'active')
    def _check_single_partner(self):
        """Un solo cónyuge o concubino vigente por trabajador."""
        for dependent in self:
            if not dependent.type_id.is_partner or dependent.date_end:
                continue
            other = self.search([
                ('employee_id', '=', dependent.employee_id.id),
                ('type_id.is_partner', '=', True),
                ('date_end', '=', False),
                ('id', '!=', dependent.id),
            ], limit=1)
            if other:
                raise ValidationError(_(
                    '%(employee)s ya tiene un cónyuge o concubino vigente '
                    '(%(other)s). Dé de baja el anterior antes de registrar '
                    'uno nuevo.',
                    employee=dependent.employee_id.display_name,
                    other=other.display_name))

    @api.constrains('gestation_due_date', 'type_id')
    def _check_gestation(self):
        for dependent in self:
            if dependent.type_id.is_unborn and not dependent.gestation_due_date:
                raise ValidationError(_(
                    'Indique la fecha probable de parto de %(name)s.',
                    name=dependent.display_name))

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def action_set_end(self):
        """Marca la baja con la fecha de hoy si no se indicó otra."""
        today = fields.Date.context_today(self)
        for dependent in self.filtered(lambda d: not d.date_end):
            dependent.date_end = today
        return True
