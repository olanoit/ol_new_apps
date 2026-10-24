# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # Se copia: las entregas parciales (backorders) siguen vinculadas.
    construction_request_id = fields.Many2one(
        'construction.material.request', string='Requerimiento de obra',
        index='btree_not_null', readonly=True)
    # Quien la valida (paquete 1.11, M111-11): el responsable (user_id) queda
    # con quien la creó y el vale de despacho necesita al almacenero.
    construction_validated_by_id = fields.Many2one(
        'res.users', string='Validado por', readonly=True, copy=False)

    def _sanity_check(self, separate_pickings=True):
        """El despacho a obra de un requerimiento lo valida el almacén
        (Logística), no quien lo pidió (v1.6, M16-10)."""
        dispatches = self.filtered(
            lambda p: p.construction_request_id
            # El almacenero puede no leer el requerimiento: solo su tipo.
            and p.picking_type_id in p.construction_request_id.sudo()._get_dispatch_picking_types())
        if dispatches and not self.env.su and not self.env.user.has_group(
                'al_construction_material_request.group_construction_logistics'):
            raise UserError(_(
                'El despacho a obra %s lo valida el almacén (grupo Logística de '
                'requerimientos de obra).', ', '.join(dispatches.mapped('name'))))
        return super()._sanity_check(separate_pickings=separate_pickings)

    def _action_done(self):
        res = super()._action_done()
        done = self.filtered(lambda p: p.state == 'done')
        done.write({'construction_validated_by_id': self.env.uid})
        done.filtered('construction_request_id')._construction_post_dispatch_done()
        return res

    def _construction_post_dispatch_done(self):
        """Nota en el requerimiento al validar el despacho (M111-20 F)."""
        for picking in self:
            request = picking.construction_request_id
            moves = picking.move_ids.filtered(
                lambda m: m.state == 'done' and m.construction_request_line_id)
            if not moves:
                continue
            lines = request.line_ids.filtered(lambda l: not l.cancelled)
            open_lines = lines.filtered(lambda l: l.line_state != 'done')
            source = picking.location_id
            request.message_post_with_source(
                'al_construction_material_request.message_dispatch_done',
                render_values={
                    'picking': picking,
                    'source': source.warehouse_id.name or source.display_name,
                    'user': self.env.user.name,
                    'rows': [{
                        'product': move.product_id.display_name,
                        'qty': request._format_qty(move.quantity, move.product_uom),
                    } for move in moves],
                    'pending': len(open_lines),
                    'purchasing': len(open_lines.filtered(lambda l: l.line_state == 'purchasing')),
                    'to_dispatch': len(open_lines.filtered(lambda l: l.line_state != 'purchasing')),
                    'backorders': self.search([('backorder_id', '=', picking.id)]),
                },
                subtype_xmlid='mail.mt_note',
            )

    def _get_dispatch_slip_user(self):
        """«Despachado por» del vale: quien validó la transferencia o, si
        aún no se valida, quien imprime."""
        self.ensure_one()
        if self.state == 'done' and self.construction_validated_by_id:
            return self.construction_validated_by_id
        # Sin validar (M111-19 B): quien imprime o, según la compañía, en blanco.
        if self.company_id.construction_slip_unvalidated_signer == 'blank':
            return self.env['res.users']
        return self.env.user
