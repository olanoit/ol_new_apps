# -*- coding: utf-8 -*-

from . import models


def post_init_hook(env):
    """Siembra las conexiones por defecto en las compañías peruanas."""
    companies = env['res.company'].search([])
    companies._l10n_pe_seed_default_connections()
