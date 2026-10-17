# -*- coding: utf-8 -*-
"""Aprobaciones con documento de origen y tramos en escalera (M19-07).

Lo nativo tiene un mínimo de aprobaciones por tipo y aprobadores en orden
uno por uno. Una solicitud de obra lleva sus aprobadores por tramo
(``construction_step``): el tramo activo es el primero que no está aprobado,
sus aprobadores están «Por aprobar» y los de los tramos siguientes
«En espera». Dentro del tramo, «basta uno» se cumple con una aprobación y
«todos» con una por cada usuario o grupo de la ruta (``construction_slots``).
Al cambiar el estado de la solicitud, el resultado vuelve al documento."""
from odoo import api, fields, models
from odoo.exceptions import UserError

from .construction_approval_route import CHANGE_TYPES


class ApprovalCategory(models.Model):
    _inherit = 'approval.category'

    approval_type = fields.Selection(
        selection_add=[('construction', 'Planificación de obra')])

    @api.model
    def _construction_category(self, company):
        """Tipo de aprobación de obra de la compañía (se crea la primera vez)."""
        # Quien envía un plan o un requerimiento no administra Aprobaciones:
        # el tipo de obra lo crea el sistema.
        Category_sudo = self.sudo()
        category = Category_sudo.search([
            ('approval_type', '=', 'construction'), ('company_id', '=', company.id)], limit=1)
        if not category:
            category = Category_sudo.create({
                'name': self.env._('Aprobación de obra'),
                'approval_type': 'construction',
                'company_id': company.id,
                'description': self.env._(
                    'Plan de recursos y requerimiento de obra (planificación de obra).'),
                'has_product': 'optional',
                'has_reference': 'optional',
                'approval_minimum': 1,
            })
        return category.sudo(False)


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    construction_res_model = fields.Char(string='Modelo de origen', readonly=True, index=True)
    construction_res_id = fields.Many2oneReference(
        string='Id de origen', model_field='construction_res_model', readonly=True, index=True)
    construction_origin_name = fields.Char(string='Documento de origen', readonly=True)
    construction_project_id = fields.Many2one(
        'project.project', string='Obra', readonly=True, index='btree_not_null')
    construction_amount = fields.Monetary(
        string='Exceso (monto)', currency_field='construction_currency_id', readonly=True)
    construction_currency_id = fields.Many2one(related='company_id.currency_id')
    construction_step_count = fields.Integer(
        string='Tramos', compute='_compute_construction_step', compute_sudo=True)
    construction_current_step = fields.Integer(
        string='Tramo actual', compute='_compute_construction_step', compute_sudo=True)
    construction_todo = fields.Char(
        string='Por aprobar', compute='_compute_construction_step', compute_sudo=True)
    construction_refuse_reason = fields.Text(string='Motivo del rechazo', readonly=True)
    # Último estado que se llevó al documento (para no repetirlo).
    construction_notified_status = fields.Char(readonly=True, copy=False)

    # ------------------------------------------------------------------
    # Tramos
    # ------------------------------------------------------------------
    def _construction_step_map(self):
        """{tramo: {'rule', 'slots', 'approvers'}}: un usuario que está en
        varios tramos tiene un solo aprobador (Odoo no repite usuarios en una
        solicitud) y su aprobación cuenta en cada uno."""
        self.ensure_one()
        steps = {}
        for approver in self.approver_ids:
            for step, rule, slot in approver._construction_slot_list():
                data = steps.setdefault(step, {
                    'rule': rule, 'slots': set(), 'approvers': approver.browse()})
                data['slots'].add(slot)
                data['approvers'] |= approver
        return steps

    def _construction_steps(self):
        self.ensure_one()
        return sorted(self._construction_step_map())

    def _construction_step_done(self, step, step_map=None):
        data = (step_map or self._construction_step_map())[step]
        approved = data['approvers'].filtered(lambda a: a.status == 'approved')
        if not approved:
            return False
        if data['rule'] == 'any':
            return True
        done = {slot for approver in approved
                for slot_step, _rule, slot in approver._construction_slot_list()
                if slot_step == step}
        return data['slots'] <= done

    def _construction_active_step(self):
        """Primer tramo sin aprobar (``None`` si todos lo están)."""
        self.ensure_one()
        step_map = self._construction_step_map()
        for step in sorted(step_map):
            if not self._construction_step_done(step, step_map):
                return step
        return None

    def _construction_active_approvers(self, user=None):
        """Aprobadores pendientes del tramo activo (de ``user``, si se da)."""
        self.ensure_one()
        active = self._construction_active_step()
        if active is None:
            return self.env['approval.approver']
        approvers = self._construction_step_map()[active]['approvers'].filtered(
            lambda a: a.status == 'pending')
        return approvers.filtered(lambda a: a.user_id == user) if user else approvers

    @api.depends('approver_ids.status', 'approver_ids.construction_slots')
    def _compute_construction_step(self):
        for request in self:
            steps = request.construction_res_model and request._construction_steps() or []
            request.construction_step_count = len(steps)
            active = steps and request._construction_active_step()
            request.construction_current_step = steps.index(active) + 1 if active in steps else 0
            todo = False
            if active in steps and request.request_status == 'pending':
                users = request._construction_active_approvers().user_id
                todo = self.env._(
                    'Tramo %(step)s de %(count)s: %(users)s', step=request.construction_current_step,
                    count=len(steps), users=', '.join(users.mapped('name')))
            request.construction_todo = todo

    def _construction_sync_steps(self):
        """Pone «Por aprobar» a quien tiene el tramo activo, «En espera» a
        quien solo está en los siguientes y cancela a quien ya no hace falta;
        las actividades siguen a los aprobadores pendientes."""
        for request in self.filtered('construction_res_model'):
            if request.request_status in ('new', 'cancel') or not request.date_confirmed:
                continue
            approvers = request.approver_ids
            if 'refused' not in approvers.mapped('status'):
                active = request._construction_active_step()
                for approver in approvers.filtered(lambda a: a.status != 'approved'):
                    steps = {step for step, _rule, _slot in approver._construction_slot_list()}
                    if active in steps:
                        status = 'pending'
                    elif active is None or max(steps) < active:
                        status = 'cancel'
                    else:
                        status = 'waiting'
                    if approver.status != status:
                        approver.status = status
            request._construction_refresh_activities()

    def _construction_refresh_activities(self):
        """Una actividad de aprobación por cada usuario con un aprobador
        pendiente; las demás se quitan."""
        activity_type = self.env.ref('approvals.mail_activity_data_approval')
        for request in self:
            pending = request.approver_ids.filtered(lambda a: a.status == 'pending')
            if request.request_status not in ('pending', 'new'):
                pending = pending.browse()
            activities = request.activity_ids.filtered(
                lambda a: a.activity_type_id == activity_type)
            activities.filtered(lambda a: a.user_id not in pending.user_id).unlink()
            have = activities.exists().user_id
            for approver in pending:
                if approver.user_id not in have:
                    approver._create_activity()
                    have |= approver.user_id

    @api.depends_context('uid')
    @api.depends('approver_ids.status')
    def _compute_user_status(self):
        # Un usuario puede estar en más de un tramo: cuenta el del tramo activo.
        managed = self.filtered('construction_res_model')
        super(ApprovalRequest, self - managed)._compute_user_status()
        for request in managed:
            mine = request.approver_ids.filtered(lambda a: a.user_id == self.env.user)
            request.user_status = mine[:1].status

    @api.depends('approver_ids.status', 'approver_ids.required')
    def _compute_request_status(self):
        managed = self.filtered('construction_res_model')
        super(ApprovalRequest, self - managed)._compute_request_status()
        for request in managed:
            old_status = request.request_status
            statuses = request.approver_ids.mapped('status')
            if not statuses:
                status = 'new'
            elif all(s == 'cancel' for s in statuses):
                status = 'cancel'
            elif 'refused' in statuses:
                status = 'refused'
            elif 'new' in statuses:
                status = 'new'
            elif request._construction_active_step() is None:
                status = 'approved'
            else:
                status = 'pending'
            request.request_status = status
            if request.id and status != old_status and status in ('approved', 'refused') \
                    and request.request_owner_id.partner_id:
                body = self.env._('Aprobada: %s.', request.construction_origin_name) \
                    if status == 'approved' else \
                    self.env._('Rechazada: %s.', request.construction_origin_name)
                request.message_notify(
                    body=body, subject='%s · %s' % (request.name, body),
                    partner_ids=request.request_owner_id.partner_id.ids)
        managed.filtered_domain(
            [('request_status', 'in', ['approved', 'refused', 'cancel'])])._cancel_activities()

    # ------------------------------------------------------------------
    # Acciones (el resultado vuelve al documento)
    # ------------------------------------------------------------------
    def action_confirm(self):
        for request in self.filtered('construction_res_model'):
            first = request._construction_steps()[0]
            # El primer tramo recibe las actividades; los demás esperan.
            request.approver_ids.filtered(
                lambda a: a.status == 'new' and first not in {
                    step for step, _rule, _slot in a._construction_slot_list()}
            ).sudo().write({'status': 'waiting'})
        return super().action_confirm()

    def action_approve(self, approver=None):
        managed = self.filtered('construction_res_model')
        if managed and not isinstance(approver, models.BaseModel):
            approver = self.env['approval.approver']
            for request in managed:
                approver |= request._construction_active_approvers(self.env.user)
            if not approver:
                raise UserError(self.env._(
                    'No tiene una aprobación pendiente en el tramo actual de %s.',
                    ', '.join(managed.mapped('name'))))
        elif managed and approver.filtered(lambda a: a.request_id.construction_res_model
                                           and a.status != 'pending'):
            raise UserError(self.env._('Todavía no le toca aprobar: espere al tramo anterior.'))
        res = super().action_approve(approver=approver)
        self._construction_after_change()
        return res

    def action_refuse(self, approver=None):
        res = super().action_refuse(approver=approver)
        self._construction_after_change()
        return res

    def action_withdraw(self, approver=None):
        res = super().action_withdraw(approver=approver)
        self._construction_after_change()
        return res

    def action_cancel(self):
        res = super().action_cancel()
        self._construction_after_change()
        return res

    def action_draft(self):
        res = super().action_draft()
        self._construction_after_change()
        return res

    def _action_force_approval(self):
        res = super()._action_force_approval()
        self._construction_after_change()
        return res

    def _construction_after_change(self):
        # Los tramos y el documento se mueven por la regla de la ruta, no por
        # los permisos de quien aprueba (que no edita el plan ni el
        # requerimiento en aprobación).
        managed_sudo = self.filtered('construction_res_model').sudo()
        if not managed_sudo:
            return
        managed_sudo._construction_sync_steps()
        for request in managed_sudo:
            status = request.request_status
            if status == request.construction_notified_status:
                continue
            request.construction_notified_status = status
            origin = request._construction_origin()
            if not origin:
                continue
            if status == 'approved':
                origin._construction_approval_granted(request)
            elif status in ('refused', 'cancel'):
                origin._construction_approval_refused(request)

    def action_construction_refuse(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Rechazar'),
            'res_model': 'construction.approval.refuse.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_approval_id': self.id},
        }

    def _construction_origin(self):
        self.ensure_one()
        if not self.construction_res_model or self.construction_res_model not in self.env:
            return None
        return self.env[self.construction_res_model].browse(self.construction_res_id).exists()

    def action_open_construction_origin(self):
        self.ensure_one()
        origin = self._construction_origin()
        if not origin:
            raise UserError(self.env._('El documento de origen ya no existe.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': origin._name,
            'res_id': origin.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
        }


class ApprovalApprover(models.Model):
    _inherit = 'approval.approver'

    construction_step = fields.Integer(
        string='Tramo', readonly=True, default=0, help='El primer tramo en que aprueba.')
    construction_route_id = fields.Many2one(
        'construction.approval.route', string='Ruta', readonly=True)
    # «tramo:regla:ruta-aprobador» por cada lugar de la ruta que cubre este
    # usuario (puede estar en varios tramos).
    construction_slots = fields.Char(readonly=True)

    def _construction_slot_list(self):
        result = []
        for token in (self.construction_slots or '').split(','):
            if token:
                step, rule, slot = token.split(':')
                result.append((int(step), rule, slot))
        return result


class ApprovalProductLine(models.Model):
    _inherit = 'approval.product.line'

    construction_change_type = fields.Selection(
        [item for item in CHANGE_TYPES if item[0] != 'all'], string='Cambio', readonly=True)
    construction_level = fields.Char(string='Nivel', readonly=True)
    construction_qty_budget = fields.Float(
        string='Presupuestado', digits='Product Unit', readonly=True,
        help='Saldo del plan para esta línea, sin contar este documento.')
    construction_qty_diff = fields.Float(
        string='Diferencia', digits='Product Unit', readonly=True)
    construction_diff_pct = fields.Float(string='Diferencia (%)', digits=(16, 2), readonly=True)
    construction_amount_diff = fields.Monetary(
        string='Diferencia (monto)', currency_field='construction_currency_id', readonly=True)
    construction_currency_id = fields.Many2one(related='company_id.currency_id')
