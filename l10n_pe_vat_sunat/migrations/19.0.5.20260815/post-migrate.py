# -*- coding: utf-8 -*-
"""Migración 19.0.5.0.0: agrega la conexión por defecto Decolecta.

Incorpora la API de Decolecta (RUC contra SUNAT y DNI contra RENIEC) a las
compañías peruanas que aún no la tengan, sin tocar las conexiones ya
configuradas por el usuario. Queda pendiente que este introduzca su token.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['res.company'].search([])._l10n_pe_ensure_connection('Decolecta')
    _logger.info('l10n_pe_vat_sunat: conexión Decolecta asegurada.')
