# -*- coding: utf-8 -*-
"""Apertura del Gantt desde el formulario del proyecto y proyectos por
defecto de cada usuario."""
from odoo import _, api, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    def action_open_gantt(self):
        """Abre la client action del Gantt acotada a este proyecto."""
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'al_project_gantt_backend.action_gantt_backend'
        )
        action['name'] = _("Gantt: %s", self.display_name)
        action['context'] = {
            **self.env.context,
            'gantt_project_ids': self.ids,
        }
        return action

    @api.model
    def get_gantt_default_project_ids(self):
        """Proyectos con que abre el Gantt: los que el usuario eligió la
        última vez (los que aún puede ver y siguen activos); si no eligió
        ninguno, el proyecto con la tarea modificada más reciente; si no hay
        tareas, el último proyecto modificado. Nunca todos: con decenas de
        proyectos el diagrama y la barra no se leían."""
        # La preferencia es del propio usuario; se filtra con sus permisos.
        saved = self.search([('id', 'in', self.env.user.al_gantt_project_ids.ids)])
        if saved:
            return saved.ids
        task = self.env['project.task'].search(
            [('project_id', '!=', False), ('project_id.active', '=', True)],
            order='write_date desc, id desc', limit=1)
        if task:
            return task.project_id.ids
        return self.search([], order='write_date desc, id desc', limit=1).ids

    @api.model
    def set_gantt_project_ids(self, project_ids):
        """Guarda los proyectos elegidos en el Gantt como preferencia del
        usuario."""
        projects = self.search([('id', 'in', [int(i) for i in project_ids or []])])
        # sudo: es una preferencia del propio usuario; puede no tener permiso
        # de escribir en su ficha. Solo se guardan proyectos que puede ver.
        user_sudo = self.env.user.sudo()
        user_sudo.al_gantt_project_ids = [(6, 0, projects.ids)]
        return projects.ids
