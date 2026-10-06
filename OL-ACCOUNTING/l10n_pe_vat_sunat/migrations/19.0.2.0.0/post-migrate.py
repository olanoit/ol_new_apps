# -*- coding: utf-8 -*-
"""Migración a la arquitectura config-driven (One2many de conexiones).

Crea las conexiones por defecto en las compañías que no tengan, migrando el
comportamiento previo (proveedores hardcodeados + tokens en
ir.config_parameter) a registros ``l10n_pe.api.connection`` editables. Los
tokens antiguos se transfieren a la conexión correspondiente.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})

    companies = env['res.company'].search([])
    companies._l10n_pe_seed_default_connections()

    # Transferir tokens de ir.config_parameter a las conexiones creadas.
    params = env['ir.config_parameter'].sudo()
    token_map = {
        'apiperu.dev': ('api_peru.url', 'api_peru.token'),
        'apis.net.pe': ('api_net.url', 'api_net.token'),
    }
    for name, (url_key, token_key) in token_map.items():
        url = params.get_param(url_key)
        token = params.get_param(token_key)
        if not (url or token):
            continue
        conns = env['l10n_pe.api.connection'].search([('name', '=', name)])
        for conn in conns:
            vals = {}
            if url:
                vals['base_url'] = url
            if token:
                vals['token'] = token
            conn.write(vals)
    _logger.info('l10n_pe_vat_sunat: conexiones por defecto sembradas y '
                 'tokens migrados.')
