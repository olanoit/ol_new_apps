# -*- coding: utf-8 -*-
from . import models
from . import wizards


def post_init_hook(env):
    """M117-15: los parámetros iniciales de cada compañía."""
    Parameter = env['construction.sheet.parameter']
    for company in env['res.company'].sudo().search([]):
        Parameter._construction_ensure(company)
