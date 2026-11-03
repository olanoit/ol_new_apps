# -*- coding: utf-8 -*-
"""Borra los apuntes analíticos de los asientos de destino.

Hasta la versión 13 el asiento de destino creaba su propio apunte además del
comprobante de origen, y el centro de costo quedaba cargado dos veces. Solo se
borran esos apuntes: los asientos y sus distribuciones no cambian.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    lines = env['account.analytic.line'].search([
        ('move_line_id.move_id.l10n_pe_is_destiny_entry', '=', True),
    ])
    _logger.info('Asientos de destino: %s apuntes analíticos duplicados borrados', len(lines))
    lines.unlink()
