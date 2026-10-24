# -*- coding: utf-8 -*-
"""La vista del recuadro guardada en la base cita «Tareas del Gantt», que ya
no existe: la vista del control de plan, que se carga antes, no validaría.
Se cambia el nombre del campo en la vista guardada; el XML la reescribe
después."""
from odoo.tools import SQL


def migrate(cr, version):
    cr.execute(SQL("""
        UPDATE ir_ui_view v
           SET arch_db = replace(v.arch_db::text, 'construction_gantt_task_ids',
                                 'construction_gantt_task_id')::jsonb
          FROM ir_model_data d
         WHERE d.model = 'ir.ui.view' AND d.res_id = v.id
           AND d.module = 'al_construction_planner_purchase'
           AND d.name = 'construction_material_request_view_form_scope'
    """))
