# -*- coding: utf-8 -*-
"""Fachada pública del servicio de datos.

Las UIs llaman siempre a ``project.project.get_gantt_data`` (un modelo con ACL
propia y reglas de registro), nunca al ``AbstractModel`` interno.
"""
from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    gantt_task_count = fields.Integer(
        string='Tareas planificadas',
        compute='_compute_gantt_task_count',
        help="Tareas del proyecto que tienen fecha y, por tanto, se pueden "
             "dibujar en el diagrama de Gantt.",
    )

    def _compute_gantt_task_count(self):
        field_map = self.env['al.gantt.field.map'].get_map()
        end_field = field_map['date_end']
        if not end_field:
            self.gantt_task_count = 0
            return
        counts = dict(self.env['project.task']._read_group(
            [('project_id', 'in', self.ids), (end_field, '!=', False)],
            groupby=['project_id'],
            aggregates=['__count'],
        ))
        for project in self:
            project.gantt_task_count = counts.get(project, 0)

    @api.model
    def get_gantt_data(self, project_ids=None, options=None):
        """Punto de entrada RPC de lectura. Ver ``al.gantt.data.get_data``."""
        return self.env['al.gantt.data'].get_data(project_ids=project_ids, options=options)

    @api.model
    def apply_gantt_changes(self, changeset=None):
        """Punto de entrada RPC de escritura. Ver ``al.gantt.data.apply_changes``."""
        return self.env['al.gantt.data'].apply_changes(changeset=changeset)
