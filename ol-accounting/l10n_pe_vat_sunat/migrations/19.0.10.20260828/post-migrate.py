# -*- coding: utf-8 -*-
"""Migración 19.0.10: el método del cron del padrón pasa a ser privado.

``cron_sync_padron`` se renombró a ``_cron_sync_padron`` para que no se
pueda lanzar por RPC. El cron es ``noupdate``: su código se corrige aquí.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    cron = env.ref('l10n_pe_vat_sunat.ir_cron_sync_sunat_padron',
                   raise_if_not_found=False)
    if cron and 'cron_sync_padron' in (cron.code or '') \
            and '_cron_sync_padron' not in cron.code:
        cron.code = cron.code.replace('cron_sync_padron', '_cron_sync_padron')
        _logger.info('l10n_pe_vat_sunat: cron del padrón apunta a '
                     '_cron_sync_padron.')
