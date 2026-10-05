# -*- coding: utf-8 -*-
"""Asigna las cuentas de diferencia de cambio en las bases ya instaladas.

Sin ellas, la ganancia o pérdida al conciliar una factura en moneda extranjera
con un cobro a otro tipo de cambio no se puede registrar. Ver ``hooks.py``.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    from odoo.addons.al_l10n_pe_currency.hooks import (
        _l10n_pe_assign_exchange_accounts)

    env = api.Environment(cr, SUPERUSER_ID, {})
    _l10n_pe_assign_exchange_accounts(env)
    _logger.info('al_l10n_pe_currency: cuentas de diferencia de cambio revisadas.')
