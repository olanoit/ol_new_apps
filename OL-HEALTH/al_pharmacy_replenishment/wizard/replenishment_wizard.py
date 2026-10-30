# -*- coding: utf-8 -*-
"""Sugerido de compra por local: lo que la botica debería pedir para cubrir
los próximos días según lo que vende, lo que le pidieron y no tenía
(faltantes), lo que tiene y lo que ya está por llegar.

    sugerido = venta diaria × días de cobertura + faltantes − stock − entrante

La venta diaria es la del TPV del local más las entregas a clientes que no
salen del TPV (pedidos de venta), menos sus devoluciones, en el periodo.
El sugerido se redondea hacia arriba al múltiplo de compra: la unidad del
proveedor principal o, si compra por unidad, la presentación más grande
(normalmente la caja)."""
import math
from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tools import float_is_zero


class PharmacyReplenishmentWizard(models.TransientModel):
    _name = 'pharmacy.replenishment.wizard'
    _description = 'Sugerido de compra'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Local', required=True, check_company=True,
        default=lambda self: self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)], limit=1))
    period_days = fields.Integer(string='Periodo de análisis (días)', required=True, default=30)
    coverage_days = fields.Integer(string='Días de cobertura', required=True, default=15,
                                   help='Días de venta que debe cubrir el pedido.')
    source_warehouse_id = fields.Many2one(
        'stock.warehouse', string='Almacén central', check_company=True,
        help='Origen del traslado si el local se abastece de otro almacén de la compañía.')
    line_ids = fields.One2many('pharmacy.replenishment.wizard.line', 'wizard_id',
                               string='Productos')
    computed = fields.Boolean(readonly=True)

    @api.constrains('period_days', 'coverage_days')
    def _check_days(self):
        for wizard in self:
            if wizard.period_days <= 0 or wizard.coverage_days <= 0:
                raise ValidationError(self.env._('El periodo y los días de cobertura deben ser mayores que cero.'))

    # ------------------------------------------------------------------
    # Cálculo
    # ------------------------------------------------------------------
    def _date_from(self):
        return fields.Datetime.now() - timedelta(days=self.period_days)

    def _pos_sales(self, date_from):
        """Unidades vendidas en el TPV del local (neto de devoluciones)."""
        groups = self.env['pos.order.line']._read_group([
            ('order_id.state', 'in', ('paid', 'done')),
            ('order_id.date_order', '>=', date_from),
            ('order_id.company_id', '=', self.company_id.id),
            ('order_id.config_id.picking_type_id.warehouse_id', '=', self.warehouse_id.id),
            ('product_id.is_storable', '=', True),
        ], ['product_id'], ['qty:sum'])
        return {product: qty for product, qty in groups}

    def _other_deliveries(self, date_from):
        """Entregas a clientes del local que no vienen del TPV (pedidos de
        venta), menos sus devoluciones, en la unidad del producto."""
        base = [
            ('state', '=', 'done'),
            ('date', '>=', date_from),
            ('company_id', '=', self.company_id.id),
            ('product_id.is_storable', '=', True),
            ('picking_id.pos_order_id', '=', False),
            ('picking_id.pos_session_id', '=', False),
        ]
        view = self.warehouse_id.view_location_id.id
        result = defaultdict(float)
        out = self.env['stock.move']._read_group(base + [
            ('location_id', 'child_of', view), ('location_dest_id.usage', '=', 'customer'),
        ], ['product_id'], ['product_qty:sum'])
        back = self.env['stock.move']._read_group(base + [
            ('location_id.usage', '=', 'customer'), ('location_dest_id', 'child_of', view),
        ], ['product_id'], ['product_qty:sum'])
        for product, qty in out:
            result[product] += qty
        for product, qty in back:
            result[product] -= qty
        return result

    def _pending_shortages(self):
        groups = self.env['pharmacy.shortage']._read_group([
            ('state', '=', 'pending'),
            ('warehouse_id', '=', self.warehouse_id.id),
            ('product_id', '!=', False),
        ], ['product_id'], ['quantity:sum'])
        return {product: qty for product, qty in groups}

    def _main_seller(self, product):
        sellers = product.seller_ids.filtered(
            lambda s: (not s.company_id or s.company_id == self.company_id)
            and (not s.product_id or s.product_id == product))
        return sellers.sorted(lambda s: (s.sequence, s.id))[:1]

    def _purchase_multiple(self, product, seller):
        """Múltiplo de compra en unidades del producto."""
        if seller and seller.uom_id and seller.uom_id != product.uom_id:
            return seller.uom_id._compute_quantity(1.0, product.uom_id)
        presentations = product.product_tmpl_id.pharmacy_presentation_ids.filtered('active')
        return max(presentations.mapped('factor'), default=1.0) or 1.0

    @api.model
    def _suggested_quantity(self, avg_daily, coverage_days, shortage_qty, stock_qty, incoming_qty,
                            multiple):
        need = avg_daily * coverage_days + shortage_qty - stock_qty - incoming_qty
        if need <= 1e-9:
            return 0.0
        multiple = multiple if multiple and multiple > 0 else 1.0
        return math.ceil(need / multiple - 1e-9) * multiple

    def _prepare_lines(self):
        self.ensure_one()
        date_from = self._date_from()
        sales = defaultdict(float)
        for product, qty in self._pos_sales(date_from).items():
            sales[product] += qty
        for product, qty in self._other_deliveries(date_from).items():
            sales[product] += qty
        shortages = self._pending_shortages()
        products = self.env['product.product'].union([*sales, *shortages])
        products = products.filtered(lambda p: p.is_storable)
        products_wh = products.with_context(warehouse_id=self.warehouse_id.id)
        values = []
        for product in products_wh.sorted('display_name'):
            sold = max(sales.get(product, 0.0), 0.0)
            avg_daily = sold / self.period_days
            shortage_qty = shortages.get(product, 0.0)
            seller = self._main_seller(product)
            multiple = self._purchase_multiple(product, seller)
            suggested = self._suggested_quantity(
                avg_daily, self.coverage_days, shortage_qty, product.qty_available,
                product.incoming_qty, multiple)
            if float_is_zero(suggested, precision_digits=6):
                continue
            values.append({
                'product_id': product.id,
                'vendor_id': seller.partner_id.id,
                'sold_qty': sold,
                'avg_daily': avg_daily,
                'shortage_qty': shortage_qty,
                'stock_qty': product.qty_available,
                'incoming_qty': product.incoming_qty,
                'multiple': multiple,
                'suggested_qty': suggested,
            })
        return values

    def action_compute(self):
        self.ensure_one()
        self.line_ids = [Command.clear()] + [Command.create(vals) for vals in self._prepare_lines()]
        self.computed = True
        return self._reopen()

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'name': self.env._('Sugerido de compra'),
        }

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def _lines_to_order(self):
        lines = self.line_ids.filtered(lambda line: line.suggested_qty > 0)
        if not lines:
            raise UserError(self.env._('No hay cantidades sugeridas que pedir.'))
        return lines

    def _mark_shortages(self, products, **values):
        shortages = self.env['pharmacy.shortage'].search([
            ('state', '=', 'pending'),
            ('warehouse_id', '=', self.warehouse_id.id),
            ('product_id', 'in', products.ids),
        ])
        shortages.write({'state': 'ordered', **values})
        return shortages

    def action_create_purchase(self):
        self.ensure_one()
        lines = self._lines_to_order()
        missing = lines.filtered(lambda line: not line.vendor_id)
        if missing:
            raise UserError(self.env._(
                'Indique el proveedor de: %s', ', '.join(missing.product_id.mapped('display_name'))))
        orders = self.env['purchase.order']
        by_vendor = defaultdict(lambda: self.env['pharmacy.replenishment.wizard.line'])
        for line in lines:
            by_vendor[line.vendor_id] |= line
        for vendor, vendor_lines in by_vendor.items():
            order_lines = []
            for line in vendor_lines:
                seller = self._main_seller(line.product_id).filtered(
                    lambda s: s.partner_id == vendor)
                uom = seller.uom_id or line.product_id.uom_id
                qty = line.product_id.uom_id._compute_quantity(line.suggested_qty, uom)
                order_lines.append(Command.create({
                    'product_id': line.product_id.id,
                    'product_qty': qty,
                    'uom_id': uom.id,  # Odoo 20: UdM de la línea de compra
                }))
            order = self.env['purchase.order'].create({
                'partner_id': vendor.id,
                'company_id': self.company_id.id,
                'picking_type_id': self.warehouse_id.in_type_id.id,
                'origin': self.env._('Sugerido %s', self.warehouse_id.name),
                'order_line': order_lines,
            })
            self._mark_shortages(vendor_lines.product_id, purchase_order_id=order.id)
            orders |= order
        action = self.env['ir.actions.actions']._for_xml_id('purchase.purchase_rfq')
        action['domain'] = [('id', 'in', orders.ids)]
        if len(orders) == 1:
            action.update({'view_mode': 'form', 'views': [(False, 'form')], 'res_id': orders.id})
        return action

    def action_create_transfer(self):
        self.ensure_one()
        source = self.source_warehouse_id
        if not source:
            raise UserError(self.env._('Elija el almacén central de donde sale el traslado.'))
        if source == self.warehouse_id:
            raise UserError(self.env._('El almacén central debe ser distinto del local.'))
        lines = self._lines_to_order()
        location = source.lot_stock_id
        destination = self.warehouse_id.lot_stock_id
        picking = self.env['stock.picking'].create({
            'picking_type_id': source.int_type_id.id,
            'location_id': location.id,
            'location_dest_id': destination.id,
            'company_id': self.company_id.id,
            'origin': self.env._('Sugerido %s', self.warehouse_id.name),
            'move_ids': [Command.create({
                'product_id': line.product_id.id,
                'product_uom_qty': line.suggested_qty,
                'uom_id': line.product_id.uom_id.id,
                'location_id': location.id,
                'location_dest_id': destination.id,
            }) for line in lines],
        })
        picking.action_confirm()
        self._mark_shortages(lines.product_id, picking_id=picking.id)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
        }


class PharmacyReplenishmentWizardLine(models.TransientModel):
    _name = 'pharmacy.replenishment.wizard.line'
    _description = 'Línea del sugerido de compra'
    _order = 'product_id'

    wizard_id = fields.Many2one('pharmacy.replenishment.wizard', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Producto', required=True, readonly=True)
    uom_id = fields.Many2one(related='product_id.uom_id', string='Unidad')
    vendor_id = fields.Many2one('res.partner', string='Proveedor')
    sold_qty = fields.Float(string='Vendido', digits='Product Unit', readonly=True)
    avg_daily = fields.Float(string='Venta diaria', digits=(16, 2), readonly=True)
    shortage_qty = fields.Float(string='Faltantes', digits='Product Unit', readonly=True)
    stock_qty = fields.Float(string='Stock', digits='Product Unit', readonly=True)
    incoming_qty = fields.Float(string='Por llegar', digits='Product Unit', readonly=True)
    multiple = fields.Float(string='Múltiplo', digits='Product Unit', readonly=True,
                            help='Unidades por empaque de compra.')
    suggested_qty = fields.Float(string='Sugerido', digits='Product Unit')
