# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Planchas enteras (paquete 1.11, M111-12). Se leen aquí porque el
    # requerimiento de obra y la fabricación del planificador las usan.
    construction_whole_sheet = fields.Boolean(
        string='Pedir tableros en planchas enteras',
        help='Los productos indivisibles se entregan, compran y despachan en planchas '
             'enteras; la fracción queda como necesidad.')
    construction_whole_sheet_tolerance = fields.Float(
        string='Tolerancia de redondeo', digits=(16, 2), default=0.0,
        help='Fracción de plancha que se redondea hacia abajo. 0 = toda fracción sube.')

    @api.constrains('construction_whole_sheet_tolerance')
    def _check_construction_whole_sheet_tolerance(self):
        for company in self:
            if not 0.0 <= company.construction_whole_sheet_tolerance < 1.0:
                raise ValidationError(self.env._(
                    'La tolerancia de redondeo va de 0 a 0.99 plancha.'))
