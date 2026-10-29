# -*- coding: utf-8 -*-
"""Recepción según BPOF 7.5.1.5-7.5.1.13: lote, vencimiento y registro
sanitario vigente en los productos farmacéuticos, e inspección del envase.
Una recepción no conforme deja sus lotes en cuarentena."""
from odoo import api, fields, models
from odoo.exceptions import UserError

RETURN_REASONS = [
    ('expiry', 'Vencimiento o próximo a vencer'),
    ('damage', 'Deterioro o envase dañado'),
    ('recall', 'Alerta sanitaria o retiro'),
    ('error', 'Error de despacho'),
    ('other', 'Otro'),
]


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    pharmacy_has_products = fields.Boolean(compute='_compute_pharmacy_has_products', store=True)
    pharmacy_inspection = fields.Selection([
        ('pending', 'Por inspeccionar'),
        ('conform', 'Conforme'),
        ('nonconform', 'No conforme'),
    ], string='Inspección de recepción', default='pending', copy=False, tracking=True,
        help='Estado del envase, rotulado y condiciones de transporte. «No conforme» deja los '
             'lotes recibidos en cuarentena.')
    pharmacy_inspection_note = fields.Text(string='Observaciones de la recepción', copy=False)
    pharmacy_return_reason = fields.Selection(RETURN_REASONS, string='Motivo de la devolución',
                                              copy=False)

    @api.depends('move_ids.product_id.pharmacy_ok')
    def _compute_pharmacy_has_products(self):
        for picking in self:
            picking.pharmacy_has_products = any(picking.move_ids.product_id.mapped('pharmacy_ok'))

    def _pre_action_done_hook(self):
        res = super()._pre_action_done_hook()
        if res is not True:
            return res
        for picking in self.filtered(lambda p: p.picking_type_code == 'incoming'
                                     and p.pharmacy_has_products):
            picking._pharmacy_check_reception()
        return res

    def _pharmacy_check_reception(self):
        self.ensure_one()
        if self.pharmacy_inspection == 'pending':
            raise UserError(self.env._(
                'Registre la inspección de la recepción %s (conforme o no conforme) antes de '
                'validarla.', self.name))
        if self.pharmacy_inspection == 'nonconform' and not self.pharmacy_inspection_note:
            raise UserError(self.env._('Describa por qué la recepción %s no es conforme.',
                                       self.name))
        today = fields.Date.context_today(self)
        problems = []
        for move_line in self.move_line_ids.filtered(
                lambda ml: ml.product_id.pharmacy_ok and ml.quantity):
            template = move_line.product_id.product_tmpl_id
            if not template.pharmacy_sanitary_registry:
                problems.append(self.env._('%s: sin registro sanitario.', template.display_name))
            elif template.pharmacy_registry_expiry and template.pharmacy_registry_expiry < today:
                problems.append(self.env._('%(product)s: registro sanitario vencido el %(date)s.',
                                           product=template.display_name,
                                           date=template.pharmacy_registry_expiry))
            if move_line.product_id.tracking:
                if not (move_line.lot_id or move_line.lot_name):
                    problems.append(self.env._('%s: falta el lote.', template.display_name))
                elif template.use_expiration_date and not (
                        move_line.expiration_date or move_line.lot_id.expiration_date):
                    problems.append(self.env._('%s: falta la fecha de vencimiento.',
                                               template.display_name))
        if problems:
            raise UserError('\n'.join(problems))

    def _action_done(self):
        res = super()._action_done()
        for picking in self.filtered(lambda p: p.picking_type_code == 'incoming'
                                     and p.pharmacy_inspection == 'nonconform'):
            lots = picking.move_line_ids.lot_id.filtered(lambda lot: lot.product_id.pharmacy_ok)
            lots._pharmacy_set_state('quarantine', self.env._(
                'Recepción no conforme %(picking)s: %(note)s', picking=picking.name,
                note=picking.pharmacy_inspection_note))
        return res
