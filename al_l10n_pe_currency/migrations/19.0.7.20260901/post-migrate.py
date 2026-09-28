# -*- coding: utf-8 -*-
"""Retira la precisión decimal ``Dual_Currency``, que no usa ningún módulo.

Se cargaba con ``noupdate``, así que quitarla del XML no la borra en las bases
ya instaladas.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    precision = env.ref('al_l10n_pe_currency.decimal_dual_currency',
                        raise_if_not_found=False)
    if precision:
        precision.unlink()
        _logger.info('al_l10n_pe_currency: precisión Dual_Currency retirada.')
