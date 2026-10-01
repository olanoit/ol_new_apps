# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import datetime, time

import pytz


from odoo import Command, _, fields, models
from odoo.tools import formatLang
from odoo.exceptions import UserError


class ConstructionMaterialRequest(models.Model):
    _inherit = 'construction.material.request'

    # ------------------------------------------------------------------
    # Procesar: división stock / compra (plan §6.4, decisión D4)
    # ------------------------------------------------------------------
    def action_process(self):
        """Divide cada línea entre lo libre en el almacén central (transferencia
        interna reservada) y el faltante (requerimiento de compra aprobado).

        Todo ocurre en la transacción de la llamada: si algo falla no queda
        nada a medias."""
        self._check_state(('approved',))
        for request in self:
            request.company_id._al_construction_ensure_setup()
            request._check_ready_to_submit()
            request._process_split()
        self.write({'state': 'in_progress'})
        return True

    def _get_free_qty_by_product(self, products):
        """Cantidad libre (UdM de cada producto) en el origen y sus
        sububicaciones, leída en lote como stock.move._prepare_procurement_qty."""
        self.ensure_one()
        products = products.with_context(location=self.location_src_id.id)
        return {product.id: product.free_qty for product in products}

    def _process_split(self):
        """Reparte cada línea entre stock y compra con el mismo algoritmo que
        la regla nativa «tomar de stock; si no hay, activar otra regla»
        (stock.move._prepare_procurement_qty): todo en la UdM del producto,
        lo ya asignado a líneas anteriores se descuenta por producto y solo
        la cantidad a comprar se convierte a la UdM de la línea (HALF-UP)."""
        self.ensure_one()
        lines = self.line_ids.filtered(lambda l: not l.cancelled)
        free_by_product = self._get_free_qty_by_product(lines.product_id)
        consumed = defaultdict(float)  # por producto, en su UdM
        for line in lines:
            product = line.product_id
            free = max(free_by_product.get(product.id, 0.0) - consumed[product.id], 0.0)
            to_purchase = max(line.product_uom_qty - free, 0.0)
            qty_to_purchase = product.uom_id._compute_quantity(
                to_purchase, line.product_uom_id, rounding_method='HALF-UP')
            line.write({
                'qty_available_at_approval': product.uom_id._compute_quantity(
                    free, line.product_uom_id, rounding_method='HALF-UP'),
                'qty_to_purchase': qty_to_purchase,
                'qty_to_dispatch': line.product_qty - qty_to_purchase,
            })
            consumed[product.id] += min(line.product_uom_qty, free)

        picking = self._create_dispatch_picking(
            lines.filtered(lambda l: not l.product_uom_id.is_zero(l.qty_to_dispatch)))
        shortages = picking and self._reserve_and_adjust(picking) or {}
        purchase_request, pending_picking = self._create_purchase_request(
            lines.filtered(lambda l: not l.product_uom_id.is_zero(l.qty_to_purchase)))
        self._post_split_message(lines, picking, purchase_request, pending_picking, shortages)

    # --- transferencia de lo disponible ---------------------------------
    def _date_required_datetime(self):
        """Fecha requerida como inicio del día en la zona del usuario (en UTC).
        Medianoche UTC se mostraría como el día anterior en Lima."""
        self.ensure_one()
        if not self.date_required:
            return fields.Datetime.now()
        tz = pytz.timezone(self.env.user.tz or 'America/Lima')
        local = tz.localize(datetime.combine(self.date_required, time.min))
        return local.astimezone(pytz.utc).replace(tzinfo=None)

    def _get_stock_reference(self):
        """Referencia de inventario del requerimiento, creada la primera vez
        (patrón de purchase.order._prepare_picking)."""
        self.ensure_one()
        if not self.stock_reference_id:
            self.stock_reference_id = self.env['stock.reference'].create({'name': self.name})
        return self.stock_reference_id

    def _prepare_picking_vals(self):
        self.ensure_one()
        picking_type = self.company_id.construction_dispatch_type_id
        vals = {
            'picking_type_id': picking_type.id,
            'location_id': self.location_src_id.id,
            'location_dest_id': self.location_dest_id.id,
            'origin': self.name,
            'construction_request_id': self.id,
            'project_id': self.project_id.id,
            'company_id': self.company_id.id,
            'scheduled_date': self._date_required_datetime(),
        }
        # GRE nativa (l10n_pe_edi_stock): traslado entre establecimientos de la
        # misma empresa. Sin dependencia dura.
        if 'l10n_pe_edi_reason_for_transfer' in self.env['stock.picking']._fields:
            vals['l10n_pe_edi_reason_for_transfer'] = '04'
        return vals

    def _prepare_move_vals(self, line, qty, picking, procure_method='make_to_stock'):
        # Campos como purchase.order.line._prepare_stock_move_vals.
        return {
            'product_id': line.product_id.id,
            'product_uom': line.product_uom_id.id,
            'product_uom_qty': qty,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
            'picking_id': picking.id,
            'picking_type_id': picking.picking_type_id.id,
            'company_id': self.company_id.id,
            'origin': self.name,
            'procure_method': procure_method,
            'date': picking.scheduled_date,
            'date_deadline': self.date_required and picking.scheduled_date,
            'warehouse_id': picking.picking_type_id.warehouse_id.id,
            # En 19.0 picking.reference_ids es related de los movimientos.
            'reference_ids': [Command.set(self._get_stock_reference().ids)],
            'sequence': line.sequence,
            'construction_request_line_id': line.id,
            'construction_analytic_distribution': line.analytic_distribution,
        }

    def _create_dispatch_picking(self, lines):
        self.ensure_one()
        if not lines:
            return self.env['stock.picking']
        picking = self.env['stock.picking'].create(self._prepare_picking_vals())
        self.env['stock.move'].create([
            self._prepare_move_vals(line, line.qty_to_dispatch, picking) for line in lines
        ])
        picking.action_confirm()
        picking.action_assign()
        return picking

    def _reserve_and_adjust(self, picking):
        """Condición de carrera: si se reservó menos de lo previsto (otro
        documento tomó el stock), la diferencia pasa a compra."""
        shortages = {}
        for move in picking.move_ids:
            line = move.construction_request_line_id
            reserved = move.quantity
            if move.product_uom.compare(reserved, move.product_uom_qty) >= 0:
                continue
            shortage = move.product_uom_qty - reserved
            shortages[line] = shortage
            line.write({
                'qty_to_dispatch': line.qty_to_dispatch - shortage,
                'qty_to_purchase': line.qty_to_purchase + shortage,
            })
            if move.product_uom.is_zero(reserved):
                move._action_cancel()
            else:
                move.product_uom_qty = reserved
        return shortages

    # --- requerimiento de compra del faltante ----------------------------
    def _prepare_purchase_request_vals(self):
        self.ensure_one()
        return {
            'origin': self.name,
            # Lo crea logística: la regla OCA solo deja editar al solicitante.
            'requested_by': self.env.user.id,
            'company_id': self.company_id.id,
            'picking_type_id': self.company_id.construction_pr_picking_type_id.id,
            'description': _('Obra %(project)s — solicitado por %(user)s',
                             project=self.project_id.display_name,
                             user=self.requested_by.name),
            'construction_request_id': self.id,
        }

    def _prepare_purchase_request_line_vals(self, line):
        return {
            'product_id': line.product_id.id,
            'name': line.product_id.display_name,
            'product_uom_id': line.product_uom_id.id,
            'product_qty': line.qty_to_purchase,
            'date_required': self.date_required or fields.Date.context_today(self),
            'analytic_distribution': line.analytic_distribution,
            'construction_request_line_id': line.id,
        }

    def _create_purchase_request(self, lines):
        self.ensure_one()
        if not lines:
            return self.env['purchase.request'], self.env['stock.picking']
        if not self.company_id.construction_pr_picking_type_id:
            raise UserError(_(
                'Configure la recepción de los requerimientos de compra en '
                'Inventario ▸ Ajustes ▸ Requerimientos de obra.'))
        vals = self._prepare_purchase_request_vals()
        vals['line_ids'] = [
            (0, 0, self._prepare_purchase_request_line_vals(line)) for line in lines]
        purchase_request = self.env['purchase.request'].create(vals)
        # Ya se aprobó el requerimiento de obra: no se vuelve a aprobar
        # (plan §F1.3, punto 6).
        purchase_request.button_approved()
        central_lines = lines.filtered(lambda l: l.supply_mode == 'central')
        pending_picking = self.env['stock.picking']
        if central_lines:
            pending_picking = self._create_pending_purchase_picking(
                central_lines, purchase_request)
        return purchase_request, pending_picking

    def _create_pending_purchase_picking(self, lines, purchase_request):
        """Vía almacén central: movimiento central → obra que espera la compra.
        El asistente de OCA copia ``move_dest_ids`` a la línea de OC y, al
        recibir, este movimiento reserva exactamente lo recibido."""
        vals = self._prepare_picking_vals()
        picking = self.env['stock.picking'].create(vals)
        pr_line_by_line = {
            pr_line.construction_request_line_id: pr_line
            for pr_line in purchase_request.line_ids
        }
        move_vals = []
        for line in lines:
            vals = self._prepare_move_vals(
                line, line.qty_to_purchase, picking, procure_method='make_to_order')
            vals['created_purchase_request_line_id'] = pr_line_by_line[line].id
            move_vals.append(vals)
        moves = self.env['stock.move'].create(move_vals)
        # Sin abastecimiento: la compra la gestiona el requerimiento de compra.
        moves._action_confirm(merge=False, create_proc=False)
        return picking

    def _format_qty(self, value, uom):
        return f'{formatLang(self.env, value, digits=2)} {uom.name}'

    def _post_split_message(self, lines, picking, purchase_request, pending_picking, shortages):
        modes = dict(self.env['construction.material.request.line']._fields['supply_mode']
                     ._description_selection(self.env))
        rows = [{
            'product': line.product_id.display_name,
            'ordered': self._format_qty(line.product_qty, line.product_uom_id),
            'available': self._format_qty(line.qty_available_at_approval, line.product_uom_id),
            'dispatch': not line.product_uom_id.is_zero(line.qty_to_dispatch),
            'dispatch_txt': self._format_qty(line.qty_to_dispatch, line.product_uom_id),
            'purchase': not line.product_uom_id.is_zero(line.qty_to_purchase),
            'purchase_txt': self._format_qty(line.qty_to_purchase, line.product_uom_id),
            'mode': modes[line.supply_mode].lower(),
        } for line in lines]
        self.message_post_with_source(
            'al_construction_material_request.message_process_result',
            render_values={
                'rows': rows,
                'picking': picking.filtered(lambda p: p.state != 'cancel'),
                'pending_picking': pending_picking,
                'purchase_request': purchase_request,
                'shortages': ', '.join(
                    f'{line.product_id.display_name} ({self._format_qty(short, line.product_uom_id)})'
                    for line, short in shortages.items()),
            },
            subtype_xmlid='mail.mt_note',
        )

    # ------------------------------------------------------------------
    # Cierre y cancelación
    # ------------------------------------------------------------------
    def _check_done(self):
        """Pasa a «Hecho» cuando todo lo pedido está en la obra."""
        for request in self.filtered(lambda r: r.state == 'in_progress'):
            open_lines = request.line_ids.filtered(lambda l: not l.cancelled)
            if open_lines and all(l.line_state == 'done' for l in open_lines):
                request.state = 'done'

    def action_cancel(self):
        self._check_state(('draft', 'to_approve', 'approved', 'rejected', 'in_progress'))
        for request in self.filtered(lambda r: r.state == 'in_progress'):
            request._cancel_pending_supply()
        return super().action_cancel()

    def _cancel_pending_supply(self):
        """Cancela movimientos no hechos y líneas de compra sin OC. Lo ya
        despachado o ya pedido al proveedor se conserva."""
        self.ensure_one()
        moves = self.line_ids.move_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
        moves._action_cancel()
        # La regla OCA solo deja editar el PR a quien lo creó (el usuario de
        # logística que procesó); cualquier otro de logística puede cancelar.
        purchase_requests_sudo = self.purchase_request_ids.sudo()
        pr_lines = purchase_requests_sudo.line_ids
        with_po = pr_lines.filtered('purchase_lines')
        (pr_lines - with_po).filtered(lambda l: not l.cancelled).do_cancel()
        purchase_requests_sudo.check_auto_reject()
        for line in self.line_ids:
            if line.product_uom_id.compare(line.qty_received_on_site, line.product_qty) < 0:
                line.cancelled = True
        if with_po:
            self.message_post(body=_(
                'Hay compras ya convertidas en OC que no se cancelaron: %s',
                ', '.join(with_po.purchase_lines.order_id.mapped('name'))))
