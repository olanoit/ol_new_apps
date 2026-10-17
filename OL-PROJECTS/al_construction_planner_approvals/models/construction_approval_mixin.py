# -*- coding: utf-8 -*-
"""Documento de obra que se aprueba en la aplicación Aprobaciones (M19-07).

El documento sigue con su flujo (borrador, en aprobación, aprobado): en lugar
de pedir las revisiones por niveles, al enviarlo se busca su escalera en la
tabla de rutas y se crea la solicitud con sus líneas. Sin tramos que
apliquen, se aprueba como antes. El resultado de la solicitud vuelve al
documento: aprobada lo libera y rechazada lo devuelve a borrador con el
motivo."""
from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError

from .res_company import APPROVAL_ENGINES


class ConstructionApprovalMixin(models.AbstractModel):
    _name = 'construction.approval.mixin'
    _description = 'Documento de obra aprobado en Aprobaciones'

    # Tipo de documento en la tabla de rutas.
    _construction_approval_document_type = None

    construction_approval_engine = fields.Selection(
        APPROVAL_ENGINES, string='Motor de aprobación', copy=False, readonly=True,
        help='Con qué se envió a aprobación: lo enviado con la validación por niveles termina '
             'con ese flujo.')
    construction_approval_ids = fields.Many2many(
        'approval.request', string='Solicitudes de aprobación',
        compute='_compute_construction_approval', compute_sudo=True)
    construction_approval_count = fields.Integer(
        string='Aprobaciones', compute='_compute_construction_approval', compute_sudo=True)
    construction_approval_id = fields.Many2one(
        'approval.request', string='Solicitud de aprobación',
        compute='_compute_construction_approval', compute_sudo=True)
    construction_approval_todo = fields.Char(
        string='Pendiente de aprobación', compute='_compute_construction_approval',
        compute_sudo=True)
    construction_approval_can_review = fields.Boolean(
        string='Puede aprobar', compute='_compute_construction_approval', compute_sudo=True)

    construction_approval_user_ids = fields.Many2many(
        'res.users', string='Aprobadores', compute='_compute_construction_approval',
        search='_search_construction_approval_user_ids', compute_sudo=True)

    def _search_construction_approval_user_ids(self, operator, value):
        if operator != 'in':
            return NotImplemented
        # Las reglas de acceso del documento preguntan si el usuario es
        # aprobador de una de sus solicitudes, que quizá no puede leer.
        approvers_sudo = self.env['approval.approver'].sudo().search([
            ('user_id', 'in', list(value)),
            ('request_id.construction_res_model', '=', self._name)])
        return [('id', 'in', approvers_sudo.request_id.mapped('construction_res_id'))]

    @api.depends_context('uid')
    def _compute_construction_approval(self):
        Request = self.env['approval.request']
        requests = Request.search([
            ('construction_res_model', '=', self._name),
            ('construction_res_id', 'in', self.ids)], order='id desc') if self.ids else Request
        by_record = {}
        for request in requests:
            by_record.setdefault(request.construction_res_id, Request)
            by_record[request.construction_res_id] |= request
        for record in self:
            own = by_record.get(record.id, Request)
            current = own.filtered(lambda r: r.request_status in ('new', 'pending'))[:1]
            record.construction_approval_ids = own
            record.construction_approval_user_ids = own.approver_ids.user_id
            record.construction_approval_count = len(own)
            record.construction_approval_id = current
            record.construction_approval_todo = current.construction_todo
            record.construction_approval_can_review = bool(
                current and current._construction_active_approvers(self.env.user))

    # ------------------------------------------------------------------
    # Envío
    # ------------------------------------------------------------------
    def _construction_set_approval_engine(self):
        """Al enviar: el motor de la compañía queda fijo en el documento."""
        for record in self:
            record.construction_approval_engine = record.company_id.construction_approval_engine
        if 'need_validation' in self._fields:
            self.invalidate_recordset(['need_validation'])

    def _construction_uses_approvals(self):
        return self.filtered(lambda r: r.construction_approval_engine == 'approvals')

    def _construction_approval_info(self):
        """Hook del documento: {'values': {tipo de cambio: {'percent': %,
        'amount': monto}}, 'lines': [valores de approval.product.line],
        'amount': exceso total, 'reason': texto}. Sin ``values``, no hay nada
        que aprobar."""
        self.ensure_one()
        return {'values': {}, 'lines': [], 'amount': 0.0, 'reason': ''}

    def _construction_submit_approval(self):
        """Crea la solicitud de los documentos con tramos que aplican y
        devuelve esos documentos (los demás se aprueban directamente)."""
        submitted = self.browse()
        Route = self.env['construction.approval.route']
        for record in self:
            info = record._construction_approval_info()
            if not info['values']:
                continue
            # La tabla de rutas la administra la jefatura: quien envía solo
            # la consulta para armar su solicitud.
            ladder = Route.sudo()._construction_ladder(
                record.company_id, self._construction_approval_document_type, info['values'])
            missing = set(info['values']) - set(ladder.mapped('change_type')) - {'all'}
            if not ladder.filtered(lambda r: r.change_type == 'all') and missing:
                labels = dict(Route._fields['change_type']._description_selection(self.env))
                raise UserError(self.env._(
                    '%(doc)s tiene cambios sin ruta de aprobación (%(types)s). Configure la '
                    'tabla de rutas en Planificación de obra › Configuración.',
                    doc=record.display_name,
                    types=', '.join(labels[t] for t in sorted(missing))))
            if not ladder:
                continue
            record._construction_create_approval(ladder, info)
            submitted |= record
        return submitted

    def _construction_project(self):
        self.ensure_one()
        return self.project_id

    def _construction_create_approval(self, ladder, info):
        self.ensure_one()
        owner = self.env.user
        tokens_by_user = {}
        for step, route in enumerate(ladder, start=1):
            users_by_slot = route._construction_users(exclude=owner)
            if not users_by_slot:
                raise UserError(self.env._(
                    'El tramo «%s» no tiene aprobadores (aparte de quien envía).', route.name))
            for slot, users in users_by_slot.items():
                for user in users:
                    tokens_by_user.setdefault(user, []).append(
                        (step, route, '%s:%s:%s' % (step, route.approval_rule, slot)))
        approver_values = [{
            'user_id': user.id,
            'sequence': tokens[0][0] * 1000 + index,
            'construction_step': tokens[0][0],
            'construction_route_id': tokens[0][1].id,
            'construction_slots': ','.join(token for _step, _route, token in tokens),
            'status': 'new',
        } for index, (user, tokens) in enumerate(tokens_by_user.items())]
        project = self._construction_project()
        reason = Markup('<p>%s</p>') % self.env._(
            '%(doc)s · obra %(project)s · %(steps)s tramo(s): %(names)s.',
            doc=self.display_name, project=project.display_name, steps=len(ladder),
            names=', '.join(ladder.mapped('name')))
        if info.get('reason'):
            reason += Markup('<p>%s</p>') % info['reason']
        # Quien envía no administra Aprobaciones (no crea aprobadores): la
        # solicitud y sus aprobadores salen de la ruta, no de su elección.
        request_sudo = self.env['approval.request'].sudo().create({
            'name': '%s · %s' % (ladder[0].category_id.name, self.display_name),
            'category_id': ladder[0].category_id.id,
            'request_owner_id': owner.id,
            'company_id': self.company_id.id,
            'reference': self.display_name,
            'reason': reason,
            'construction_res_model': self._name,
            'construction_res_id': self.id,
            'construction_origin_name': self.display_name,
            'construction_project_id': project.id,
            'construction_amount': info.get('amount', 0.0),
            'product_line_ids': [fields.Command.create(vals) for vals in info['lines']],
        })
        request_sudo.write({'approver_ids': [fields.Command.clear()] + [
            fields.Command.create(vals) for vals in approver_values]})
        request_sudo.action_confirm()
        request_sudo.construction_notified_status = request_sudo.request_status
        # Los campos de la solicitud no tienen dependencias: se recalculan.
        self.invalidate_recordset()
        followers = ladder._construction_follower_partners(project)
        if followers:
            request_sudo.message_subscribe(partner_ids=followers.ids)
            self.message_subscribe(partner_ids=followers.ids)
        self.message_post(body=Markup('%s <a href="#" data-oe-model="approval.request" '
                                      'data-oe-id="%s">%s</a> · %s') % (
            self.env._('Enviado a Aprobaciones:'), request_sudo.id, request_sudo.name,
            request_sudo.construction_todo or ''))
        return request_sudo

    # ------------------------------------------------------------------
    # Resultado
    # ------------------------------------------------------------------
    def _construction_approval_granted(self, request):
        """La solicitud vigente quedó aprobada: se libera el documento."""
        self.ensure_one()
        if self.state != 'to_approve':
            return
        self.message_post(body=self.env._('Aprobado en %s.', request.name))
        self.with_context(construction_approval_granted=True)._write_approved()

    def _construction_approval_refused(self, request):
        """Rechazada o cancelada: el documento vuelve a borrador con el motivo."""
        self.ensure_one()
        if self.state != 'to_approve':
            return
        if request.request_status == 'refused':
            body = self.env._('Rechazado en %(request)s: %(reason)s', request=request.name,
                              reason=request.construction_refuse_reason or self.env._('sin motivo'))
        else:
            body = self.env._('La solicitud %s se canceló.', request.name)
        self.with_context(skip_validation_check=True).write({'state': 'draft'})
        self.message_post(body=body)

    def _construction_cancel_open_approvals(self):
        """Volver a borrador o cancelar el documento cancela su solicitud abierta."""
        # Quien devuelve el documento a borrador no administra Aprobaciones.
        requests_sudo = self.sudo().construction_approval_ids.filtered(
            lambda r: r.request_status in ('new', 'pending'))
        if requests_sudo:
            # La solicitud cancelada no debe devolver el documento otra vez.
            requests_sudo.construction_notified_status = 'cancel'
            requests_sudo.action_cancel()

    # ------------------------------------------------------------------
    # Botones
    # ------------------------------------------------------------------
    def action_construction_approve(self):
        self.ensure_one()
        request = self.construction_approval_id
        if not request:
            raise UserError(self.env._('%s no tiene una solicitud de aprobación abierta.',
                                       self.display_name))
        request.action_approve()
        return True

    def action_construction_refuse(self):
        self.ensure_one()
        if not self.construction_approval_id:
            raise UserError(self.env._('%s no tiene una solicitud de aprobación abierta.',
                                       self.display_name))
        return self.construction_approval_id.action_construction_refuse()

    def action_view_construction_approvals(self):
        self.ensure_one()
        requests = self.construction_approval_ids
        action = {
            'type': 'ir.actions.act_window',
            'name': self.env._('Aprobaciones'),
            'res_model': 'approval.request',
            'domain': [('id', 'in', requests.ids)],
            'view_mode': 'list,form',
        }
        if len(requests) == 1:
            action.update(view_mode='form', res_id=requests.id)
        return action
