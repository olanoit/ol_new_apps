# -*- coding: utf-8 -*-
"""Configuración de proveedores de consulta RUC/DNI por compañía.

Las opciones de ``Selection`` se generan desde
``services.providers``; agregar un proveedor nuevo no requiere tocar
este archivo, sólo registrar la clase en ``providers.py``.
"""
from odoo import api, fields, models

from ..services import providers


class ResCompany(models.Model):
    _inherit = "res.company"

    # Activación de validaciones automáticas.
    l10n_pe_ruc_validation = fields.Boolean(
        string='Validación de RUC',
        default=lambda self: (self.country_id.code or '') == 'PE',
    )
    l10n_pe_dni_validation = fields.Boolean(
        string='Validación de DNI',
        default=lambda self: (self.country_id.code or '') == 'PE',
    )

    # Proveedores de API (Strategy pattern — se rellena dinámicamente).
    l10n_pe_api_dni_connection = fields.Selection(
        selection=lambda self: providers.dni_selection(),
        string='Proveedor de DNI',
        default='api_peru',
    )
    l10n_pe_api_ruc_connection = fields.Selection(
        selection=lambda self: providers.ruc_selection(),
        string='Proveedor de RUC',
        default='api_peru',
    )

    # Banderas SUNAT oficial.
    annexed_locals = fields.Boolean(
        string='Importar locales anexos',
        help='Sólo aplica al proveedor "SUNAT (oficial)".',
    )
    legal_representatives = fields.Boolean(
        string='Importar representantes legales',
        help='Sólo aplica al proveedor "SUNAT (oficial)".',
    )

    # Versión de apis.net.pe (v1/v2 — v2 usa /reniec/dni).
    vision_api = fields.Selection(
        selection=[
            ('v1', 'versión 1'),
            ('v2', 'versión 2'),
        ],
        string='Versión API',
        default='v2',
    )

    @api.onchange('country_id')
    def _onchange_country_id_pe_validation(self):
        is_pe = bool(self.country_id and self.country_id.code == 'PE')
        self.l10n_pe_ruc_validation = is_pe
        self.l10n_pe_dni_validation = is_pe
