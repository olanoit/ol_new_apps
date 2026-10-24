# -*- coding: utf-8 -*-
"""«Tareas del Gantt» pasa a «Tarea del Gantt» (paquete 1.11, M111-20 E): se
guarda la primera tarea y, si había más, se anota en el historial del
requerimiento. La tabla de la relación anterior se borra."""
from odoo import SUPERUSER_ID, api
from odoo.tools import SQL

TABLE = 'construction_mat_request_gantt_task_rel'


def migrate(cr, version):
    cr.execute(SQL("SELECT to_regclass(%s)", TABLE))
    if not cr.fetchone()[0]:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute(SQL(
        "SELECT request_id, array_agg(task_id ORDER BY task_id) FROM %s GROUP BY request_id",
        SQL.identifier(TABLE)))
    Request = env['construction.material.request']
    Task = env['project.task']
    for request_id, task_ids in cr.fetchall():
        request = Request.browse(request_id).exists()
        if not request:
            continue
        request.construction_gantt_task_id = task_ids[0]
        if len(task_ids) > 1:
            request.message_post(body=env._(
                'Tenía varias tareas del Gantt: queda %(kept)s. Sin tarea en el '
                'requerimiento: %(others)s.',
                kept=Task.browse(task_ids[0]).display_name,
                others=', '.join(Task.browse(task_ids[1:]).mapped('display_name'))))
    cr.execute(SQL("DROP TABLE %s", SQL.identifier(TABLE)))
