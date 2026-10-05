# -*- coding: utf-8 -*-
"""Antes de crear el índice único de colores globales, quita duplicados.

`UNIQUE(state_key, company_id)` no impedía dos filas globales (``company_id``
nulo) para el mismo estado. Si existen, el índice nuevo no se podría crear: se
conserva la más antigua de cada estado.
"""
from odoo.tools import SQL


def migrate(cr, version):
    if not version:
        return
    cr.execute(SQL(
        """
        DELETE FROM al_gantt_state_color color
         USING al_gantt_state_color keep
         WHERE color.company_id IS NULL
           AND keep.company_id IS NULL
           AND keep.state_key = color.state_key
           AND keep.id < color.id
        """
    ))
