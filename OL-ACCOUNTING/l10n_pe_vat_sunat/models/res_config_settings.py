# -*- coding: utf-8 -*-
"""Ajustes globales de la consulta RUC/DNI.

La configuración de las APIs (URLs, tokens, mapeo) vive ahora en el
One2many ``l10n_pe_api_connection_ids`` de la compañía; aquí solo se
exponen los interruptores de activación y un acceso directo a la lista
de conexiones.
"""
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_ruc_validation = fields.Boolean(
        string='Validación de RUC',
        related='company_id.l10n_pe_ruc_validation', readonly=False)
    l10n_pe_dni_validation = fields.Boolean(
        string='Validación de DNI',
        related='company_id.l10n_pe_dni_validation', readonly=False)
    l10n_pe_api_use_fallback = fields.Boolean(
        string='Usar fallback en cascada',
        related='company_id.l10n_pe_api_use_fallback', readonly=False)

    l10n_pe_ruc_lookup_ready = fields.Boolean(
        string='Consulta de RUC lista', compute='_compute_l10n_pe_lookup_status')
    l10n_pe_dni_lookup_ready = fields.Boolean(
        string='Consulta de DNI lista', compute='_compute_l10n_pe_lookup_status')
    l10n_pe_lookup_missing_token = fields.Char(
        string='Conexiones sin token', compute='_compute_l10n_pe_lookup_status')

    @api.depends('company_id')
    def _compute_l10n_pe_lookup_status(self):
        for settings in self:
            company = settings.company_id
            settings.l10n_pe_ruc_lookup_ready = company._l10n_pe_lookup_ready('ruc')
            settings.l10n_pe_dni_lookup_ready = company._l10n_pe_lookup_ready('dni')
            missing = (company._l10n_pe_enabled_connections('ruc')
                       | company._l10n_pe_enabled_connections('dni')).filtered('missing_token')
            settings.l10n_pe_lookup_missing_token = ', '.join(missing.mapped('name'))

    def action_open_pe_api_connections(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Conexiones de consulta RUC/DNI'),
            'res_model': 'l10n_pe.api.connection',
            'view_mode': 'list,form',
            'domain': [('company_id', '=', self.company_id.id)],
            'context': {'default_company_id': self.company_id.id},
        }
