# -*- coding: utf-8 -*-
from odoo import fields, models

from .common import stage_selection


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    construction_consumption_stage = fields.Selection(
        stage_selection, string='Etapa de consumo',
        help='Etapa de la obra en la que se consume el componente (columna ETAPA '
             'CONSUMO del maestro). Obligatoria en la BOM de una tipología para '
             'aprobar el plan.')
