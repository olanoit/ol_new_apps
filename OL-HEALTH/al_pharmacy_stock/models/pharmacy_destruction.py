# -*- coding: utf-8 -*-
"""Acta de baja y destrucción (BPOF 7.5.1.33-34): productos vencidos,
deteriorados o retirados. Al validarla se dan de baja con un desecho de
inventario por línea y el acta queda impresa para la firma."""
from odoo import api, fields, models
from odoo.exceptions import UserError

REASONS = [
    ('expired', 'Vencido'),
    ('damaged', 'Deteriorado'),
    ('recall', 'Alerta sanitaria o retiro'),
    ('other', 'Otro'),
]


class PharmacyDestruction(models.Model):
    _name = 'pharmacy.destruction'
    _description = 'Acta de baja y destrucción'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', readonly=True, copy=False, default='/')
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    warehouse_id = fields.Many2one('stock.warehouse', string='Local', required=True,
                                   check_company=True)
    method = fields.Char(string='Método de destrucción',
                         help='Por ejemplo, entrega a una empresa operadora de residuos sólidos.')
    witness = fields.Char(string='Testigos o autoridad presente')
    line_ids = fields.One2many('pharmacy.destruction.line', 'destruction_id', string='Productos')
    # Odoo 20: la baja es un movimiento de stock (is_scrap), sin stock.scrap.
    scrap_ids = fields.One2many('stock.move', 'pharmacy_destruction_id', string='Bajas')
    state = fields.Selection([('draft', 'Borrador'), ('done', 'Validada')], default='draft',
                             string='Estado', tracking=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('pharmacy.destruction') or '/'
        return super().create(vals_list)

    def action_validate(self):
        if not self.env.user.has_group('al_pharmacy_base.group_pharmacy_pharmacist'):
            raise UserError(self.env._('Solo un químico farmacéutico valida el acta de baja.'))
        for destruction in self.filtered(lambda d: d.state == 'draft'):
            if not destruction.line_ids:
                raise UserError(self.env._('El acta %s no tiene productos.', destruction.name))
            for line in destruction.line_ids:
                scrap = self.env['stock.move'].with_context(pharmacy_any_lot_state=True).create({
                    'is_scrap': True,
                    'product_id': line.product_id.id,
                    'uom_id': line.product_id.uom_id.id,
                    'quantity': line.quantity,
                    'location_id': line.location_id.id,
                    'location_dest_id': destruction.company_id.scrap_location_id.id,
                    'origin': destruction.name,
                    'company_id': destruction.company_id.id,
                    'pharmacy_destruction_id': destruction.id,
                })
                if line.lot_id:
                    scrap.lot_ids = line.lot_id
                # Lote vencido o bloqueado: la baja se hace igual (es su destino).
                scrap.with_context(pharmacy_any_lot_state=True)._action_scrap()
            destruction.state = 'done'


class PharmacyDestructionLine(models.Model):
    _name = 'pharmacy.destruction.line'
    _description = 'Producto del acta de baja'
    _check_company_auto = True

    destruction_id = fields.Many2one('pharmacy.destruction', required=True, ondelete='cascade',
                                     index=True, check_company=True)
    company_id = fields.Many2one(related='destruction_id.company_id', store=True)
    product_id = fields.Many2one('product.product', string='Producto', required=True,
                                 check_company=True)
    lot_id = fields.Many2one('stock.lot', string='Lote', check_company=True,
                             domain="[('product_id', '=', product_id)]")
    expiration_date = fields.Datetime(related='lot_id.expiration_date', string='Vencimiento')
    location_id = fields.Many2one('stock.location', string='Ubicación', required=True,
                                  check_company=True, domain="[('usage', '=', 'internal')]")
    quantity = fields.Float(string='Cantidad', required=True, digits='Product Unit')
    uom_id = fields.Many2one(related='product_id.uom_id', string='Unidad')
    reason = fields.Selection(REASONS, string='Motivo', required=True, default='expired')


class StockMove(models.Model):
    _inherit = 'stock.move'

    pharmacy_destruction_id = fields.Many2one('pharmacy.destruction', string='Acta de baja',
                                              readonly=True, index='btree_not_null',
                                              check_company=True)
