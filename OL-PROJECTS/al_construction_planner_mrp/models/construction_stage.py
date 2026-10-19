# -*- coding: utf-8 -*-
"""Etapa con su planta (paquete 1.10, M110-01).

Cada etapa que consume en la orden de fabricación puede tener su planta (la
operación de fabricación del almacén) y la categoría del producto intermedio
que entrega a la siguiente. Con eso el importador arma una lista de
materiales por etapa (M110-02) y Odoo encadena las órdenes por sus rutas.

Los campos van en este puente y no en el núcleo porque el núcleo no depende
de Inventario. La planta y la categoría son por compañía: el catálogo de
etapas es común a todas."""
from odoo import api, fields, models


class ConstructionStage(models.Model):
    _inherit = 'construction.stage'

    production_picking_type_id = fields.Many2one(
        'stock.picking.type', string='Planta (operación de fabricación)',
        company_dependent=True, domain=[('code', '=', 'mrp_operation')],
        help='Dónde se fabrica lo de esta etapa. Vacío: la etapa no tiene orden propia y sus '
             'materiales van en la orden de la etapa siguiente.')
    intermediate_categ_id = fields.Many2one(
        'product.category', string='Categoría de lo que entrega', company_dependent=True,
        help='Categoría del producto intermedio que sale de esta etapa hacia la siguiente. '
             'Sus rutas llevan el material entre plantas.')
    accessory_request = fields.Boolean(
        string='Accesorios a pedido desde la orden',
        help='Los materiales de esta etapa se proponen con «Pedir accesorios» en la orden de '
             'fabricación (paquete 1.9, M19-02).')
    production_chain_ok = fields.Boolean(
        string='Etapa de fabricación', compute='_compute_production_chain_ok',
        help='Fabricación o «Consume en la orden de fabricación»: puede tener planta.')

    @api.depends('kind', 'production_consumption', 'is_group')
    def _compute_production_chain_ok(self):
        for stage in self:
            stage.production_chain_ok = not stage.is_group and (
                stage.kind == 'production' or stage.production_consumption)

    @api.model
    def _production_chain(self, company):
        """Etapas con orden de fabricación propia en la compañía, en el orden del
        árbol (paquete 1.10, M110-01). Vacío: la fabricación de siempre."""
        stages = self.with_context(active_test=False).search([
            ('is_group', '=', False),
            '|', ('kind', '=', 'production'), ('production_consumption', '=', True)])
        stages = stages.with_company(company).filtered('production_picking_type_id')
        return self._tree_sorted(stages)

    @api.model
    def _accessory_codes(self):
        """Etapas cuyos materiales se piden con «Pedir accesorios» (M110-04)."""
        return tuple(self.with_context(active_test=False).search(
            [('accessory_request', '=', True)]).mapped('code'))

    @api.model
    def _construction_mark_assembly_accessories(self):
        """Compatibilidad con M19-02: el armado de mobiliario sigue proponiendo
        sus accesorios en las bases que ya lo usan."""
        stage = self.with_context(active_test=False).search([('code', '=', 'assembly')], limit=1)
        if stage and not stage.accessory_request:
            stage.accessory_request = True
