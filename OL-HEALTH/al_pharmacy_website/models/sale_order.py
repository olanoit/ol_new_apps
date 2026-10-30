# -*- coding: utf-8 -*-
"""Pedidos de la tienda en línea de la botica.

* Los productos controlados no se venden en línea (BPOF 7.5.5.1).
* Los productos con receta piden subir la receta antes de pagar; el pedido no
  se confirma (ni se entrega) hasta que un químico farmacéutico la aprueba.
* La cadena de frío se marca en el pedido y en la entrega.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import BinaryBytes

REVIEW_STATES = [
    ('none', 'No requiere'),
    ('to_upload', 'Falta la receta'),
    ('to_review', 'Por validar'),
    ('approved', 'Aprobada'),
    ('rejected', 'Rechazada'),
]


def _is_controlled(product):
    """Controlado por su condición de venta o, si está instalada la capa
    peruana de controlados, por su lista de fiscalización."""
    return product.pharmacy_sale_condition == 'controlled' or bool(
        'pharmacy_control_list' in product._fields and product.pharmacy_control_list)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    pharmacy_prescription_required = fields.Boolean(
        string='Requiere receta', compute='_compute_pharmacy_prescription_required', store=True,
        help='Pedido de la tienda en línea con productos de venta con receta.')
    pharmacy_prescription_file = fields.Binary(
        string='Receta', attachment=True, copy=False,
        groups='al_pharmacy_base.group_pharmacy_pharmacist',
        help='Foto o PDF de la receta que subió el cliente.')
    pharmacy_prescription_filename = fields.Char(
        string='Archivo de la receta', copy=False,
        groups='al_pharmacy_base.group_pharmacy_pharmacist')
    pharmacy_prescription_uploaded = fields.Boolean(string='Receta subida', copy=False, readonly=True)
    pharmacy_review_decision = fields.Selection(
        [('approved', 'Aprobada'), ('rejected', 'Rechazada')], string='Decisión del Q.F.',
        copy=False, readonly=True)
    pharmacy_review_state = fields.Selection(
        REVIEW_STATES, string='Validación de la receta', compute='_compute_pharmacy_review_state',
        store=True, index='btree_not_null')
    pharmacy_review_reason = fields.Text(
        string='Motivo del rechazo', copy=False,
        help='Se informa al cliente al rechazar la receta.')
    pharmacy_reviewer_id = fields.Many2one('res.users', string='Validada por', copy=False, readonly=True)
    pharmacy_review_date = fields.Datetime(string='Fecha de validación', copy=False, readonly=True)
    pharmacy_cold_chain = fields.Boolean(
        string='Cadena de frío', compute='_compute_pharmacy_cold_chain',
        help='El pedido lleva productos que se conservan entre 2 y 8 °C.')

    @api.depends('website_id', 'order_line.product_id.pharmacy_sale_condition')
    def _compute_pharmacy_prescription_required(self):
        for order in self:
            order.pharmacy_prescription_required = bool(order.website_id) and any(
                product.pharmacy_sale_condition == 'prescription'
                for product in order.order_line.product_id)

    @api.depends('pharmacy_prescription_required', 'pharmacy_prescription_uploaded',
                 'pharmacy_review_decision')
    def _compute_pharmacy_review_state(self):
        for order in self:
            if not order.pharmacy_prescription_required:
                order.pharmacy_review_state = 'none'
            elif order.pharmacy_review_decision:
                order.pharmacy_review_state = order.pharmacy_review_decision
            elif order.pharmacy_prescription_uploaded:
                order.pharmacy_review_state = 'to_review'
            else:
                order.pharmacy_review_state = 'to_upload'

    @api.depends('order_line.product_id.pharmacy_cold_chain')
    def _compute_pharmacy_cold_chain(self):
        for order in self:
            order.pharmacy_cold_chain = any(order.order_line.product_id.mapped('pharmacy_cold_chain'))

    # ------------------------------------------------------------------
    # Carrito
    # ------------------------------------------------------------------
    def _verify_updated_quantity(self, order_line, product_id, new_qty, uom_id, **kwargs):
        product = self.env['product.product'].browse(product_id)
        if self.website_id and new_qty > 0 and _is_controlled(product):
            return 0, _('%s es un medicamento controlado: solo se vende en el local, con la '
                        'receta especial.', product.display_name)
        return super()._verify_updated_quantity(order_line, product_id, new_qty, uom_id, **kwargs)

    def _is_cart_ready_for_payment(self):
        # Odoo 20: el carrito no lanza error; avisa al cliente y bloquea el paso.
        controlled = self.order_line.product_id.filtered(_is_controlled)
        if self.website_id and controlled:
            self._add_blocking_alert(_(
                'Los medicamentos controlados no se venden en línea: %s.',
                ', '.join(controlled.mapped('display_name'))))
            return False
        if self.pharmacy_prescription_required and not self.pharmacy_prescription_uploaded:
            self._add_blocking_alert(_('Suba la receta médica antes de pagar.'))
            return False
        return super()._is_cart_ready_for_payment()

    def _pharmacy_save_prescription(self, content, filename):
        """Guarda la receta que sube el cliente (contenido binario) y la
        deja por validar."""
        self.ensure_one()
        self.write({
            # Odoo 20: los campos Binary se escriben con BinaryBytes.
            'pharmacy_prescription_file': BinaryBytes(content),
            'pharmacy_prescription_filename': filename,
            'pharmacy_prescription_uploaded': True,
            'pharmacy_review_decision': False,
            'pharmacy_review_reason': False,
        })
        self.message_post(body=_('El cliente subió la receta %s: queda por validar por un químico '
                                 'farmacéutico.', filename))
        responsible = self.warehouse_id.pharmacy_director_id.user_id or self.user_id
        if responsible:
            self.activity_schedule(
                'mail.mail_activity_data_todo', user_id=responsible.id,
                summary=_('Validar la receta del pedido en línea'))

    # ------------------------------------------------------------------
    # Validación del químico farmacéutico
    # ------------------------------------------------------------------
    def _is_confirmation_amount_reached(self):
        # Un pedido pagado con receta por validar no se confirma al pagar:
        # lo confirma la aprobación del químico farmacéutico.
        if self.pharmacy_prescription_required and self.pharmacy_review_state != 'approved':
            return False
        return super()._is_confirmation_amount_reached()

    def _validate_order(self):
        pending = self.filtered(
            lambda o: o.pharmacy_prescription_required and o.pharmacy_review_state != 'approved')
        return super(SaleOrder, self - pending)._validate_order()

    def action_confirm(self):
        pending = self.filtered(
            lambda o: o.pharmacy_prescription_required and o.pharmacy_review_state != 'approved')
        if pending:
            raise UserError(_(
                'Un químico farmacéutico debe aprobar la receta antes de confirmar: %s.',
                ', '.join(pending.mapped('name'))))
        return super().action_confirm()

    def _pharmacy_check_reviewer(self):
        if not self.env.user.has_group('al_pharmacy_base.group_pharmacy_pharmacist'):
            raise UserError(_('Solo un químico farmacéutico valida las recetas.'))
        for order in self:
            if order.pharmacy_review_state not in ('to_review', 'approved', 'rejected'):
                raise UserError(_('El pedido %s no tiene una receta por validar.', order.name))

    def action_pharmacy_approve_prescription(self):
        self._pharmacy_check_reviewer()
        self.write({
            'pharmacy_review_decision': 'approved', 'pharmacy_review_reason': False,
            'pharmacy_reviewer_id': self.env.uid, 'pharmacy_review_date': fields.Datetime.now(),
        })
        for order in self:
            order.message_post(body=_('Receta aprobada por %s.', self.env.user.name))
            if order.state in ('draft', 'sent') and order._is_confirmation_amount_reached():
                order.with_context(send_email=True).action_confirm()
        return True

    def action_pharmacy_reject_prescription(self):
        self._pharmacy_check_reviewer()
        for order in self:
            if not order.pharmacy_review_reason:
                raise UserError(_('Indique el motivo del rechazo de la receta del pedido %s.',
                                  order.name))
        self.write({
            'pharmacy_review_decision': 'rejected',
            'pharmacy_reviewer_id': self.env.uid, 'pharmacy_review_date': fields.Datetime.now(),
        })
        for order in self:
            # Al cliente: ve el motivo en el portal y puede subir otra receta.
            order.message_post(
                body=_('La receta no se aprobó: %s. Puede subir otra receta o comunicarse con la '
                       'botica.', order.pharmacy_review_reason),
                partner_ids=order.partner_id.ids, subtype_xmlid='mail.mt_comment')
        return True
