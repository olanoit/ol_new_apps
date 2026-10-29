# -*- coding: utf-8 -*-
from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import SQL

from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon


def _program_vals(**vals):
    return {
        'name': 'Club de Salud', 'program_type': 'loyalty', 'applies_on': 'both',
        'trigger': 'auto',
        'rule_ids': [Command.create({'reward_point_mode': 'money', 'reward_point_amount': 0.25})],
        'reward_ids': [Command.create({
            'reward_type': 'discount', 'discount': 10, 'discount_mode': 'percent',
            'discount_applicability': 'order', 'required_points': 1,
            'description': 'Descuento de socio'})],
        **vals,
    }


@tagged('post_install', '-at_install')
class TestPharmacyLoyalty(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        common = {'type': 'consu', 'available_in_pos': True, 'sale_ok': True,
                  'taxes_id': [Command.set([])]}
        cls.otc = cls.env['product.product'].create({
            **common, 'name': 'Bloqueador solar FPS 50', 'list_price': 8.0})
        cls.prescription = cls.env['product.product'].create({
            **common, 'name': 'Amoxicilina 500 mg', 'list_price': 40.0, 'pharmacy_ok': True,
            'pharmacy_sale_condition': 'prescription'})
        cls.controlled = cls.env['product.product'].create({
            **common, 'name': 'Clonazepam 2 mg', 'list_price': 12.0, 'pharmacy_ok': True,
            'pharmacy_sale_condition': 'controlled'})
        cls.program = cls.env['loyalty.program'].create(_program_vals())

    def test_rule_excludes_prescription_products(self):
        rule = self.program.rule_ids
        self.assertFalse(rule.any_product)
        self.assertIn(self.otc, rule.valid_product_ids)
        self.assertNotIn(self.prescription, rule.valid_product_ids)
        self.assertNotIn(self.controlled, rule.valid_product_ids)
        valid = self.program._get_valid_products(self.otc | self.prescription | self.controlled)[rule]
        self.assertEqual(valid, self.otc)

    def test_without_the_option_every_product_counts(self):
        self.program.pharmacy_exclude_prescription = False
        self.assertTrue(self.program.rule_ids.any_product)

    def test_order_discount_does_not_reach_prescription(self):
        reward = self.program.reward_ids
        self.assertEqual(reward.discount_applicability, 'specific')
        products = self.otc | self.prescription | self.controlled
        self.assertEqual(products.filtered_domain(reward._get_discount_product_domain()), self.otc)
        self.env['ir.config_parameter'].set_str('loyalty.compute_all_discount_product_ids', 'enabled')
        reward.invalidate_recordset(['all_discount_product_ids'])
        self.assertIn(self.otc, reward.all_discount_product_ids)
        self.assertNotIn(self.prescription, reward.all_discount_product_ids)

    def test_install_hook_restricts_existing_programs(self):
        from odoo.addons.al_pharmacy_loyalty import _post_init_hook
        reward = self.program.reward_ids
        # Como un programa creado antes de instalar el módulo.
        self.env.cr.execute(SQL(
            "UPDATE loyalty_reward SET discount_applicability = 'order' WHERE id = %s", reward.id))
        reward.invalidate_recordset()
        _post_init_hook(self.env)
        self.assertEqual(reward.discount_applicability, 'specific')

    def test_cannot_give_away_prescription_medicine(self):
        with self.assertRaises(ValidationError):
            self.env['loyalty.reward'].create({
                'program_id': self.program.id, 'reward_type': 'product',
                'reward_product_id': self.prescription.id, 'required_points': 100})

    def test_payment_programs_are_not_restricted(self):
        gift_card = self.env['loyalty.program'].create({
            'name': 'Tarjeta de regalo', 'program_type': 'gift_card'})
        self.assertFalse(gift_card._pharmacy_excludes_prescription())

    def test_sale_order_points_skip_prescription(self):
        partner = self.env['res.partner'].create({'name': 'Rosa Quispe', 'vat': '44556677'})
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [
                Command.create({'product_id': self.otc.id, 'product_uom_qty': 1}),
                Command.create({'product_id': self.prescription.id, 'product_uom_qty': 1}),
            ],
        })
        order._update_programs_and_rewards()
        points = order.coupon_point_ids.filtered(lambda p: p.coupon_id.program_id == self.program)
        # S/ 8 de producto de venta libre × 0,25 = 2 puntos; la amoxicilina no suma.
        self.assertEqual(points.points, 2)


@tagged('post_install', '-at_install')
class TestPharmacyLoyaltyPos(TestPointOfSaleHttpCommon):

    def test_pos_points_skip_prescription(self):
        self.env['loyalty.program'].search([]).write({'active': False})
        common = {'type': 'consu', 'available_in_pos': True, 'taxes_id': [Command.set([])]}
        self.env['product.product'].create({
            **common, 'name': 'Bloqueador solar FPS 50', 'list_price': 8.0})
        # Sin pharmacy_ok, la caja no pide receta: solo se prueba el programa.
        self.env['product.product'].create({
            **common, 'name': 'Amoxicilina 500 mg', 'list_price': 40.0,
            'pharmacy_sale_condition': 'prescription'})
        program = self.env['loyalty.program'].create(_program_vals(
            pos_config_ids=[Command.link(self.main_pos_config.id)]))
        partner = self.env['res.partner'].create({'name': 'Rosa Quispe'})
        card = self.env['loyalty.card'].create({
            'program_id': program.id, 'partner_id': partner.id, 'points': 10})
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour('al_pharmacy_loyalty_points')
        order = self.env['pos.order'].search(
            [('session_id', '=', self.main_pos_config.current_session_id.id)], limit=1)
        # El 10 % de socio solo alcanza al bloqueador: S/ 0,80, no S/ 4,80.
        self.assertAlmostEqual(order.lines.filtered('reward_id').price_subtotal_incl, -0.80)
        self.assertGreater(card.points, 10 - 1)
