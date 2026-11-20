# -*- coding: utf-8 -*-
"""Paquete 1.24, M124-04: el formulario del requerimiento de obra ya no tiene
pestañas. La vista del alcance guardada en la base todavía se ancla en
``//notebook``, y al actualizar se valida con el formulario nuevo antes de que
se cargue su archivo: se le cambia el ancla aquí para que la actualización no
se detenga."""
from odoo.tools import SQL


def migrate(cr, version):
    cr.execute(SQL(
        """
        UPDATE ir_ui_view view
           SET arch_db = replace(view.arch_db::text, %(old)s, %(new)s)::jsonb
          FROM ir_model_data data
         WHERE data.model = 'ir.ui.view'
           AND data.res_id = view.id
           AND data.module = 'al_construction_planner_purchase'
           AND data.name = 'construction_material_request_view_form_scope'
           AND view.arch_db::text LIKE %(like)s
        """,
        old='//notebook', new="//separator[@name='lines']", like='%//notebook%'))
