# -*- coding: utf-8 -*-
"""Las líneas base guardan ahora el avance en porcentaje.

Antes se copiaba tal cual el ``progress`` de ``hr_timesheet``, que es una
fracción (0.5 = 50 %). Si ese es el campo configurado, las líneas ya
capturadas se pasan a porcentaje para que las nuevas y las viejas digan lo
mismo. Va por SQL porque las líneas son inmutables por ORM (``write`` falla a
propósito).
"""
from odoo import SUPERUSER_ID, api
from odoo.tools import SQL


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    field_map = env['al.gantt.field.map'].get_map()
    factor = env['al.gantt.field.map'].get_progress_factor(field_map)
    if factor == 1.0:
        return
    cr.execute(SQL(
        "UPDATE al_gantt_baseline_line SET progress = progress * %s WHERE progress IS NOT NULL",
        factor,
    ))
