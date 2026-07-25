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
