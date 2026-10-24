# -*- coding: utf-8 -*-
"""Costo real, holguras y precio en la cotización (requerimiento CREVAL v1.0,
6.5). Tres capas por partida: el costo real (metrado real × costo del APU),
el costo ofertado (con holguras de metrado y de costo) y el precio (costo
ofertado más margen). El plan se genera con el metrado real y el costo del
APU; la diferencia queda como reserva por holguras."""
from odoo import api, fields, models

CONTRACT_TYPES = [
    ('lump_sum', 'Suma alzada'),
    ('unit_price', 'Precios unitarios'),
]
PRINT_FORMATS = [
    ('prices', 'Solo precios'),
    ('breakdown', 'Desglosado'),
]
LAYER_FIELDS = (
    'construction_qty_real', 'construction_qty_slack_pct', 'construction_qty_slack',
    'construction_cost_apu', 'construction_cost_slack_pct', 'construction_cost_slack',
    'construction_margin_pct', 'construction_margin_amount',
)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    construction_contract_type = fields.Selection(
        CONTRACT_TYPES, string='Tipo de contrato', default='lump_sum',
        help='Suma alzada: se cobra el precio pactado. Precios unitarios: la valorización cobra '
             'el metrado medido, de modo que la holgura de metrado no se cobra.')
    construction_print_format = fields.Selection(
        PRINT_FORMATS, string='Formato de impresión', default='prices',
        help='Solo precios: el cliente ve el precio de cada partida. Desglosado: además el costo '
             'directo, los gastos generales, los imprevistos y la utilidad. Las columnas '
             'internas (metrado real, costo del APU, costo ofertado, margen) no se imprimen.')
    construction_amount_real = fields.Monetary(
        string='Costo directo real', compute='_compute_construction_layers',
        help='Metrado real × costo del APU: el presupuesto meta del plan.')
    construction_amount_offered = fields.Monetary(
        string='Costo ofertado', compute='_compute_construction_layers')
    construction_amount_reserve = fields.Monetary(
        string='Reserva por holguras', compute='_compute_construction_layers',
        help='Costo ofertado − costo real: queda como reserva del plan.')
    construction_layers_warning = fields.Char(compute='_compute_construction_layers')

    @api.depends('order_line.construction_amount_real', 'order_line.construction_amount_offered',
                 'order_line.construction_margin_pct', 'order_line.construction_margin_amount',
                 'order_line.construction_qty_slack_pct', 'order_line.construction_qty_slack',
                 'order_line.construction_line_role', 'construction_contract_type')
    def _compute_construction_layers(self):
        for order in self:
            lines = order.order_line.filtered(
                lambda l: not l.display_type and l.construction_line_role == 'partida')
            order.construction_amount_real = sum(lines.mapped('construction_amount_real'))
            order.construction_amount_offered = sum(lines.mapped('construction_amount_offered'))
            order.construction_amount_reserve = \
                order.construction_amount_offered - order.construction_amount_real
            warnings = []
            if order.construction_contract_type == 'unit_price' and any(
                    line.construction_qty_slack_pct or line.construction_qty_slack
                    for line in lines):
                warnings.append(self.env._(
                    'Contrato a precios unitarios: la valorización cobra el metrado medido y la '
                    'holgura de metrado no se cobra.'))
            if any(line.construction_margin_pct or line.construction_margin_amount
                   for line in lines) and order.order_line.filtered(
                    lambda l: l.construction_line_role in ('overhead', 'profit')):
                warnings.append(self.env._(
                    'Hay margen por partida y también gastos generales o utilidad en el pie: use '
                    'uno de los dos.'))
            order.construction_layers_warning = ' '.join(warnings) or False


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    construction_qty_real = fields.Float(
        string='Metrado real', digits='Product Unit', copy=True,
        help='El que pasa al plan. La cantidad de la cotización es el metrado ofertado.')
    construction_qty_slack_pct = fields.Float(string='Holgura de metrado (%)', digits=(16, 4),
                                              copy=True)
    construction_qty_slack = fields.Float(string='Holgura de metrado', digits='Product Unit',
                                          copy=True)
    construction_cost_apu = fields.Float(
        string='Costo del APU', digits='Product Price', copy=True,
        help='Costo unitario de la receta o del Work Item.')
    construction_cost_slack_pct = fields.Float(string='Holgura de costo (%)', digits=(16, 4),
                                               copy=True)
    construction_cost_slack = fields.Float(string='Holgura de costo', digits='Product Price',
                                           copy=True)
    construction_margin_pct = fields.Float(string='Margen (%)', digits=(16, 4), copy=True)
    construction_margin_amount = fields.Float(string='Margen', digits='Product Price', copy=True)
    construction_cost_offered = fields.Float(
        string='Costo ofertado', digits='Product Price', compute='_compute_construction_layers',
        store=True)
    construction_amount_real = fields.Monetary(
        string='Costo real', compute='_compute_construction_layers', store=True)
    construction_amount_offered = fields.Monetary(
        string='Costo ofertado total', compute='_compute_construction_layers', store=True)
    construction_amount_reserve = fields.Monetary(
        string='Reserva', compute='_compute_construction_layers', store=True)

    @api.depends(*LAYER_FIELDS, 'product_uom_qty')
    def _compute_construction_layers(self):
        for line in self:
            offered = line._construction_cost_offered()
            line.construction_cost_offered = offered
            line.construction_amount_real = line.construction_qty_real * line.construction_cost_apu
            line.construction_amount_offered = line.product_uom_qty * offered \
                if line.construction_qty_real else 0.0
            line.construction_amount_reserve = \
                line.construction_amount_offered - line.construction_amount_real

    def _construction_cost_offered(self):
        self.ensure_one()
        return self.construction_cost_apu * (1 + self.construction_cost_slack_pct / 100.0) \
            + self.construction_cost_slack

    def _construction_layer_values(self):
        """Cantidad y precio de la línea que salen de las capas: metrado
        ofertado y precio unitario (y costo para el margen de ventas)."""
        self.ensure_one()
        if not self.construction_qty_real:
            return {}
        offered = self._construction_cost_offered()
        values = {
            'product_uom_qty': self.construction_qty_real
            * (1 + self.construction_qty_slack_pct / 100.0) + self.construction_qty_slack,
            'price_unit': offered * (1 + self.construction_margin_pct / 100.0)
            + self.construction_margin_amount,
        }
        if 'purchase_price' in self._fields:
            values['purchase_price'] = offered
        return values

    @api.onchange(*LAYER_FIELDS)
    def _onchange_construction_layers(self):
        self.update(self._construction_layer_values())

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line, vals in zip(lines, vals_list):
            if set(LAYER_FIELDS) & set(vals):
                line.write(line._construction_layer_values())
        return lines

    def write(self, vals):
        res = super().write(vals)
        if set(LAYER_FIELDS) & set(vals):
            for line in self:
                values = line._construction_layer_values()
                if values:
                    super(SaleOrderLine, line).write(values)
        return res


class ConstructionResourcePlan(models.Model):
    _inherit = 'construction.resource.plan'

    construction_reserve_amount = fields.Monetary(
        string='Reserva por holguras', compute='_compute_construction_reserve_amount',
        help='Costo ofertado − costo real de la cotización del contrato: no está en las líneas '
             'del plan; se libera a una partida con un cambio aprobado.')

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | {'construction_reserve_amount'}

    @api.depends('project_id.construction_sale_order_id.order_line.construction_amount_reserve')
    def _compute_construction_reserve_amount(self):
        for plan in self:
            # sudo: quien ve el plan no siempre lee ventas; solo se suma la
            # reserva de la cotización del contrato.
            order_sudo = plan.project_id.construction_sale_order_id.sudo()
            plan.construction_reserve_amount = order_sudo.construction_amount_reserve
