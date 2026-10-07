# -*- coding: utf-8 -*-
"""Escolaridad de construcción civil: el hijo con estudios técnicos o
superiores genera derecho hasta los 24 años (convenio vigente). Solo se
cambian las compañías que conservan el 21 que traía el módulo."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['res.company'].with_context(active_test=False).search([
        ('l10n_pe_construction_school_age_study', '=', 21),
    ]).write({'l10n_pe_construction_school_age_study': 24})
