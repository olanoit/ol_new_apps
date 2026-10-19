# -*- coding: utf-8 -*-
"""Faltante (demanda perdida): lo que un cliente pide en la caja y no se le
puede vender. Sin este registro la venta se pierde sin rastro y la compra no
se entera; el sugerido de compra suma los faltantes pendientes."""
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

REASONS = [
    ('no_stock', 'Sin stock'),
    ('not_carried', 'No lo trabajamos'),
    ('price', 'Precio'),
    ('other', 'Otro'),
]


class PharmacyShortage(models.Model):
    _name = 'pharmacy.shortage'
    _description = 'Faltante'
    _order = 'date desc, id desc'
    _check_company_auto = True

    date = fields.Datetime(string='Fecha', required=True, default=fields.Datetime.now, index=True)
    product_id = fields.Many2one('product.product', string='Producto', check_company=True,
                                 index='btree_not_null',
                                 help='Vacío si el cliente pidió algo que no está en el catálogo.')
    description = fields.Char(string='Descripción',
                              help='Lo que pidió el cliente, si no es un producto del catálogo.')
    quantity = fields.Float(string='Cantidad', digits='Product Unit', required=True, default=1.0)
    uom_id = fields.Many2one(related='product_id.uom_id', string='Unidad')
    reason = fields.Selection(REASONS, string='Motivo', required=True, default='no_stock')
    warehouse_id = fields.Many2one('stock.warehouse', string='Local', required=True,
                                   check_company=True, index=True)
    pos_session_id = fields.Many2one('pos.session', string='Sesión de caja', readonly=True,
                                     check_company=True, index='btree_not_null')
    pos_config_id = fields.Many2one(related='pos_session_id.config_id', string='Caja')
    employee_id = fields.Many2one('hr.employee', string='Cajero (empleado)', check_company=True)
    user_id = fields.Many2one('res.users', string='Registrado por', required=True,
                              default=lambda self: self.env.user)
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('ordered', 'Pedido'),
        ('done', 'Atendido'),
        ('discarded', 'Descartado'),
    ], string='Estado', required=True, default='pending', index=True)
    purchase_order_id = fields.Many2one('purchase.order', string='Solicitud de presupuesto',
                                        readonly=True, check_company=True)
    picking_id = fields.Many2one('stock.picking', string='Traslado', readonly=True,
                                 check_company=True)
    note = fields.Text(string='Nota')
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company, index=True)

    @api.depends('product_id', 'description')
    def _compute_display_name(self):
        for shortage in self:
            shortage.display_name = shortage.product_id.display_name or shortage.description or ''

    @api.constrains('product_id', 'description')
    def _check_product_or_description(self):
        for shortage in self:
            if not shortage.product_id and not (shortage.description or '').strip():
                raise ValidationError(self.env._('Indique el producto o lo que pidió el cliente.'))

    @api.constrains('quantity')
    def _check_quantity(self):
        if any(shortage.quantity <= 0 for shortage in self):
            raise ValidationError(self.env._('La cantidad del faltante debe ser mayor que cero.'))

    @api.model
    def create_from_pos(self, values):
        """Faltante registrado desde la caja. ``values``: session_id,
        product_id (opcional), description, quantity, reason y employee_id
        (con «Iniciar sesión con empleados»). El local sale de la caja."""
        session = self.env['pos.session'].browse(values['session_id']).exists()
        if not session:
            raise UserError(self.env._('La sesión de caja ya no existe.'))
        warehouse = session.config_id.picking_type_id.warehouse_id
        if not warehouse:
            raise UserError(self.env._('La caja %s no tiene local (almacén).', session.config_id.name))
        reason = values.get('reason') or 'no_stock'
        if reason not in dict(REASONS):
            reason = 'other'
        shortage = self.create({
            'product_id': values.get('product_id') or False,
            'description': (values.get('description') or '').strip() or False,
            'quantity': values.get('quantity') or 1.0,
            'reason': reason,
            'warehouse_id': warehouse.id,
            'pos_session_id': session.id,
            'employee_id': values.get('employee_id') or False,
            'company_id': session.company_id.id,
        })
        return {'id': shortage.id, 'name': shortage.display_name}

    def action_done(self):
        self.filtered(lambda s: s.state in ('pending', 'ordered')).state = 'done'

    def action_discard(self):
        self.filtered(lambda s: s.state in ('pending', 'ordered')).state = 'discarded'

    def action_reset(self):
        self.state = 'pending'
