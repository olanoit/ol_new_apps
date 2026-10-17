# -*- coding: utf-8 -*-
from odoo import api, fields, models

AMOUNT_FIELDS = {'amount_budget', 'amount_required', 'amount_diff', 'amount_consumed'}


class ConstructionProductionVersus(models.Model):
    """Presupuestado, requerido y consumido de la orden (M19-05): lo
    consumido sale de los componentes hechos al cerrar la orden."""
    _name = 'construction.production.versus'
    _inherit = ['construction.production.versus', 'construction.amounts.mixin']

    qty_consumed = fields.Float(string='Consumido', digits='Product Unit')
    amount_consumed = fields.Monetary(string='Consumido (monto)', currency_field='currency_id')

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | AMOUNT_FIELDS
