# -*- coding: utf-8 -*-
"""Presupuestado frente a real de fabricación en el planificador (M19-05).

Una fila por orden, nivel del plan (el módulo o el ambiente de la línea),
etapa y material. Lo presupuestado sale de esas líneas del plan; lo
requerido y lo consumido de la orden se reparten entre sus niveles en
proporción a lo presupuestado (en partes iguales si el material no está en
el plan). Así el piso suma lo mismo que sus órdenes."""
from odoo import api, fields, models

from odoo.addons.al_construction_planner.models.common import stage_selection

AMOUNT_FIELDS = {'amount_budget', 'amount_required', 'amount_consumed', 'amount_diff'}


class ConstructionProductionAnalysis(models.Model):
    _name = 'construction.production.analysis'
    _inherit = ['construction.amounts.mixin']
    _description = 'Presupuestado frente a real de fabricación'
    _order = 'project_id, floor_task_id, space_task_id, task_id, stage, product_id'

    production_id = fields.Many2one(
        'mrp.production', string='Orden de fabricación', required=True, ondelete='cascade',
        index=True)
    company_id = fields.Many2one(related='production_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    project_id = fields.Many2one('project.project', string='Obra', index=True)
    task_id = fields.Many2one('project.task', string='Nivel', index=True)
    furniture_task_id = fields.Many2one(
        related='task_id.construction_furniture_task_id', string='Mueble', store=True)
    space_task_id = fields.Many2one('project.task', string='Ambiente', index=True)
    apartment_task_id = fields.Many2one(
        related='space_task_id.construction_apartment_task_id', string='Departamento',
        store=True)
    floor_task_id = fields.Many2one(
        related='space_task_id.construction_floor_task_id', string='Piso', store=True)
    stage = fields.Selection(stage_selection, string='Etapa')
    product_id = fields.Many2one('product.product', string='Material', index=True)
    uom_id = fields.Many2one(related='product_id.uom_id', string='Unidad')
    qty_budget = fields.Float(string='Presupuestado', digits='Product Unit', aggregator='sum')
    qty_required = fields.Float(string='Requerido', digits='Product Unit', aggregator='sum')
    qty_consumed = fields.Float(string='Consumido', digits='Product Unit', aggregator='sum')
    amount_budget = fields.Monetary(string='Presupuestado (monto)', currency_field='currency_id')
    amount_required = fields.Monetary(string='Requerido (monto)', currency_field='currency_id')
    amount_consumed = fields.Monetary(string='Consumido (monto)', currency_field='currency_id')
    amount_diff = fields.Monetary(
        string='Diferencia (monto)', currency_field='currency_id',
        help='Requerido menos presupuestado.')

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | AMOUNT_FIELDS
