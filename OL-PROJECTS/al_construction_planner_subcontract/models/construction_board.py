# -*- coding: utf-8 -*-
"""Contratas en el tablero de obra, la tarea de obra y la sección Obra del
tablero del proyecto (requerimiento CREVAL v1.0, capítulo 4)."""
from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    construction_open_order_count = fields.Integer(
        string='Órdenes de contrata abiertas', compute='_compute_construction_contract_board')
    construction_settlement_to_approve_count = fields.Integer(
        string='Valorizaciones por aprobar', compute='_compute_construction_contract_board')
    construction_deduction_pending_count = fields.Integer(
        string='Deductivos pendientes', compute='_compute_construction_contract_board')

    def _compute_construction_contract_board(self):
        # sudo: los contadores del tablero los ve quien ejecuta la obra aunque
        # no administre compras.
        orders = dict(self.env['purchase.order'].sudo()._read_group(
            [('construction_project_id', 'in', self.ids), ('construction_is_service_order', '=', True),
             ('state', 'in', ('draft', 'sent', 'to approve', 'purchase')),
             ('construction_closed', '=', False)], ['construction_project_id'], ['__count']))
        settlements = dict(self.env['construction.contract.settlement']._read_group(
            [('project_id', 'in', self.ids), ('state', 'in', ('submitted', 'validated'))],
            ['project_id'], ['__count']))
        deductions = dict(self.env['construction.contract.deduction']._read_group(
            [('project_id', 'in', self.ids), ('state', '=', 'pending')], ['project_id'],
            ['__count']))
        for project in self:
            project.construction_open_order_count = orders.get(project, 0)
            project.construction_settlement_to_approve_count = settlements.get(project, 0)
            project.construction_deduction_pending_count = deductions.get(project, 0)

    def action_construction_assign_contract(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'al_construction_planner_subcontract.action_plan_contract_wizard')
        action['context'] = self._construction_board_context()
        return action

    def action_construction_view_contract_orders(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'al_construction_planner_subcontract.action_construction_service_orders')
        action['domain'] = [('construction_is_service_order', '=', True),
                            ('construction_project_id', '=', self.id)]
        return action

    def action_construction_view_settlements_to_approve(self):
        action = self.action_view_construction_settlements()
        action['context'] = dict(action.get('context') or {}, search_default_submitted=1,
                                 search_default_validated=1)
        return action

    def action_construction_view_deductions(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'al_construction_planner_subcontract.action_construction_contract_deduction')
        action['domain'] = [('project_id', '=', self.id)]
        action['context'] = {'search_default_pending': 1}
        return action

    def action_construction_view_contract_summary(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'al_construction_planner_subcontract.action_construction_contract_summary_report')
        action['domain'] = [('project_id', '=', self.id)]
        return action

    def _construction_stat_buttons(self):
        buttons = super()._construction_stat_buttons()
        user = 'al_construction_planner.group_planner_user'
        buttons += [
            (3, user, {'icon': 'handshake-o', 'text': self.env._('Asignar contrata'),
                       'number': '', 'action_type': 'object',
                       'action': 'action_construction_assign_contract',
                       'show': bool(self.construction_board_plan_id)}),
            (7, user, {'icon': 'file-text-o', 'text': self.env._('Órdenes de contrata'),
                       'number': self.construction_open_order_count, 'action_type': 'object',
                       'action': 'action_construction_view_contract_orders', 'show': True}),
            (8, user, {'icon': 'calendar-check-o', 'text': self.env._('Valorizaciones de contrata'),
                       'number': self.construction_settlement_to_approve_count,
                       'action_type': 'object',
                       'action': 'action_construction_view_settlements_to_approve', 'show': True}),
            (9, user, {'icon': 'minus-circle', 'text': self.env._('Deductivos'),
                       'number': self.construction_deduction_pending_count,
                       'action_type': 'object', 'action': 'action_construction_view_deductions',
                       'show': True}),
        ]
        return buttons


class ConstructionTaskExecuteWizard(models.TransientModel):
    _inherit = 'construction.task.execute.wizard'

    def action_assign_contract(self):
        return self._launch('al_construction_planner_subcontract.action_plan_contract_wizard')

    def action_register_deduction(self):
        """Deductivo de una orden de contrata de la tarea (o de la obra)."""
        self.ensure_one()
        task = self.task_id
        # sudo: solo para proponer la orden; quien registra no lee compras.
        orders = self.env['purchase.order'].sudo().search([
            ('construction_project_id', '=', task.project_id.id),
            ('construction_is_service_order', '=', True), ('state', '=', 'purchase'),
            ('construction_closed', '=', False)])
        order = orders.filtered(lambda o: task in o.order_line.construction_task_id)[:1] \
            or orders[:1]
        return {
            'type': 'ir.actions.act_window', 'name': self.env._('Registrar deductivo'),
            'res_model': 'construction.contract.deduction', 'view_mode': 'form',
            'target': 'current',
            'context': {'default_purchase_order_id': order.id, 'default_task_id': task.id},
        }
