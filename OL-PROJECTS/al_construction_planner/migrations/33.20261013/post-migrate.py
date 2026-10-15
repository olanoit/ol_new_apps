# -*- coding: utf-8 -*-
"""v1.7, migración de Allcenter: las compañías que ya usaban el planificador
(con obras o tipologías) quedan con el perfil Mobiliario, y sus obras con él.
Las demás eligen su perfil en Ajustes."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    companies = env['construction.vertical.profile']._assign_legacy_companies()
    _logger.info('Planificador v1.7: perfil Mobiliario para %s',
                 ', '.join(companies.mapped('name')) or '-')
