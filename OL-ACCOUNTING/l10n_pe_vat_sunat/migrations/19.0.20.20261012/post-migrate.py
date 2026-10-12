# -*- coding: utf-8 -*-
"""La unicidad de ciudades pasa a una validación solo para Perú: se elimina
la restricción SQL anterior, que abarcaba las ciudades de todos los países."""
from odoo.tools import SQL


def migrate(cr, version):
    cr.execute(SQL('ALTER TABLE res_city DROP CONSTRAINT IF EXISTS %s',
                   SQL.identifier('res_city_unique_city_id')))
    cr.execute(SQL(
        "DELETE FROM ir_model_constraint WHERE name = %s AND type = 'u'",
        'res_city_unique_city_id'))
