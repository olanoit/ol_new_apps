# -*- coding: utf-8 -*-
"""Requerimiento de obra en Aprobaciones (M19-03 y M19-07).

Sin cambios frente al plan va directo al almacén. Un material que no está en
el plan es un cambio de material; más de lo que queda en el plan (o repetir
lo ya pedido de un nivel y sub etapa) es un cambio de cantidad. Cada cambio
sigue su escalera de la tabla de rutas; con Aprobaciones, la política «Solo
alerta» de materiales ya no deja pasar estos cambios.

El requerimiento interno (paquete 1.11, M111-21) no tiene plan ni rutas: con
Aprobaciones lo aprueba el jefe del departamento de quien pide o, sin jefe,
el grupo de la compañía (M111-19 C), igual que con los niveles."""
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

    def _construction_submit_approval(self):
        internal = self.filtered(lambda r: r.request_type == 'internal')
        submitted = super(ConstructionMaterialRequest, self - internal)._construction_submit_approval()
        for request in internal:
            users = request._construction_internal_approvers()
            if not users:
                continue
            # Un solo tramo, «basta uno», con el jefe o con el grupo.
            approver_values = [{
                'user_id': user.id,
                'construction_step': 1,
                'construction_slots': '1:any:internal',
                'status': 'new',
            } for index, user in enumerate(users)]
            category = self.env['approval.category']._construction_category(request.company_id)
            summary = self.env._(
                '%(doc)s · requerimiento interno de %(user)s · %(approver)s.',
                doc=request.display_name, user=request.requested_by.name,
                approver=request.construction_department_manager_id.name
                or request.company_id.construction_internal_fallback_group_id.name)
            request._construction_open_approval(
                category, approver_values, request._construction_approval_info(), summary)
            submitted |= request
        # Regla 7.4 con Aprobaciones (paquete 1.16, M116-03): lo que no tiene
        # tramo pasa al jefe de la obra, igual que con la validación por niveles.
        for request in self - internal - submitted:
            manager = request._construction_site_manager_review()
            if not manager:
                continue
            category = self.env['approval.category']._construction_category(request.company_id)
            summary = self.env._(
                '%(doc)s · obra %(project)s · sin regla de aprobación: jefe de la obra %(user)s.',
                doc=request.display_name, project=request.project_id.display_name,
                user=manager.name)
            request._construction_open_approval(category, [{
                'user_id': manager.id, 'sequence': 1000, 'construction_step': 1,
                'construction_slots': '1:any:site_manager', 'status': 'new',
            }], request._construction_approval_info(), summary)
            submitted |= request
        return submitted

    def _construction_internal_approvers(self):
        """Quien aprueba el interno: el jefe del departamento o, sin jefe,
        los usuarios internos activos del grupo de la compañía, nunca quien
        pide. Vacío: se aprueba al solicitarlo."""
        self.ensure_one()
        manager = self.construction_department_manager_id
        if manager:
            return manager - self.env.user
        group = self.company_id.construction_internal_fallback_group_id
        # Los usuarios del grupo los lee el sistema: quien pide no ve grupos.
        group_sudo = group.sudo()
        return group_sudo.all_user_ids.filtered(
            lambda u: u.active and not u.share and self.company_id in u.company_ids
        ).sudo(False) - self.env.user

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
        # Paquete 1.16, M116-03 (M114-02): sin plan, con «Material fuera del
        # plan», cada línea es material fuera del plan y sigue su tramo.
        no_plan = not plan and self._construction_no_plan_review()
        if not plan and not no_plan:
            return {'values': values, 'lines': lines, 'amount': total, 'reason': ''}
        # El residente no ve el plan: el saldo y los precios se leen sin sus
        # permisos, solo para armar la solicitud.
        plan_sudo = plan.sudo()
        for line in self.line_ids.filtered(lambda l: not l.cancelled and l.product_id):
            line_sudo = line.sudo()
            uom = line.product_id.uom_id
            plan_lines = line_sudo._construction_candidate_plan_lines(plan_sudo) \
                if plan else plan_sudo.line_ids
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
                # Paquete 1.11, M111-06: las cifras son las de todo el material
                # bajo el nivel y la etapa del pedido, aunque el pedido ya
                # tenga asignada solo una parte del plan.
                scope = line_sudo._construction_scope_plan_lines(plan_sudo) or plan_lines
                planned = sum(pl._qty_to_product_uom(pl.qty_planned) for pl in scope)
                budget = sum(scope._supply_balance(
                    line_sudo.construction_allocation_ids).values())
                requested_before = planned - budget
                percent = diff / planned * 100 if planned else 100.0
                price = sum(scope.mapped('amount_planned')) / planned if planned else 0.0
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
        reason = self.construction_exceed_reason or ''
        if no_plan and values:
            reason = '\n'.join(filter(None, [
                self.env._('Material fuera del plan (obra sin plan).'), reason]))
        return {'values': values, 'lines': lines, 'amount': total, 'reason': reason,
                'extra_vals': {'construction_no_plan': True} if no_plan else {}}

    def _construction_no_plan_review(self):
        """Requerimiento de obra sin plan vigente que la compañía revisa como
        material fuera del plan (M116-03)."""
        self.ensure_one()
        return self.request_type == 'site' and bool(self.project_id) \
            and self.company_id.construction_site_request_without_rule == 'out_of_plan'

    def _construction_site_manager_review(self):
        """Regla 7.4 con la aplicación Aprobaciones: sin cambios que aprobar,
        el requerimiento de obra pasa al jefe de la obra si la compañía lo pide
        (con la validación por niveles lo hace la regla de respaldo)."""
        self.ensure_one()
        manager = self.project_manager_id
        return manager if (
            self.request_type == 'site' and manager and manager != self.env.user
            and self.company_id.construction_site_request_without_rule == 'manager') \
            else self.env['res.users']

    def action_draft(self):
        self.filtered(lambda r: r.state == 'to_approve')._construction_cancel_open_approvals()
        return super().action_draft()

    def action_cancel(self):
        self.filtered(lambda r: r.state == 'to_approve')._construction_cancel_open_approvals()
        return super().action_cancel()
