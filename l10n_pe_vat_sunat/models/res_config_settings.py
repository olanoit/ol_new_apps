# -*- coding: utf-8 -*-
"""Ajustes globales (espejo de ``res.company`` + parámetros del sistema).

Los tokens de las APIs se exponen aquí como campos puente al
``ir.config_parameter`` para que el administrador no tenga que
navegar a "Parámetros del Sistema" para configurarlos.
"""
from odoo import api, fields, models


# Parámetros expuestos en la UI de Ajustes.
PARAM_KEYS = {
    'api_peru_url':   'api_peru.url',
    'api_peru_token': 'api_peru.token',
    'api_net_url':    'api_net.url',
    'api_net_token':  'api_net.token',
}


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # === Espejo de res.company === #
    l10n_pe_ruc_validation = fields.Boolean(
        string='Validación de RUC',
        related='company_id.l10n_pe_ruc_validation',
        readonly=False,
    )
    l10n_pe_dni_validation = fields.Boolean(
        string='Validación de DNI',
        related='company_id.l10n_pe_dni_validation',
        readonly=False,
    )
    l10n_pe_api_dni_connection = fields.Selection(
        related='company_id.l10n_pe_api_dni_connection',
        readonly=False,
    )
    l10n_pe_api_ruc_connection = fields.Selection(
        related='company_id.l10n_pe_api_ruc_connection',
        readonly=False,
    )
    annexed_locals = fields.Boolean(
        related='company_id.annexed_locals', readonly=False,
    )
    legal_representatives = fields.Boolean(
        related='company_id.legal_representatives', readonly=False,
    )
    vision_api = fields.Selection(
        related='company_id.vision_api', readonly=False,
    )

    # === Tokens (puente a ir.config_parameter) === #
    api_peru_url = fields.Char(string='URL apiperu.dev')
    api_peru_token = fields.Char(string='Token apiperu.dev')
    api_net_url = fields.Char(string='URL apis.net.pe')
    api_net_token = fields.Char(string='Token apis.net.pe')

    # ------------------------------------------------------------------ #
    # Hooks de carga / guardado                                          #
    # ------------------------------------------------------------------ #

    @api.model
    def get_values(self):
        res = super().get_values()
        params = self.env['ir.config_parameter'].sudo()
        res.update({
            fname: params.get_param(key, '')
            for fname, key in PARAM_KEYS.items()
        })
        return res

    def set_values(self):
        super().set_values()
        params = self.env['ir.config_parameter'].sudo()
        for fname, key in PARAM_KEYS.items():
            params.set_param(key, (self[fname] or '').strip())
