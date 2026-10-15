# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.al_construction_planner.models.common import PROJECT_HEAD_GROUPS


class ConstructionMaterialRequest(models.Model):
    _inherit = 'construction.material.request'

    # Descuento del material extra a una contrata (v1.6, M16-08): lo decide
    # la jefatura de proyectos al aprobar el extra; entra como línea negativa
    # en la siguiente liquidación semanal de esa contrata en la obra.
    construction_discount = fields.Boolean(
        string='Descontar a la contrata', copy=False, tracking=True)
    construction_discount_partner_id = fields.Many2one(
        'res.partner', string='Contrata a descontar', copy=False, tracking=True,
        help='La contrata responsable del extra: su siguiente liquidación en la obra lleva el '
             'descuento.')
    construction_discount_amount = fields.Monetary(
        string='Monto a descontar', copy=False, tracking=True, currency_field='currency_id',
        compute='_compute_construction_discount_amount', store=True, readonly=False,
        help='Por defecto, el valor estimado del requerimiento.')
    construction_discount_settlement_id = fields.Many2one(
        'construction.contract.settlement', string='Descontado en', copy=False, readonly=True,
        index='btree_not_null', check_company=True)

    @api.depends('construction_discount', 'amount_estimated')
    def _compute_construction_discount_amount(self):
        for request in self:
            if not request.construction_discount:
                request.construction_discount_amount = 0.0
            elif not request.construction_discount_amount:
                request.construction_discount_amount = request.amount_estimated

    @api.constrains('construction_discount', 'construction_discount_partner_id',
                    'construction_discount_amount')
    def _check_construction_discount(self):
        for request in self.filtered('construction_discount'):
            if not request.construction_discount_partner_id:
                raise ValidationError(self.env._(
                    'Indique la contrata a la que se descuenta el extra %s.', request.name))
            if request.currency_id.compare_amounts(request.construction_discount_amount, 0) <= 0:
                raise ValidationError(self.env._(
                    'El monto a descontar del extra %s debe ser mayor que cero.', request.name))

    def _check_discount_manager(self):
        if not self.env.su and not self.env.user.has_groups(PROJECT_HEAD_GROUPS):
            raise UserError(self.env._(
                'El descuento a la contrata lo decide la jefatura de proyectos.'))

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get('construction_discount') for vals in vals_list):
            self._check_discount_manager()
        return super().create(vals_list)

    def write(self, vals):
        discount_fields = {'construction_discount', 'construction_discount_partner_id',
                           'construction_discount_amount'}
        if discount_fields & set(vals):
            self._check_discount_manager()
            if self.filtered('construction_discount_settlement_id'):
                raise UserError(self.env._(
                    'El extra ya se descontó en una liquidación: no se puede cambiar el descuento.'))
        return super().write(vals)

    @api.model
    def _get_under_validation_exceptions(self):
        # El descuento a la contrata lo decide la jefatura mientras revisa el
        # extra (v1.6, M16-08).
        return super()._get_under_validation_exceptions() + [
            'construction_discount', 'construction_discount_partner_id',
            'construction_discount_amount']

    @api.model
    def _get_all_validation_exceptions(self):
        # Sin esto, OCA los deja de solo lectura en la vista durante la revisión.
        return super()._get_all_validation_exceptions() + [
            'construction_discount', 'construction_discount_partner_id',
            'construction_discount_amount']
