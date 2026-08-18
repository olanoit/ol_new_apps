# -*- coding: utf-8 -*-
"""Apertura del Gantt desde el formulario del proyecto."""
from odoo import _, models


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
