# -*- coding: utf-8 -*-
"""Los datos de demostración de los genéricos esenciales vivían en al_industry_pharmacy: en
las bases que ya los tienen, pasan a este módulo (mismo nombre) y no se
duplican al cargar su nueva demo."""
from odoo.tools import SQL

NAMES = ('essential_01', 'essential_02', 'essential_03', 'essential_04', 'essential_05', 'essential_06')


def migrate(cr, version):
    cr.execute(SQL(
        """UPDATE ir_model_data old SET module = %s
            WHERE old.module = 'al_industry_pharmacy' AND old.name IN %s
              AND NOT EXISTS (SELECT 1 FROM ir_model_data new
                               WHERE new.module = %s AND new.name = old.name)""",
        'al_l10n_pe_pharmacy_digemid', tuple(NAMES), 'al_l10n_pe_pharmacy_digemid'))
