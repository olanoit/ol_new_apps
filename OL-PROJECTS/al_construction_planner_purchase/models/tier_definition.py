# -*- coding: utf-8 -*-
from odoo import fields, models


class TierDefinition(models.Model):
    _inherit = 'tier.definition'

    # Regla «obra sin plan» (paquete 1.16, M116-03): la crea y actualiza la
    # compañía según «Requerimiento de obra sin regla».
    construction_no_plan = fields.Boolean(string='Obra sin plan', readonly=True, copy=False)
