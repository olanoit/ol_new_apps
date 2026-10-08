# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Lo de negocio de la configuración principal de planillas (un registro
    # por compañía): se edita desde Ajustes ▸ Nómina ▸ Perú. El mapeo de
    # reglas, entradas y tipos de trabajo sigue en su formulario.
    l10n_pe_payroll_sctr_health_entity = fields.Selection(
        related='company_id.l10n_pe_sctr_health_entity', readonly=False)
    l10n_pe_payroll_sctr_health_rate = fields.Float(
        related='company_id.l10n_pe_sctr_health_rate', readonly=False)
    l10n_pe_payroll_sctr_pension_entity = fields.Selection(
        related='company_id.l10n_pe_sctr_pension_entity', readonly=False)
    l10n_pe_payroll_sctr_pension_rate = fields.Float(
        related='company_id.l10n_pe_sctr_pension_rate', readonly=False)
    l10n_pe_payroll_legal_representative_id = fields.Many2one(
        related='company_id.l10n_pe_main_parameter_id.reprentante_legal_id',
        readonly=False)
    l10n_pe_payroll_signature = fields.Binary(
        related='company_id.l10n_pe_main_parameter_id.signature', readonly=False)

    @api.model
    def default_get(self, fields_list):
        # La configuración principal tiene que existir para que los campos
        # relacionados de arriba tengan dónde guardar.
        # Solo si el usuario ve la nómina: los ajustes también se abren al
        # crear un almacén o desde otras apps, sin permisos de planillas.
        if self.env.company.country_id.code == 'PE' \
                and self.env['hr.main.parameter'].has_access('read'):
            self.env['hr.main.parameter'].get_main_parameter(self.env.company)
        return super().default_get(fields_list)

    def action_l10n_pe_open_main_parameter(self):
        return self.env['hr.main.parameter'].action_open_main_parameter()
