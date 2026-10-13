# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

APPROVAL_STATES = [
    ('not_required', 'No requiere'),
    ('to_request', 'Por solicitar'),
    ('pending', 'En aprobación'),
    ('refused', 'Rechazada'),
    ('approved', 'Aprobada'),
]


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    sale_approval_exempt = fields.Boolean(
        string='Sin aprobación (carga histórica)', copy=False,
        groups='sales_team.group_sale_manager',
        help='Orden cargada de otro sistema: se confirma sin solicitud aprobada.')
    sale_approval_required = fields.Boolean(
        string='Requiere aprobación', compute='_compute_sale_approval')
    sale_approval_state = fields.Selection(
        APPROVAL_STATES, string='Aprobación', compute='_compute_sale_approval')
    sale_approval_request_count = fields.Integer(compute='_compute_sale_approval')

    def _sale_approval_domain(self):
        """Solicitudes de la orden: las enlazadas y las anteriores al módulo
        con el número de la orden como referencia."""
        self.ensure_one()
        category = self.company_id.sale_approval_category_id
        domain = [('sale_order_id', '=', self.id)]
        if self.name and category:
            domain = ['|'] + domain + ['&', ('category_id', '=', category.id),
                                       ('reference', '=', self.name)]
        return domain

    def _sale_approval_requests(self):
        # sudo: el vendedor puede no ver las solicitudes de otros en Aprobaciones;
        # solo se lee su estado.
        return self.env['approval.request'].sudo().search(self._sale_approval_domain()) \
            if self.id else self.env['approval.request']

    @api.depends('order_line.product_id', 'company_id', 'name', 'sale_approval_exempt')
    @api.depends_context('uid')
    def _compute_sale_approval(self):
        for order in self:
            exempt = order.sudo().sale_approval_exempt
            required = not exempt and any(
                order.order_line.product_id.product_tmpl_id.mapped('sale_approval_required'))
            requests_sudo = order._sale_approval_requests()
            order.sale_approval_required = required
            order.sale_approval_request_count = len(requests_sudo)
            statuses = set(requests_sudo.mapped('request_status'))
            if not required:
                state = 'not_required'
            elif 'approved' in statuses:
                state = 'approved'
            elif statuses & {'new', 'pending'}:
                state = 'pending'
            elif 'refused' in statuses:
                state = 'refused'
            else:
                state = 'to_request'
            order.sale_approval_state = state

    def action_confirm(self):
        for order in self:
            if order.sale_approval_required and order.sale_approval_state != 'approved':
                raise UserError(_(
                    'La orden %(order)s necesita una solicitud aprobada en Aprobaciones '
                    '(«Solicitar aprobación») antes de confirmarse.', order=order.name))
        return super().action_confirm()

    def action_request_sale_approval(self):
        self.ensure_one()
        category = self.company_id.sale_approval_category_id
        if not category:
            raise UserError(_('Elija la categoría de aprobación de ventas en Ajustes ▸ Ventas.'))
        request = self.env['approval.request'].create({
            'name': _('Aprobación de %s', self.name),
            'category_id': category.id,
            'sale_order_id': self.id,
            'reference': self.name,
            'partner_id': self.partner_id.id,
            'amount': self.amount_total,
            'request_owner_id': self.env.user.id,
            'company_id': self.company_id.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'approval.request',
            'res_id': request.id,
            'view_mode': 'form',
        }

    def action_view_sale_approvals(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Aprobaciones'),
            'res_model': 'approval.request',
            'view_mode': 'list,form',
            'domain': self._sale_approval_domain(),
        }
