# -*- coding: utf-8 -*-
"""Ajustes globales de la consulta RUC/DNI.

La configuración de las APIs (URLs, tokens, mapeo) vive ahora en el
One2many ``l10n_pe_api_connection_ids`` de la compañía; aquí solo se
exponen los interruptores de activación y un acceso directo a la lista
de conexiones.
"""
from odoo import fields, models


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
    l10n_pe_api_connection_ids = fields.One2many(
        related='company_id.l10n_pe_api_connection_ids', readonly=False)

    def action_open_pe_api_connections(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Conexiones de consulta RUC/DNI',
            'res_model': 'l10n_pe.api.connection',
            'view_mode': 'list,form',
            'domain': [('company_id', '=', self.company_id.id)],
            'context': {'default_company_id': self.company_id.id},
        }
