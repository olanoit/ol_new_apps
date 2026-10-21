# -*- coding: utf-8 -*-
"""Vale de despacho para pegar en el bulto (paquete 1.11, M111-07).

Muestra todo el requerimiento y, por material, cuánto se despachó antes,
cuánto va en el bulto que acompaña y cuánto falta, con la situación en
palabras. No lleva precios ni stock interno."""
from odoo import fields, models

OPEN_MOVE_STATES = ('draft', 'waiting', 'confirmed', 'partially_available', 'assigned')


class ConstructionMaterialRequest(models.Model):
    _inherit = 'construction.material.request'

    def _get_dispatch_slip(self, picking=None):
        """{'rows': [...], 'summary': texto, 'date': fecha de despacho} del
        vale; ``picking`` es la transferencia que acompaña (o ninguna, al
        imprimirlo desde el requerimiento)."""
        self.ensure_one()
        picking = picking or self.env['stock.picking']
        rows = []
        in_bundle = pending_count = 0
        pending_kinds = {}
        for index, line in enumerate(self.line_ids, start=1):
            row = line._get_dispatch_slip_row(picking)
            row['index'] = index
            rows.append(row)
            if row['kind'] == 'cancel':
                continue
            if row['in_bundle']:
                in_bundle += 1
            if row['pending']:
                pending_count += 1
                pending_kinds[row['kind']] = pending_kinds.get(row['kind'], 0) + 1
        active = len([row for row in rows if row['kind'] != 'cancel'])
        labels = {'purchase': self.env._('en compra'), 'reserved': self.env._('por despachar'),
                  'pending': self.env._('sin despacho')}
        parts = []
        if picking:
            parts.append(self.env._('En este bulto: %(count)s de %(total)s materiales.',
                                    count=in_bundle, total=active))
        if pending_count:
            detail = ', '.join('%s %s' % (count, labels[kind]) if len(pending_kinds) > 1
                               else labels[kind]
                               for kind, count in sorted(pending_kinds.items()))
            parts.append(self.env._('Pendientes: %(count)s (%(detail)s).',
                                    count=pending_count, detail=detail))
        else:
            parts.append(self.env._('Sin pendientes.'))
        date = picking.date_done if picking and picking.state == 'done' \
            else fields.Datetime.now()
        return {'rows': rows, 'summary': ' '.join(parts), 'date': date}


class ConstructionMaterialRequestLine(models.Model):
    _inherit = 'construction.material.request.line'

    def _get_dispatch_slip_row(self, picking):
        """Cifras de la línea en el vale, en su unidad. ``kind``: done,
        bundle (este bulto la cierra), reserved, purchase, pending o
        cancel."""
        self.ensure_one()
        uom = self.product_uom_id

        def to_line_uom(moves):
            return sum(move.product_uom._compute_quantity(
                move.quantity, uom, rounding_method='HALF-UP') for move in moves) \
                if uom else 0.0

        moves = self.move_ids.filtered(lambda m: m.state != 'cancel')
        bundle_moves = moves.filtered(lambda m: m.picking_id == picking) if picking \
            else moves.browse()
        # Lo preparado si aún no se valida, lo hecho si ya se validó.
        in_bundle = to_line_uom(bundle_moves) if picking else 0.0
        delivered = self.qty_received_on_site if self.supply_mode == 'direct' \
            else self.qty_dispatched
        before = delivered - (in_bundle if picking and picking.state == 'done' else 0.0)
        if uom and uom.compare(before, 0.0) < 0:
            before = 0.0
        pending = max(self.product_qty - before - in_bundle, 0.0)
        if uom and uom.is_zero(pending):
            pending = 0.0
        row = {
            'line': self, 'qty': self.product_qty, 'before': before,
            'in_bundle': in_bundle if uom and not uom.is_zero(in_bundle) else 0.0,
            'pending': pending,
        }
        if self.cancelled:
            row.update(kind='cancel', situation=self.env._('Cancelado'), pending=0.0)
            return row
        if not pending:
            if row['in_bundle']:
                row.update(kind='bundle', situation=self.env._('Va completo en este bulto'))
            else:
                row.update(kind='done', situation=self.env._('Completo'))
            return row
        others = moves.filtered(lambda m: m.state in OPEN_MOVE_STATES) - bundle_moves
        reserved = others.filtered(lambda m: m.state in ('assigned', 'partially_available'))
        if reserved:
            row.update(kind='reserved', situation=self.env._(
                'Por despachar · %s', ', '.join(reserved.picking_id.mapped('name'))))
            return row
        purchase_lines = self.purchase_request_line_ids.filtered(
            lambda l: l.request_state != 'rejected')
        if purchase_lines:
            text = self.env._('En compra · %s', ', '.join(
                purchase_lines.request_id.mapped('name')))
            orders = purchase_lines.purchase_lines.filtered(
                lambda l: l.order_id.state != 'cancel')
            for order_line in orders.sorted('date_planned')[:1]:
                text += ' · ' + self.env._('OC %s', order_line.order_id.name)
                if order_line.date_planned:
                    text += ' · ' + self.env._(
                        'llega %s', order_line.date_planned.strftime('%d/%m'))
            row.update(kind='purchase', situation=text)
            return row
        if others:
            row.update(kind='reserved', situation=self.env._(
                'Por despachar · %s', ', '.join(others.picking_id.mapped('name'))))
            return row
        row.update(kind='pending', situation=self.env._('Pendiente'))
        return row
