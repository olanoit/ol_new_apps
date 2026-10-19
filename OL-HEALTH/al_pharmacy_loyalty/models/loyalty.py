# -*- coding: utf-8 -*-
"""Fidelización de botica dentro de la norma: los medicamentos con receta y
los controlados no suman puntos ni reciben recompensas (DS 014-2011-SA y
Manual BPOF: no se promueve el consumo de medicamentos con sorteos, premios
ni canjes)."""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain

PRESCRIPTION_CONDITIONS = ('prescription', 'controlled')


def _without_prescription_domain():
    return Domain('pharmacy_sale_condition', 'not in', PRESCRIPTION_CONDITIONS)


class LoyaltyProgram(models.Model):
    _inherit = 'loyalty.program'

    pharmacy_exclude_prescription = fields.Boolean(
        string='Excluir medicamentos con receta', default=True,
        help='Los medicamentos de venta con receta y los controlados no suman puntos ni '
             'reciben descuentos o regalos del programa. No aplica a tarjetas de regalo ni '
             'monederos, que son medios de pago.')

    def _pharmacy_excludes_prescription(self):
        self.ensure_one()
        return self.pharmacy_exclude_prescription and not self.is_payment_program

    def write(self, vals):
        result = super().write(vals)
        if 'pharmacy_exclude_prescription' in vals:
            self.reward_ids._pharmacy_restrict_order_discount()
        return result


class LoyaltyRule(models.Model):
    _inherit = 'loyalty.rule'

    def _get_valid_product_domain(self):
        domain = super()._get_valid_product_domain()
        if self.program_id._pharmacy_excludes_prescription():
            domain = Domain(domain) & _without_prescription_domain()
        return domain

    @api.depends('program_id.pharmacy_exclude_prescription', 'program_id.program_type')
    def _compute_valid_product_ids(self):
        # El TPV usa «cualquier producto» cuando la regla no filtra nada: con la
        # exclusión, la regla sí filtra y el TPV recibe la lista de productos.
        super()._compute_valid_product_ids()
        for rule in self.filtered(lambda r: r.program_id._pharmacy_excludes_prescription()):
            rule.valid_product_ids = self.env['product.product'].search(
                Domain('available_in_pos', '=', True) & rule._get_valid_product_domain(), order='id')
            rule.any_product = False


class LoyaltyReward(models.Model):
    _inherit = 'loyalty.reward'

    def _get_discount_product_domain(self):
        domain = super()._get_discount_product_domain()
        if self.program_id._pharmacy_excludes_prescription():
            domain = Domain(domain) & _without_prescription_domain()
        return domain

    @api.model_create_multi
    def create(self, vals_list):
        rewards = super().create(vals_list)
        rewards._pharmacy_restrict_order_discount()
        return rewards

    def write(self, vals):
        result = super().write(vals)
        if {'discount_applicability', 'reward_type', 'program_id'} & vals.keys():
            self._pharmacy_restrict_order_discount()
        return result

    def _pharmacy_restrict_order_discount(self):
        """Un descuento «sobre el pedido» alcanzaría a los medicamentos con
        receta: pasa a «productos específicos», que sin más filtros son todos
        los demás productos."""
        to_restrict = self.filtered(lambda r: (
            r.reward_type == 'discount' and r.discount_applicability == 'order'
            and r.program_id._pharmacy_excludes_prescription()))
        for reward in to_restrict:
            # La descripción se recalcula con el alcance: se conserva la del usuario.
            super(LoyaltyReward, reward).write({
                'discount_applicability': 'specific', 'description': reward.description})

    @api.constrains('reward_type', 'reward_product_id', 'reward_product_tag_id', 'program_id')
    def _check_pharmacy_reward_product(self):
        for reward in self:
            if reward.reward_type != 'product' or not reward.program_id._pharmacy_excludes_prescription():
                continue
            products = reward.reward_product_id | reward.reward_product_tag_id.product_ids
            prescription = products.filtered(
                lambda p: p.pharmacy_sale_condition in PRESCRIPTION_CONDITIONS)
            if prescription:
                raise ValidationError(_(
                    'El programa %(program)s no puede regalar medicamentos con receta: %(products)s.',
                    program=reward.program_id.display_name,
                    products=', '.join(prescription.mapped('display_name'))))



class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def _load_pos_data_fields(self, config):
        # El TPV evalúa el dominio de productos del descuento sobre los
        # productos cargados: necesita la condición de venta.
        return super()._load_pos_data_fields(config) + ['pharmacy_sale_condition']
