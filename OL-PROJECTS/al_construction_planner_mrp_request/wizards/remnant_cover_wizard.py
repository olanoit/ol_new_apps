# -*- coding: utf-8 -*-
"""«Cubrir con retazo» en el despacho del requerimiento de obra (paquete
1.11, M111-22): la necesidad es la del movimiento, no la de una orden."""
from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang


class ConstructionRemnantCoverWizard(models.TransientModel):
    _inherit = 'construction.remnant.cover.wizard'

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        move = self.env['stock.move'].browse(values.get('move_id'))
        if move and move._construction_is_request_board():
            values['need_qty'] = move.product_uom._compute_quantity(
                move.construction_need_qty, move.product_id.uom_id, round=False)
        return values

    def action_assign(self):
        self.ensure_one()
        move = self.move_id
        if not move._construction_is_request_board():
            return super().action_assign()
        chosen = self.line_ids.filtered('selected')
        if not chosen:
            raise UserError(self.env._('Marque al menos un retazo.'))
        if self.fit_required and not self.fit_confirmed:
            raise UserError(self.env._(
                'Confirme que las piezas entran en los retazos elegidos (despiece).'))
        quants = chosen.quant_id
        if quants.lot_id.filtered(lambda l: l.product_id.construction_remnant_source_tmpl_id
                                  != self.product_id.product_tmpl_id):
            raise UserError(self.env._('El retazo debe ser del mismo tablero.'))
        move._construction_cover_request_with_remnants(quants)
        covered = sum(chosen.mapped('sheet_pct')) / 100
        product = self.product_id
        body = self.env._(
            'Fracción %(fraction)s de [%(code)s] cubierta con el retazo %(lots)s '
            '(%(covered)s plancha) por %(user)s.',
            fraction=formatLang(self.env, self.fraction_to_cover, digits=2),
            code=product.default_code or product.name,
            lots=', '.join(quants.lot_id.mapped('name')),
            covered=formatLang(self.env, covered, digits=2), user=self.env.user.name)
        self.picking_id.message_post(body=body)
        # El almacenero puede no leer el requerimiento: solo se deja la nota.
        move.construction_request_line_id.request_id.sudo().message_post(body=body)
        if covered > self.need_qty:
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
                'type': 'warning',
                'message': self.env._('Lo cubierto con retazos supera la necesidad.'),
                'next': {'type': 'ir.actions.act_window_close'},
            }}
        return {'type': 'ir.actions.act_window_close'}
