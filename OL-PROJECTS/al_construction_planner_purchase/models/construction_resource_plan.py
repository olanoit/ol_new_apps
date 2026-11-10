# -*- coding: utf-8 -*-
from odoo import Command, models
from odoo.exceptions import RedirectWarning, UserError


class ConstructionResourcePlan(models.Model):
    _inherit = 'construction.resource.plan'

    def _write_approved(self):
        res = super()._write_approved()
        # Paquete 1.16, M114-01: después de pasar las asignaciones de la
        # versión anterior, el plan recoge lo pedido sin él.
        for plan in self.filtered(lambda p: p.state == 'approved'):
            plan._construction_regularize_requests()
        return res

    def _construction_regularize_requests(self):
        """Asigna al plan las líneas de los requerimientos de obra de la obra
        (en aprobación, aprobados, en proceso o hechos) que no tienen asignación
        en él: los pedidos sin plan y los que quedaron fuera de una versión
        anterior. Lo que no calza con ninguna línea del plan queda «fuera de
        plan». Paquete 1.17, M117-10: un plan suele aprobarse con requerimientos
        todavía «En aprobación»."""
        self.ensure_one()
        # Lo corre el sistema al aprobar: quien aprueba el plan puede no tener
        # permiso sobre los requerimientos de obra ni sus asignaciones.
        RequestLine_sudo = self.env['construction.material.request.line'].sudo()
        lines_sudo = RequestLine_sudo.search([
            ('request_id.project_id', '=', self.project_id.id),
            ('request_id.request_type', '=', 'site'),
            ('request_id.state', 'in', ('to_approve', 'approved', 'in_progress', 'done')),
            ('cancelled', '=', False), ('product_id', '!=', False)])
        lines_sudo = lines_sudo.filtered(lambda l: not l.construction_allocation_ids.filtered(
            lambda a: a.plan_line_id.plan_id == self))
        if not lines_sudo:
            return
        result = self._construction_assign_request_lines(lines_sudo)
        self.message_post(body=self.env._(
            'Pedidos sin plan regularizados: %(requests)s requerimiento(s) revisado(s), '
            '%(assigned)s línea(s) asignada(s) y %(unplanned)s fuera de plan.',
            requests=len(lines_sudo.request_id), assigned=len(result['assigned']),
            unplanned=len(result['unplanned'])))

    def _construction_assign_request_lines(self, lines_sudo):
        """Reparte ``lines_sudo`` entre las líneas de este plan y registra el
        exceso con el motivo «Regularización de pedido sin plan».

        :return: ``{'assigned': líneas, 'unplanned': líneas}``"""
        self.ensure_one()
        Allocation_sudo = self.env['construction.resource.plan.allocation'].sudo()
        lines_sudo.request_id.filtered(lambda r: r.construction_plan_id != self).write(
            {'construction_plan_id': self.id})
        assigned = unplanned = self.env['construction.material.request.line']
        exceed_values = []
        plan_sudo = self.sudo()
        for line_sudo in lines_sudo:
            plan_lines = line_sudo._construction_candidate_plan_lines(plan_sudo)
            if not plan_lines:
                unplanned |= line_sudo
                continue
            # Las asignaciones de versiones anteriores quedan como historia.
            # M117-11: lo pedido neto de lo que ya volvió de la obra.
            net = line_sudo._construction_net_qty()
            _balance, _tolerance, excess = plan_lines._supply_check(net)
            shares = plan_lines._supply_split(net)
            Allocation_sudo.create([{
                'plan_line_id': plan_line.id,
                'kind': 'material_request',
                'material_request_line_id': line_sudo.id,
                'qty_allocated': qty,
            } for plan_line, qty in shares.items() if not plan_line.product_uom_id.is_zero(qty)])
            assigned |= line_sudo
            if line_sudo.product_id.uom_id.compare(excess, 0.0) > 0:
                plan_line = plan_lines._supply_sorted()[-1:]
                qty = line_sudo.product_id.uom_id._compute_quantity(
                    excess, line_sudo.product_uom_id)
                exceed_values.append({
                    'kind': 'excess', 'plan_id': self.id, 'project_id': self.project_id.id,
                    'company_id': self.company_id.id, 'plan_line_id': plan_line.id,
                    'task_id': (line_sudo.task_id or line_sudo.request_id.task_id
                                or plan_line.task_id).id,
                    'product_id': line_sudo.product_id.id, 'qty': qty,
                    'uom_id': line_sudo.product_uom_id.id,
                    'amount': qty * (plan_line.price_unit_planned or 0.0),
                    'reason': self.env._('Regularización de pedido sin plan'),
                    'document': line_sudo.request_id.name,
                    'res_model': line_sudo.request_id._name, 'res_id': line_sudo.request_id.id,
                })
        if exceed_values:
            self.env['construction.exceed.log'].sudo()._log(exceed_values)
        if assigned:
            Allocation_sudo._refresh_for_documents('material_request_line_id', assigned)
        return {'assigned': assigned, 'unplanned': unplanned}

    def action_open_price_wizard(self):
        self.ensure_one()
        self._check_draft()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Aplicar costo'),
            'res_model': 'construction.plan.price.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_plan_id': self.id},
        }

    def action_open_price_group_wizard(self, scope='unpriced', lines=None):
        """«Aplicar costo» por grupo (paquete 1.18, M118-04): desde el plan,
        con las líneas sin costo o con la selección de la lista."""
        self.ensure_one()
        self._check_draft()
        context = {'default_plan_id': self.id, 'default_scope': scope,
                   'dialog_size': 'extra-large'}
        if lines:
            context['default_selected_line_ids'] = [Command.set(lines.ids)]
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Aplicar costo'),
            'res_model': 'construction.plan.price.group.wizard',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': context,
        }

    def action_request_approval(self):
        """M118-04, punto 5: si lo único que falta es el costo, el aviso dice
        cuántos productos faltan y abre «Aplicar costo» con ese filtro. Con
        otros motivos, el mensaje de siempre con todos."""
        for plan in self.filtered(lambda p: p.state == 'draft'):
            unpriced = plan.line_ids.filtered(
                lambda l: l.line_state != 'cancel' and l.qty_planned and l.product_id
                and not l.price_unit_planned and not l.is_client_supply)
            if unpriced and len(plan._get_approval_issues()) == 1:
                action = plan.action_open_price_group_wizard()
                raise RedirectWarning(self.env._(
                    'El plan %(plan)s no se puede enviar a aprobación. Líneas sin costo: '
                    '%(lines)s de %(products)s productos. Decida su costo con «Aplicar costo».',
                    plan=plan.display_name, lines=len(unpriced),
                    products=len(unpriced.product_id)),
                    action, self.env._('Aplicar costo'))
        return super().action_request_approval()


class ConstructionResourcePlanLine(models.Model):
    _inherit = 'construction.resource.plan.line'

    def action_open_price_wizard(self):
        """«Aplicar costo» desde la lista de líneas: con un solo producto, el
        asistente de siempre; con varios, el de grupo (paquete 1.18, M118-04)."""
        plan = self.plan_id
        if len(plan) != 1 or not all(self.mapped('product_id')):
            raise UserError(self.env._(
                'Seleccione líneas de un solo plan y con producto.'))
        if len(self.product_id) > 1:
            return plan.action_open_price_group_wizard('selection', self)
        action = plan.action_open_price_wizard()
        action['context'] = {
            'default_plan_id': plan.id,
            'default_product_id': self.product_id.id,
            'default_line_ids': [Command.set(self.ids)],
        }
        return action
