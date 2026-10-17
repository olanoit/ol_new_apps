# -*- coding: utf-8 -*-
from odoo import fields, models

MARGIN_BASES = [
    ('order', 'Costo total de la orden'),
    ('material', 'Por material'),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_production_margin = fields.Float(
        string='Margen del jefe de producción (%)', digits=(5, 2),
        help='Exceso que el jefe de producción aprueba en la misma orden. Con 0, todo exceso '
             'va a Aprobaciones.')
    construction_production_margin_basis = fields.Selection(
        MARGIN_BASES, string='Base del margen', required=True, default='order',
        help='Costo total de la orden: el exceso en soles sobre lo presupuestado de toda la '
             'orden. Por material: el material con más exceso.')
    construction_production_margin_material = fields.Boolean(
        string='El margen cubre cambios de material',
        help='Sin la marca, un material que no está en el plan va siempre a Aprobaciones.')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_production_margin = fields.Float(
        related='company_id.construction_production_margin', readonly=False)
    construction_production_margin_basis = fields.Selection(
        related='company_id.construction_production_margin_basis', readonly=False)
    construction_production_margin_material = fields.Boolean(
        related='company_id.construction_production_margin_material', readonly=False)
