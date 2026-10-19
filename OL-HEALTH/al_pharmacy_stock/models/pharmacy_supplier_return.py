# -*- coding: utf-8 -*-
"""Canje o devolución a la droguería: los lotes por vencer, vencidos o dañados
que el proveedor acepta canjear. Al aceptarlo se prepara la salida del stock
hacia el proveedor y, con su nota de crédito, se registra la rectificativa."""
from odoo import Command, api, fields, models
from odoo.exceptions import UserError

RETURN_REASONS = [
    ('near_expiry', 'Por vencer'),
    ('expired', 'Vencido'),
    ('damaged', 'Dañado'),
]


class PharmacySupplierReturn(models.Model):
    _name = 'pharmacy.supplier.return'
    _description = 'Canje con la droguería'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', readonly=True, copy=False, default='/')
    partner_id = fields.Many2one('res.partner', string='Droguería o proveedor', required=True,
                                 check_company=True, tracking=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Local', required=True,
                                   check_company=True,
                                   default=lambda self: self.env['stock.warehouse'].search(
                                       [('company_id', '=', self.env.company.id)], limit=1))
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('sent', 'Enviado'),
        ('accepted', 'Aceptado'),
        ('done', 'Hecho'),
        ('cancel', 'Cancelado'),
    ], string='Estado', default='draft', required=True, tracking=True, copy=False)
    line_ids = fields.One2many('pharmacy.supplier.return.line', 'return_id', string='Lotes',
                               copy=True)
    picking_id = fields.Many2one('stock.picking', string='Devolución de stock', readonly=True,
                                 copy=False, check_company=True)
    refund_id = fields.Many2one('account.move', string='Nota de crédito', readonly=True,
                                copy=False, check_company=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    amount_total = fields.Monetary(string='Total', compute='_compute_amount_total')
    note = fields.Text(string='Notas')
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)

    @api.depends('line_ids.subtotal')
    def _compute_amount_total(self):
        for supplier_return in self:
            supplier_return.amount_total = sum(supplier_return.line_ids.mapped('subtotal'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('pharmacy.supplier.return') or '/'
        return super().create(vals_list)

    def _check_lines(self):
        for supplier_return in self:
            if not supplier_return.line_ids:
                raise UserError(self.env._('El canje %s no tiene lotes.', supplier_return.name))

    def action_send(self):
        self._check_lines()
        self.filtered(lambda r: r.state == 'draft').state = 'sent'

    def action_accept(self):
        self._check_lines()
        for supplier_return in self.filtered(lambda r: r.state in ('draft', 'sent')):
            supplier_return.picking_id = supplier_return._create_return_picking()
            supplier_return.state = 'accepted'

    def _create_return_picking(self):
        """Salida del local al proveedor con los lotes del canje. Los lotes
        vencidos o bloqueados se pueden reservar: el canje es justamente para
        sacarlos."""
        self.ensure_one()
        dest = self.partner_id.property_stock_supplier or self.env.ref('stock.stock_location_suppliers')
        picking_type = self.warehouse_id.out_type_id
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'partner_id': self.partner_id.id,
            'location_id': self.warehouse_id.lot_stock_id.id,
            'location_dest_id': dest.id,
            'origin': self.name,
            'company_id': self.company_id.id,
            'move_ids': [Command.create({
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'product_uom': line.product_id.uom_id.id,
                'location_id': line.location_id.id,
                'location_dest_id': dest.id,
                'pharmacy_supplier_return_line_id': line.id,
            }) for line in self.line_ids],
        })
        picking = picking.with_context(pharmacy_any_lot_state=True)
        picking.action_confirm()
        # Al confirmar, Odoo junta los movimientos del mismo producto: cada lote
        # del canje es una línea de detalle de su movimiento.
        picking.move_line_ids.unlink()
        for line in self.line_ids:
            move = picking.move_ids.filtered(
                lambda m, line=line: m.product_id == line.product_id
                and m.location_id == line.location_id)[:1]
            self.env['stock.move.line'].with_context(pharmacy_any_lot_state=True).create({
                'move_id': move.id,
                'picking_id': picking.id,
                'product_id': line.product_id.id,
                'product_uom_id': line.product_id.uom_id.id,
                'lot_id': line.lot_id.id,
                'quantity': line.quantity,
                'location_id': line.location_id.id,
                'location_dest_id': dest.id,
            })
        return picking

    def action_done(self):
        """Valida la salida al proveedor (si aún no se validó) y cierra el canje.
        Los lotes vencidos salen sin el aviso de producto vencido: el canje es
        justamente para devolverlos."""
        for supplier_return in self.filtered(lambda r: r.state == 'accepted'):
            picking = supplier_return.picking_id
            if picking.state not in ('done', 'cancel'):
                picking.move_ids.picked = True
                picking.with_context(skip_expired=True, pharmacy_any_lot_state=True,
                                     skip_backorder=True).button_validate()
            if picking.state != 'done':
                raise UserError(self.env._(
                    'La devolución de stock %s no se pudo validar: revise sus cantidades.',
                    picking.name))
            supplier_return.state = 'done'

    def action_cancel(self):
        for supplier_return in self:
            if supplier_return.state == 'done':
                raise UserError(self.env._('Un canje hecho no se cancela: %s.', supplier_return.name))
            if supplier_return.picking_id and supplier_return.picking_id.state != 'done':
                supplier_return.picking_id.action_cancel()
            supplier_return.state = 'cancel'

    def action_draft(self):
        self.filtered(lambda r: r.state == 'cancel').write({'state': 'draft', 'picking_id': False})

    def action_create_refund(self):
        """Nota de crédito del proveedor en borrador, con las cantidades y el
        costo del canje, para completarla con el comprobante que envíe."""
        self.ensure_one()
        if self.state not in ('accepted', 'done'):
            raise UserError(self.env._('Registre la nota de crédito cuando el proveedor acepte el canje.'))
        if not self.refund_id:
            self.refund_id = self.env['account.move'].create({
                'move_type': 'in_refund',
                'partner_id': self.partner_id.id,
                'invoice_origin': self.name,
                'ref': self.env._('Canje %s', self.name),
                'company_id': self.company_id.id,
                'invoice_line_ids': [Command.create({
                    'product_id': line.product_id.id,
                    'name': '%s - %s' % (line.product_id.display_name, line.lot_id.name or ''),
                    'quantity': line.quantity,
                    'product_uom_id': line.product_id.uom_id.id,
                    'price_unit': line.price_unit,
                }) for line in self.line_ids],
            })
        return self.action_view_refund()

    def action_view_refund(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.refund_id.id,
            'view_mode': 'form',
        }

    def action_view_picking(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': self.picking_id.id,
            'view_mode': 'form',
        }

    def action_load_lots(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Cargar lotes'),
            'res_model': 'pharmacy.supplier.return.load',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_return_id': self.id},
        }


class PharmacySupplierReturnLine(models.Model):
    _name = 'pharmacy.supplier.return.line'
    _description = 'Lote del canje con la droguería'
    _check_company_auto = True

    return_id = fields.Many2one('pharmacy.supplier.return', required=True, ondelete='cascade',
                                index=True)
    company_id = fields.Many2one(related='return_id.company_id', store=True)
    currency_id = fields.Many2one(related='return_id.currency_id')
    product_id = fields.Many2one('product.product', string='Producto', required=True,
                                 check_company=True)
    lot_id = fields.Many2one('stock.lot', string='Lote', check_company=True,
                             domain="[('product_id', '=', product_id)]")
    expiration_date = fields.Datetime(related='lot_id.expiration_date', string='Vencimiento')
    location_id = fields.Many2one('stock.location', string='Ubicación', required=True,
                                  check_company=True, domain="[('usage', '=', 'internal')]")
    quantity = fields.Float(string='Cantidad', required=True, digits='Product Unit')
    uom_id = fields.Many2one(related='product_id.uom_id', string='Unidad')
    reason = fields.Selection(RETURN_REASONS, string='Motivo', required=True, default='near_expiry')
    price_unit = fields.Float(string='Costo unitario', digits='Product Price',
                              help='Costo de compra del lote; se usa en la nota de crédito.')
    subtotal = fields.Monetary(string='Subtotal', compute='_compute_subtotal')

    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id and not self.price_unit:
            self.price_unit = self.product_id.standard_price
        if not self.location_id and self.return_id.warehouse_id:
            self.location_id = self.return_id.warehouse_id.lot_stock_id


class StockMove(models.Model):
    _inherit = 'stock.move'

    pharmacy_supplier_return_line_id = fields.Many2one(
        'pharmacy.supplier.return.line', string='Línea del canje', readonly=True,
        index='btree_not_null', copy=False)
