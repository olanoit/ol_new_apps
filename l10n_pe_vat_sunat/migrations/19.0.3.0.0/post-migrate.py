# -*- coding: utf-8 -*-
"""Migración 19.0.3.0.0: agrega la conexión por defecto json.pe.

Incorpora la API json.pe (POST con body JSON) a las compañías peruanas que aún
no la tengan, sin tocar las conexiones ya configuradas por el usuario.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['res.company'].search([])._l10n_pe_ensure_connection('json.pe')
    _logger.info('l10n_pe_vat_sunat: conexión json.pe asegurada.')
