# -*- coding: utf-8 -*-
"""Programa por piso de la hoja guardado en la obra (paquete 1.18, M118-06,
decisión D2): el servidor no evalúa la hoja, así que el envío deja aquí el
inicio, el ritmo, los días por sub etapa y el orden de PROGRAMA, y «Generar
plan» los propone."""
from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    construction_program_start = fields.Date(string='Inicio del programa', copy=False)
    construction_program_pace = fields.Float(string='Pisos por semana del programa', copy=False)
    construction_program_days = fields.Integer(string='Días por sub etapa del programa',
                                               copy=False)
    construction_program_order = fields.Selection(
        [('asc', 'Del primero al último'), ('desc', 'Del último al primero')],
        string='Orden de los pisos del programa', copy=False)
    construction_program_source = fields.Char(string='Programa tomado de', copy=False)
    construction_program_date = fields.Datetime(string='Programa enviado el', copy=False)
