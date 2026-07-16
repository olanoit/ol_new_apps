from odoo import fields, models


class L10nPeKardexLine(models.TransientModel):
    _name = 'l10n_pe.kardex.line'
    _description = 'Línea de Kardex SUNAT'
    _order = 'sequence, id'

    wizard_id = fields.Many2one(
        'l10n_pe.kardex.report.wizard', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=0)
    line_type = fields.Selection(
        [
            ('opening', 'Saldo inicial'),
            ('move', 'Movimiento'),
            ('total', 'Totales'),
        ],
        string='Tipo de línea', required=True, default='move')
    warehouse_id = fields.Many2one('stock.warehouse', string='Almacén')
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    date = fields.Datetime(string='Fecha')
    document_type_code = fields.Char(string='Tipo (Tabla 10)')
    serie = fields.Char(string='Serie')
    folio = fields.Char(string='Número')
    operation_type = fields.Char(string='Operación (Tabla 12)')
    picking_id = fields.Many2one('stock.picking', string='Transferencia')
    move_id = fields.Many2one('stock.move', string='Movimiento de stock')
    account_move_id = fields.Many2one('account.move', string='Comprobante')

    qty_in = fields.Float(string='Entrada', digits='Product Unit')
    cost_unit_in = fields.Float(string='C.U. entrada', digits='Product Price')
    cost_total_in = fields.Float(string='C.T. entrada', digits=(16, 2))
    qty_out = fields.Float(string='Salida', digits='Product Unit')
    cost_unit_out = fields.Float(string='C.U. salida', digits='Product Price')
    cost_total_out = fields.Float(string='C.T. salida', digits=(16, 2))
    balance_qty = fields.Float(string='Saldo', digits='Product Unit')
    balance_unit_cost = fields.Float(string='C.U. saldo', digits='Product Price')
    balance_value = fields.Float(string='C.T. saldo', digits=(16, 2))

    def action_open_origin(self):
        """Abre el documento origen: comprobante, transferencia o movimiento."""
        self.ensure_one()
        if self.account_move_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'res_id': self.account_move_id.id,
                'view_mode': 'form',
            }
        if self.picking_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'res_id': self.picking_id.id,
                'view_mode': 'form',
            }
        if self.move_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'stock.move',
                'res_id': self.move_id.id,
                'view_mode': 'form',
            }
        return False
