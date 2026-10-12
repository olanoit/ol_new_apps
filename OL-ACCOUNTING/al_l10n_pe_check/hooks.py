# -*- coding: utf-8 -*-
"""Diarios y cuentas de cheques en las compañías que ya tienen el plan
peruano (las nuevas los reciben con la plantilla)."""


def post_init_hook(env):
    env['res.company'].search([('chart_template', '=', 'pe')])._l10n_pe_check_setup()
