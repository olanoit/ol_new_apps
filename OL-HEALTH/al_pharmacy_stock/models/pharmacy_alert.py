# -*- coding: utf-8 -*-
"""Alertas sanitarias y retiro de lotes: al confirmar, los lotes afectados
quedan bloqueados (no se reservan ni se venden) y se listan el stock por
ubicación y los clientes que los recibieron, para el retiro."""
from odoo import api, fields, models
from odoo.exceptions import UserError


class PharmacyAlert(models.Model):
    _name = 'pharmacy.alert'
    _description = 'Alerta sanitaria'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Número de alerta', required=True, tracking=True,
                       help='Por ejemplo «ALERTA DIGEMID 105-2025».')
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    source = fields.Selection([
        ('authority', 'Autoridad sanitaria'),
        ('manufacturer', 'Titular o fabricante'),
        ('internal', 'Interna'),
    ], string='Origen', required=True, default='authority')
    description = fields.Text(string='Detalle', help='Motivo: falsificado, baja calidad, etc.')
    line_ids = fields.One2many('pharmacy.alert.line', 'alert_id', string='Productos afectados')
    lot_ids = fields.Many2many('stock.lot', string='Lotes bloqueados', readonly=True,
                               copy=False, check_company=True)
    quant_ids = fields.Many2many('stock.quant', compute='_compute_impact', string='Stock afectado')
    customer_ids = fields.Many2many('res.partner', compute='_compute_impact',
                                   string='Clientes que los recibieron')
    state = fields.Selection([('draft', 'Borrador'), ('done', 'Confirmada')],
                             string='Estado', default='draft', tracking=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)

    def _find_lots(self):
        self.ensure_one()
        Lot = self.env['stock.lot']
        lots = Lot.browse()
        for line in self.line_ids:
            domain = [('product_id', 'in', line.product_tmpl_id.product_variant_ids.ids),
                      ('company_id', 'in', [self.company_id.id, False])]
            names = [name.strip() for name in (line.lot_names or '').split(',') if name.strip()]
            if names:
                domain.append(('name', 'in', names))
            lots |= Lot.search(domain)
        return lots

    def action_confirm(self):
        for alert in self:
            lots = alert._find_lots()
            if not lots:
                raise UserError(self.env._('Ningún lote de la base coincide con la alerta %s.',
                                           alert.name))
            lots._pharmacy_set_state('blocked', self.env._('Alerta %s', alert.name))
            alert.write({'lot_ids': [(6, 0, lots.ids)], 'state': 'done'})
            self.env['pharmacy.logbook.entry']._log(
                'incident', self.env._('Alerta sanitaria %(alert)s: %(count)s lotes bloqueados (%(lots)s).',
                                       alert=alert.name, count=len(lots),
                                       lots=', '.join(lots.mapped('name'))), record=alert)

    @api.depends('lot_ids')
    def _compute_impact(self):
        for alert in self:
            alert.quant_ids = self.env['stock.quant'].search([
                ('lot_id', 'in', alert.lot_ids.ids), ('location_id.usage', '=', 'internal'),
                ('quantity', '>', 0)]) if alert.lot_ids else False
            move_lines = self.env['stock.move.line'].search([
                ('lot_id', 'in', alert.lot_ids.ids), ('state', '=', 'done'),
                ('location_dest_id.usage', '=', 'customer')]) if alert.lot_ids else self.env['stock.move.line']
            alert.customer_ids = move_lines.picking_id.partner_id


class PharmacyAlertLine(models.Model):
    _name = 'pharmacy.alert.line'
    _description = 'Producto de la alerta sanitaria'

    alert_id = fields.Many2one('pharmacy.alert', required=True, ondelete='cascade', index=True)
    product_tmpl_id = fields.Many2one('product.template', string='Producto', required=True)
    lot_names = fields.Char(string='Lotes',
                            help='Separados por comas. Vacío: todos los lotes del producto.')
    sanitary_registry = fields.Char(related='product_tmpl_id.pharmacy_sanitary_registry')
