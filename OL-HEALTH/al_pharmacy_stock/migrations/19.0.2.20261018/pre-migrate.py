# -*- coding: utf-8 -*-
"""Los datos de demostración de los puntos de control ambiental vivían en al_industry_pharmacy: en
las bases que ya los tienen, pasan a este módulo (mismo nombre) y no se
duplican al cargar su nueva demo."""
from odoo.tools import SQL

NAMES = ('environment_point_room', 'environment_point_fridge')


def migrate(cr, version):
    cr.execute(SQL(
        """UPDATE ir_model_data old SET module = %s
            WHERE old.module = 'al_industry_pharmacy' AND old.name IN %s
              AND NOT EXISTS (SELECT 1 FROM ir_model_data new
                               WHERE new.module = %s AND new.name = old.name)""",
        'al_pharmacy_stock', tuple(NAMES), 'al_pharmacy_stock'))
