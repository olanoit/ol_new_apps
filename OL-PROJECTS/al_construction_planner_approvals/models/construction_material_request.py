# -*- coding: utf-8 -*-
"""Requerimiento de obra en Aprobaciones (M19-03 y M19-07).

Sin cambios frente al plan va directo al almacén. Un material que no está en
el plan es un cambio de material; más de lo que queda en el plan (o repetir
lo ya pedido de un nivel y sub etapa) es un cambio de cantidad. Cada cambio
sigue su escalera de la tabla de rutas; con Aprobaciones, la política «Solo
alerta» de materiales ya no deja pasar estos cambios."""
from odoo import models


class ConstructionMaterialRequest(models.Model):
    _name = 'construction.material.request'
    _inherit = ['construction.material.request', 'construction.approval.mixin']

    _construction_approval_document_type = 'material_request'

    def _compute_need_validation(self):
        # Con Aprobaciones no se piden revisiones por niveles.
        approvals = self._construction_uses_approvals()
        super(ConstructionMaterialRequest, self - approvals)._compute_need_validation()
        approvals.need_validation = False

    def action_request_approval(self):
        drafts = self.filtered(lambda r: r.state == 'draft')
        drafts._construction_set_approval_engine()
        if drafts._construction_uses_approvals():
            # El exceso no pasa por el asistente de la política: va a la ruta.
            self = self.with_context(construction_exceed_checked=True)
        return super().action_request_approval()

    def _write_approved(self):
        if not self.env.context.get('construction_approval_granted'):
            submitted = self._construction_uses_approvals()._construction_submit_approval()
            return super(ConstructionMaterialRequest, self - submitted)._write_approved()
        res = super()._write_approved()
        # Con Aprobaciones el exceso quedó aprobado por la ruta, sea cual sea
        # la política de materiales.
        exceeded = self.filtered(lambda r: r.construction_exceed_state == 'exceeded')
        if exceeded:
            exceeded.with_context(al_construction_approving=True).write(
                {'construction_exceed_state': 'approved'})
            exceeded._construction_log_exceed()
        return res

    def _construction_approval_info(self):
        self.ensure_one()
        values, lines, total = {}, [], 0.0
        plan = self.construction_plan_id
        if not plan:
            return {'values': values, 'lines': lines, 'amount': total, 'reason': ''}
        # El residente no ve el plan: el saldo y los precios se leen sin sus
        # permisos, solo para armar la solicitud.
        plan_sudo = plan.sudo()
        for line in self.line_ids.filtered(lambda l: not l.cancelled and l.product_id):
            line_sudo = line.sudo()
            uom = line.product_id.uom_id
            plan_lines = line_sudo._construction_candidate_plan_lines(plan_sudo)
            # Cifras de la solicitud (paquete 1.10, M110-08), en la unidad del
            # producto: presupuestado, ya pedido por otros documentos y saldo.
            planned = requested_before = budget = 0.0
            if not plan_lines:
                change = 'material'
                diff, percent = line.product_uom_qty, 100.0
                price = line.product_id.with_company(self.company_id).standard_price
            else:
                excess = line_sudo._construction_get_excess()
                if excess > 0:
                    # Con saldo negativo todo lo pedido es exceso, pero nunca
                    # más que lo pedido.
                    diff = min(line.product_uom_qty, excess)
                elif line_sudo._construction_is_repeat():
                    diff = line.product_uom_qty
                else:
                    continue
                change = 'quantity'
                planned = sum(pl._qty_to_product_uom(pl.qty_planned) for pl in plan_lines)
                budget = sum(plan_lines._supply_balance(
                    line_sudo.construction_allocation_ids).values())
                requested_before = planned - budget
                percent = diff / planned * 100 if planned else 100.0
                price = sum(plan_lines.mapped('amount_planned')) / planned if planned else 0.0
            amount = diff * price
            total += amount
            bucket = values.setdefault(change, {'percent': 0.0, 'amount': 0.0})
            bucket['percent'] = max(bucket['percent'], percent)
            bucket['amount'] += amount
            lines.append({
                'product_id': line.product_id.id,
                'description': line.construction_level_label or line.product_id.display_name,
                'quantity': uom._compute_quantity(line.product_uom_qty, line.product_uom_id),
                'product_uom_id': line.product_uom_id.id,
                'construction_change_type': change,
                'construction_level': line.construction_level_label,
                'construction_qty_planned': uom._compute_quantity(planned, line.product_uom_id),
                'construction_qty_requested_before': uom._compute_quantity(
                    requested_before, line.product_uom_id),
                'construction_qty_budget': uom._compute_quantity(budget, line.product_uom_id),
                'construction_qty_diff': uom._compute_quantity(diff, line.product_uom_id),
                'construction_diff_pct': percent,
                'construction_amount_diff': amount,
            })
        if values:
            values['all'] = {
                'percent': max(v['percent'] for v in values.values()),
                'amount': sum(v['amount'] for v in values.values()),
            }
        return {'values': values, 'lines': lines, 'amount': total,
                'reason': self.construction_exceed_reason or ''}

    def action_draft(self):
        self.filtered(lambda r: r.state == 'to_approve')._construction_cancel_open_approvals()
        return super().action_draft()

    def action_cancel(self):
        self.filtered(lambda r: r.state == 'to_approve')._construction_cancel_open_approvals()
        return super().action_cancel()
