# -*- coding: utf-8 -*-
import base64

from odoo import Command, http
from odoo.exceptions import UserError, ValidationError
from odoo.tests import HttpCase, TransactionCase, new_test_user, tagged

# PNG de 1 × 1 píxel.
PNG = base64.b64decode(
    b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGD4DwABBAEAwS2OUAAAAABJRU5ErkJggg==')


class PharmacyWebsiteCommon:

    @classmethod
    def _setup_pharmacy_products(cls):
        cls.website = cls.env.ref('website.default_website')
        ingredient = cls.env['pharmacy.ingredient']._get_or_create('Amoxicilina')
        common = {
            'type': 'consu', 'is_published': True, 'sale_ok': True, 'pharmacy_ok': True,
            'taxes_id': [Command.set([])],
            'pharmacy_dosage_form_id': cls.env.ref('al_pharmacy_base.dosage_form_capsule').id,
            'pharmacy_ingredient_line_ids': [Command.create({
                'ingredient_id': ingredient.id, 'strength': 500, 'strength_unit': 'mg'})],
        }
        cls.innovator = cls.env['product.template'].create({
            **common, 'name': 'Amoxival 500 mg', 'list_price': 3.0,
            'pharmacy_product_type': 'innovator', 'pharmacy_sale_condition': 'prescription'})
        cls.generic = cls.env['product.template'].create({
            **common, 'name': 'Amoxicilina 500 mg', 'list_price': 0.8,
            'pharmacy_product_type': 'generic_dci', 'pharmacy_sale_condition': 'prescription'})
        cls.brand_generic = cls.env['product.template'].create({
            **common, 'name': 'Amoxil genérico 500 mg', 'list_price': 0.5,
            'pharmacy_product_type': 'generic_brand', 'pharmacy_sale_condition': 'prescription'})
        cls.controlled = cls.env['product.template'].create({
            'name': 'Clonazepam 2 mg', 'type': 'consu', 'is_published': True, 'sale_ok': True,
            'pharmacy_ok': True, 'pharmacy_sale_condition': 'controlled', 'list_price': 1.0,
            'taxes_id': [Command.set([])]})
        cls.insulin = cls.env['product.template'].create({
            'name': 'Insulina NPH 100 UI/mL', 'type': 'consu', 'is_storable': True,
            'is_published': True, 'sale_ok': True, 'pharmacy_ok': True,
            'pharmacy_sale_condition': 'otc', 'pharmacy_cold_chain': True, 'list_price': 30.0,
            'taxes_id': [Command.set([])]})
        cls.customer = cls.env['res.partner'].create({
            'name': 'Rosa Quispe', 'email': 'rosa.quispe@example.com', 'street': 'Av. Arequipa 123',
            'city': 'Lima', 'country_id': cls.env.ref('base.pe').id})

    @classmethod
    def _web_order(cls, product, partner=None, qty=1):
        return cls.env['sale.order'].create({
            'partner_id': (partner or cls.customer).id,
            'website_id': cls.website.id,
            'order_line': [Command.create({'product_id': product.product_variant_id.id,
                                           'product_uom_qty': qty})],
        })


@tagged('post_install', '-at_install')
class TestPharmacyWebsite(PharmacyWebsiteCommon, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_pharmacy_products()
        cls.pharmacist = new_test_user(
            cls.env, login='qf_web', name='Q.F. Web',
            groups='base.group_user,sales_team.group_sale_salesman_all_leads,'
                   'al_pharmacy_base.group_pharmacy_pharmacist')
        cls.salesman = new_test_user(
            cls.env, login='vendedor_web', groups='base.group_user,sales_team.group_sale_salesman')

    def test_alternatives_generics_first(self):
        alternatives = self.innovator._pharmacy_website_alternatives()
        self.assertEqual(alternatives.mapped('name'),
                         ['Amoxicilina 500 mg', 'Amoxil genérico 500 mg'])

    def test_controlled_not_added_to_cart(self):
        order = self._web_order(self.insulin)
        qty, warning = order._verify_updated_quantity(
            self.env['sale.order.line'], self.controlled.product_variant_id.id, 1,
            self.controlled.uom_id.id)
        self.assertEqual(qty, 0)
        self.assertIn('controlado', warning)
        with self.assertRaises(ValidationError):
            self._web_order(self.controlled)._check_cart_is_ready_to_be_paid()

    def test_prescription_needed_before_paying(self):
        order = self._web_order(self.generic)
        self.assertTrue(order.pharmacy_prescription_required)
        self.assertEqual(order.pharmacy_review_state, 'to_upload')
        with self.assertRaisesRegex(ValidationError, 'receta'):
            order._check_cart_is_ready_to_be_paid()
        backend_order = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'order_line': [Command.create({'product_id': self.generic.product_variant_id.id})]})
        self.assertFalse(backend_order.pharmacy_prescription_required)

    def test_order_waits_for_the_pharmacist(self):
        order = self._web_order(self.generic)
        order._pharmacy_save_prescription(base64.b64encode(PNG), 'receta.png')
        self.assertEqual(order.pharmacy_review_state, 'to_review')
        self.assertFalse(order._is_confirmation_amount_reached())
        with self.assertRaises(UserError):
            order.action_confirm()
        with self.assertRaises(UserError):
            order.with_user(self.salesman).action_pharmacy_approve_prescription()
        # Sin pago no se confirma; aquí el pedido no exige pago previo.
        order.require_payment = False
        order.with_user(self.pharmacist).action_pharmacy_approve_prescription()
        self.assertEqual(order.pharmacy_review_state, 'approved')
        self.assertEqual(order.pharmacy_reviewer_id, self.pharmacist)
        self.assertEqual(order.state, 'sale')

    def test_rejection_needs_a_reason_and_allows_a_new_upload(self):
        order = self._web_order(self.generic)
        order._pharmacy_save_prescription(base64.b64encode(PNG), 'receta.png')
        as_pharmacist = order.with_user(self.pharmacist)
        with self.assertRaises(UserError):
            as_pharmacist.action_pharmacy_reject_prescription()
        order.pharmacy_review_reason = 'La receta venció hace un mes.'
        as_pharmacist.action_pharmacy_reject_prescription()
        self.assertEqual(order.pharmacy_review_state, 'rejected')
        self.assertIn(order.partner_id, order.message_ids[:1].partner_ids)
        order._pharmacy_save_prescription(base64.b64encode(PNG), 'receta2.png')
        self.assertEqual(order.pharmacy_review_state, 'to_review')
        self.assertFalse(order.pharmacy_review_reason)

    def test_cold_chain_on_delivery(self):
        order = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'order_line': [Command.create({'product_id': self.insulin.product_variant_id.id})]})
        self.assertTrue(order.pharmacy_cold_chain)
        order.action_confirm()
        picking = order.picking_ids
        self.assertTrue(picking.pharmacy_cold_chain)
        html = self.env['ir.actions.report']._render_qweb_html(
            'stock.action_report_delivery', picking.ids)[0].decode()
        self.assertIn('CADENA DE FRÍO', html)


@tagged('post_install', '-at_install')
class TestPharmacyWebsiteHttp(PharmacyWebsiteCommon, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_pharmacy_products()
        cls.portal_user = new_test_user(
            cls.env, login='cliente_web', password='cliente_web', groups='base.group_portal')
        cls.portal_user.partner_id.write({
            'street': 'Av. Arequipa 123', 'city': 'Lima', 'country_id': cls.env.ref('base.pe').id,
            'email': 'cliente_web@example.com'})

    def test_product_page_generics_first_and_controlled(self):
        html = self.url_open(self.innovator.website_url).text
        self.assertIn('o_pharmacy_alternatives', html)
        self.assertLess(html.index('Amoxicilina 500 mg'), html.index('Amoxil genérico 500 mg'))
        self.assertIn('o_pharmacy_prescription', html)
        html = self.url_open(self.controlled.website_url).text
        self.assertIn('o_pharmacy_controlled', html)
        self.assertNotIn('id="add_to_cart"', html)

    def test_checkout_asks_for_the_prescription(self):
        order = self._web_order(self.generic, partner=self.portal_user.partner_id)
        self.authenticate('cliente_web', 'cliente_web')
        response = self.url_open('/shop/payment')
        self.assertTrue(response.url.endswith('/shop/pharmacy/prescription'))
        csrf = http.Request.csrf_token(self)
        # Un archivo que no es imagen ni PDF se rechaza.
        response = self.url_open('/shop/pharmacy/prescription', data={'csrf_token': csrf},
                                 files={'prescription': ('receta.txt', b'hola', 'text/plain')})
        self.assertIn('o_pharmacy_upload_error', response.text)
        self.assertEqual(order.pharmacy_review_state, 'to_upload')
        response = self.url_open('/shop/pharmacy/prescription', data={'csrf_token': csrf},
                                 files={'prescription': ('receta.png', PNG, 'image/png')})
        self.assertNotIn('o_pharmacy_upload_error', response.text)
        order.invalidate_recordset()
        self.assertEqual(order.pharmacy_review_state, 'to_review')

    def test_portal_upload_needs_access(self):
        order = self._web_order(self.generic)
        self.authenticate(None, None)
        csrf = http.Request.csrf_token(self)
        url = '/my/orders/%s/prescription' % order.id
        response = self.url_open(url + '?access_token=malo', data={'csrf_token': csrf},
                                 files={'prescription': ('receta.png', PNG, 'image/png')})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(order.pharmacy_review_state, 'to_upload')
        order._portal_ensure_token()
        self.url_open('%s?access_token=%s' % (url, order.access_token), data={'csrf_token': csrf},
                      files={'prescription': ('receta.png', PNG, 'image/png')})
        order.invalidate_recordset()
        self.assertEqual(order.pharmacy_review_state, 'to_review')
