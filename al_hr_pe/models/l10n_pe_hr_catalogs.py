# -*- coding: utf-8 -*-
"""Catálogos PLAME (SUNAT) y entidades de la seguridad social peruana.

Patrón multicompañía «global con override»: los códigos los define la
norma (universales), así que los registros viven con ``company_id`` vacío
y una compañía puede crear su propio override; la regla de seguridad
(security.xml) muestra globales + propios.
"""
from odoo import fields, models


class L10nPeHrCatalogMixin(models.AbstractModel):
    _name = 'l10n_pe.hr.catalog.mixin'
    _description = 'Catálogo SUNAT (mixin)'
    _order = 'code, name'

    code = fields.Char(string='Código')
    description = fields.Char(string='Descripción')
    name = fields.Char(string='Abreviación', required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', index=True,
        help='Vacío: registro global compartido entre compañías. Con '
             'compañía: override propio de esa compañía.')

    _code_company_uniq = models.Constraint(
        'UNIQUE(code, company_id)',
        'Ya existe un registro con ese código (global o en la compañía).')


class HrWorkerType(models.Model):
    """TABLA 08 PLAME — Tipo de trabajador (régimen laboral)."""
    _name = 'hr.worker.type'
    _description = 'Tipo de Trabajador (T08)'
    _inherit = ['l10n_pe.hr.catalog.mixin']


class HrSituation(models.Model):
    """TABLA 15 PLAME — Situación del trabajador."""
    _name = 'hr.situation'
    _description = 'Situación del Trabajador (T15)'
    _inherit = ['l10n_pe.hr.catalog.mixin']


class HrReasonsLeave(models.Model):
    """TABLA 17 PLAME — Motivos de baja."""
    _name = 'hr.reasons.leave'
    _description = 'Motivo de Baja (T17)'
    _inherit = ['l10n_pe.hr.catalog.mixin']


class HrSuspensionType(models.Model):
    """TABLA 21 PLAME — Tipos de suspensión de la relación laboral."""
    _name = 'hr.suspension.type'
    _description = 'Tipo de Suspensión (T21)'
    _inherit = ['l10n_pe.hr.catalog.mixin']


class L10nPeHrRoadType(models.Model):
    """TABLA 5 — Vía (avenida, jirón, calle…)."""
    _name = 'l10n_pe.hr.road.type'
    _description = 'Tipo de vía (T05)'
    _inherit = ['l10n_pe.hr.catalog.mixin']


class L10nPeHrZoneType(models.Model):
    """TABLA 6 — Zona (urbanización, asentamiento humano…)."""
    _name = 'l10n_pe.hr.zone.type'
    _description = 'Tipo de zona (T06)'
    _inherit = ['l10n_pe.hr.catalog.mixin']


class L10nPeHrEducationLevel(models.Model):
    """TABLA 9 — Situación educativa."""
    _name = 'l10n_pe.hr.education.level'
    _description = 'Situación educativa (T09)'
    _inherit = ['l10n_pe.hr.catalog.mixin']


class L10nPeHrContractType(models.Model):
    """TABLA 12 — Tipo de contrato de trabajo / condición laboral."""
    _name = 'l10n_pe.hr.contract.type'
    _description = 'Tipo de contrato (T12)'
    _inherit = ['l10n_pe.hr.catalog.mixin']


class L10nPeHrOccupationalCategory(models.Model):
    """TABLA 24 — Categoría ocupacional del trabajador."""
    _name = 'l10n_pe.hr.occupational.category'
    _description = 'Categoría ocupacional (T24)'
    _inherit = ['l10n_pe.hr.catalog.mixin']

    #: T30 habilita cada ocupación solo para ciertas categorías.
    occupation_field = fields.Selection(
        selection=[('executive', 'Ejecutivo'), ('employee', 'Empleado'),
                   ('worker', 'Obrero')],
        string='Columna en la T30',
        help='Categoría equivalente en la tabla de ocupaciones: filtra las '
             'ocupaciones que SUNAT admite para esta categoría.')


class L10nPeHrOccupation(models.Model):
    """TABLA 30 — Ocupación (sector privado).

    Son ~4 600 códigos: viven en CSV, no en XML, para no inflar el módulo
    ni el ``ir_model_data`` con un registro por ocupación en formato
    verboso.
    """
    _name = 'l10n_pe.hr.occupation'
    _description = 'Ocupación (T30)'
    _inherit = ['l10n_pe.hr.catalog.mixin']

    for_executive = fields.Boolean(string='Ejecutivo')
    for_employee = fields.Boolean(string='Empleado')
    for_worker = fields.Boolean(string='Obrero')

    def _l10n_pe_allowed_for(self, category):
        """¿SUNAT admite esta ocupación para esa categoría ocupacional?

        Las categorías del sector público no tienen columna en la T30, así
        que no restringen nada.
        """
        self.ensure_one()
        field = category.occupation_field
        if not field:
            return True
        return bool(self['for_%s' % field])


class L10nPeHrLaborRegime(models.Model):
    """TABLA 33 — Régimen laboral.

    ``regime_kind`` es el puente con la clasificación funcional que usa el
    motor de beneficios (divisores de CTS, gratificación y vacaciones):
    SUNAT distingue 27 regímenes, pero al cálculo solo le importan cinco
    familias.
    """
    _name = 'l10n_pe.hr.labor.regime'
    _description = 'Régimen laboral (T33)'
    _inherit = ['l10n_pe.hr.catalog.mixin']

    regime_kind = fields.Selection(
        selection=[
            ('general', 'Régimen general'),
            ('small', 'Pequeña empresa'),
            ('micro', 'Microempresa'),
            ('practicante', 'Practicante'),
            ('construccion', 'Construcción civil'),
        ],
        string='Familia de cálculo', default='general', required=True,
        help='Determina los divisores de CTS, gratificación y vacaciones.')


class HrSocialInsurance(models.Model):
    """Seguros sociales (EsSalud, EPS, SCTR) y su tasa."""
    _name = 'hr.social.insurance'
    _description = 'Seguro Social'
    _order = 'name'

    name = fields.Char(string='Seguro', required=True)
    percent = fields.Float(string='%', digits=(12, 2))
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', index=True,
        help='Vacío: registro global. Con compañía: override (p. ej. '
             'SCTR con tasa negociada).')


class HrContributions(models.Model):
    """Aportes/contribuciones de planilla (PLAME)."""
    _name = 'hr.contributions'
    _description = 'Aporte/Contribución'
    _order = 'code, name'

    name = fields.Char(string='Descripción', required=True)
    code = fields.Char(string='Código', required=True)
    type = fields.Selection(
        [('fixed', 'Importe Fijo'), ('percentage', 'Porcentaje')],
        default='percentage', string='Tipo')
    tasa = fields.Float(string='Tasa')
    amount = fields.Float(string='Monto')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', index=True,
        help='Vacío: registro global compartido entre compañías.')
