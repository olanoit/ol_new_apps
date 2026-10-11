# -*- coding: utf-8 -*-
"""Migración 19.0.19: ficha RUC completa.

Las conexiones por defecto «SUNAT (oficial)» y «Decolecta» ganan los mapeos
de la ficha RUC (tipo de contribuyente, fechas, sistemas de emisión y de
contabilidad, PLE, padrones). Se agregan solo los que falten, sin tocar los
que el usuario haya configurado.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    companies = env['res.company'].search([])
    for name in ('SUNAT (oficial)', 'Decolecta'):
        companies._l10n_pe_sync_default_mappings(name)
    _logger.info('l10n_pe_vat_sunat: mapeos de la ficha RUC agregados.')
