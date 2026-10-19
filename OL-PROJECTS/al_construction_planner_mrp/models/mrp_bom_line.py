# -*- coding: utf-8 -*-
from odoo import fields, models

from odoo.addons.al_construction_planner.models.common import stage_selection


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    construction_consumption_stage = fields.Selection(
        stage_selection, string='Etapa de consumo',
        help='Etapa de la obra en la que se consume el componente (columna ETAPA '
             'CONSUMO del maestro). Obligatoria en la BOM de una tipología para '
             'aprobar el plan.')
    construction_intermediate = fields.Boolean(
        string='Producto intermedio', readonly=True,
        help='Lo que entrega la etapa anterior (el paquete de piezas): no se compara con el '
             'plan ni cuenta como cambio de material (paquete 1.10, M110-02).')
