# -*- coding: utf-8 -*-
"""Gratificaciones, CTS y vacaciones creadas sin nombre (fuera del formulario):
reciben el que propone el formulario."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for model in ('hr.gratification', 'hr.cts'):
        Model = env[model].with_context(active_test=False)
        for record in Model.search([('name', 'in', (False, ''))]):
            name = Model._l10n_pe_default_name({'type': record.type, 'year': record.year})
            if name:
                record.name = name
    vacations = env['hr.vacation'].with_context(active_test=False).search(
        [('name', 'in', (False, '')), ('payslip_run_id', '!=', False)])
    for vacation in vacations:
        vacation.name = 'Vacaciones %s' % vacation.payslip_run_id.name
