# -*- coding: utf-8 -*-
"""Proyectos que cada usuario ve en el Gantt (su última selección)."""
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    al_gantt_project_ids = fields.Many2many(
        'project.project', 'al_gantt_user_project_rel', 'user_id', 'project_id',
        string='Proyectos del Gantt', copy=False,
        help='Los proyectos que el usuario eligió la última vez en el Gantt de proyectos.')
