# -*- coding: utf-8 -*-
"""Vuelca a los parámetros nativos ``l10n_pe_uit`` / ``l10n_pe_rmv`` los
valores cargados a mano en los catálogos anteriores (los de los datos del
módulo ya llegan con el XML)."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Value = env['hr.rule.parameter.value']
    targets = {
        'l10n_pe_hr_uit_bak': ('al_hr_pe.rule_parameter_l10n_pe_uit',
                               "SELECT make_date(year, 1, 1), amount FROM l10n_pe_hr_uit_bak"),
        'l10n_pe_hr_rmv_bak': ('al_hr_pe.rule_parameter_l10n_pe_rmv',
                               "SELECT date_from, amount FROM l10n_pe_hr_rmv_bak"),
    }
    for table, (xmlid, query) in targets.items():
        cr.execute("SELECT to_regclass(%s)", [table])
        if not cr.fetchone()[0]:
            continue
        parameter = env.ref(xmlid)
        existing = set(Value.search([('rule_parameter_id', '=', parameter.id)]).mapped('date_from'))
        cr.execute(query)
        for date_from, amount in cr.fetchall():
            if date_from not in existing:
                Value.create({'rule_parameter_id': parameter.id, 'date_from': date_from,
                              'parameter_value': repr(float(amount))})
        cr.execute(f'DROP TABLE "{table}"')
    # Tablas de los catálogos anteriores (sus modelos ya no existen).
    cr.execute('DROP TABLE IF EXISTS l10n_pe_hr_uit, l10n_pe_hr_rmv')
