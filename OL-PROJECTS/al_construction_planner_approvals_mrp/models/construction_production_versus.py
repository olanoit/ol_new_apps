# -*- coding: utf-8 -*-
from odoo import fields, models

from odoo.addons.al_construction_planner_approvals.models.construction_approval_route import (
    CHANGE_TYPES)


class ConstructionProductionVersus(models.Model):
    """Presupuestado frente a requerido de la orden, por material (M19-04).
    Se rehace al confirmar y al actualizar la comparación: toda diferencia
    queda registrada aunque no pida aprobación."""
    _name = 'construction.production.versus'
    _description = 'Presupuestado frente a requerido de la orden de fabricación'
    _order = 'production_id, amount_diff desc, id'

    production_id = fields.Many2one(
        'mrp.production', string='Orden de fabricación', required=True, ondelete='cascade',
        index=True)
    company_id = fields.Many2one(related='production_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    product_id = fields.Many2one('product.product', string='Material', required=True)
    uom_id = fields.Many2one('uom.uom', string='Unidad')
    change_type = fields.Selection(
        [item for item in CHANGE_TYPES if item[0] != 'all'], string='Cambio',
        help='Material: no está en el plan. Cantidad: más de lo presupuestado.')
    qty_budget = fields.Float(string='Presupuestado', digits='Product Unit')
    qty_required = fields.Float(string='Requerido', digits='Product Unit')
    qty_diff = fields.Float(string='Diferencia', digits='Product Unit')
    diff_pct = fields.Float(string='Diferencia (%)', digits=(16, 2))
    amount_budget = fields.Monetary(string='Presupuestado (monto)', currency_field='currency_id')
    amount_required = fields.Monetary(string='Requerido (monto)', currency_field='currency_id')
    amount_diff = fields.Monetary(string='Diferencia (monto)', currency_field='currency_id')
