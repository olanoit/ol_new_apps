# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.addons.point_of_sale.tests.common import TestPoSCommon
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestPharmacyTreatment(TestPoSCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.basic_config
        # TestPoSCommon trabaja con un usuario contable: aquí atiende el Q.F.
        cls.env.user.group_ids += cls.env.ref('al_pharmacy_base.group_pharmacy_manager') \
            + cls.env.ref('sales_team.group_sale_manager')
        cls.today = fields.Date.context_today(cls.env['pharmacy.treatment'])
        ingredient = cls.env['pharmacy.ingredient']._get_or_create('Enalapril')
        tablet = cls.env.ref('al_pharmacy_base.dosage_form_tablet')
        common = {
            'pharmacy_ok': True, 'pharmacy_dosage_form_id': tablet.id,
            'pharmacy_ingredient_line_ids': [(0, 0, {'ingredient_id': ingredient.id,
                                                     'strength': 10, 'strength_unit': 'mg'})],
        }
        cls.brand = cls.create_product('Enalabrand 10 mg tableta', cls.categ_basic, 1.0)
        cls.brand.product_tmpl_id.write({**common, 'pharmacy_product_type': 'innovator'})
        cls.generic = cls.create_product('Enalapril 10 mg tableta', cls.categ_basic, 0.3)
        cls.generic.product_tmpl_id.write({**common, 'pharmacy_product_type': 'generic_dci'})
        cls.patient = cls.env['res.partner'].create({
            'name': 'Julia Ramos Quispe', 'phone': '987 654 321', 'email': 'julia@example.com',
            'country_id': cls.env.ref('base.pe').id})
        cls.env.company.pharmacy_care_reminder_days = 5

    def _treatment(self, **vals):
        return self.env['pharmacy.treatment'].create({
            'patient_id': self.patient.id, 'product_id': self.brand.id, 'daily_units': 1,
            'date_start': self.today - timedelta(days=60), **vals})

    def _pos_purchase(self, product, qty, days_ago):
        order = self.env['pos.order'].create({
            'session_id': self.pos_session.id,
            'partner_id': self.patient.id,
            'lines': [(0, 0, {'product_id': product.id, 'qty': qty, 'price_unit': 1.0,
                              'price_subtotal': qty, 'price_subtotal_incl': qty})],
            'amount_tax': 0, 'amount_total': qty, 'amount_paid': qty, 'amount_return': 0,
        })
        order.write({'state': 'paid',
                     'date_order': fields.Datetime.now() - timedelta(days=days_ago)})
        return order

    def test_purchases_of_equivalents_are_chained(self):
        self.open_new_session()
        treatment = self._treatment()
        self.assertEqual(treatment.refill_state, 'no_purchase')
        # 30 tabletas del genérico hace 40 días y 30 de la marca hace 15:
        # la segunda compra empieza cuando se acaba la primera.
        self._pos_purchase(self.generic, 30, 40)
        self._pos_purchase(self.brand, 30, 15)
        treatment._update_coverage()
        self.assertEqual(treatment.last_purchase_date, self.today - timedelta(days=15))
        self.assertEqual(treatment.covered_until, self.today + timedelta(days=20))
        self.assertEqual(treatment.next_refill_date, self.today + timedelta(days=15))
        self.assertEqual(treatment.refill_state, 'ok')
        # 41 días cubiertos (30 + 11 hasta hoy) de los 61 desde el inicio.
        self.assertAlmostEqual(treatment.pdc, 67.2, places=1)
        self.assertFalse(treatment.adherent)

    def test_returns_shorten_the_coverage(self):
        self.open_new_session()
        treatment = self._treatment()
        self._pos_purchase(self.brand, 30, 10)
        self._pos_purchase(self.brand, -10, 5)
        treatment._update_coverage()
        self.assertEqual(treatment.covered_until, self.today + timedelta(days=10))

    def test_late_treatment_gets_one_reminder(self):
        self.open_new_session()
        self.env.company.pharmacy_care_send_email = True
        treatment = self._treatment()
        self._pos_purchase(self.generic, 30, 40)
        mails_before = self.env['mail.mail'].search_count([])
        self.env['pharmacy.treatment']._cron_refill_reminders()
        self.assertEqual(treatment.refill_state, 'late')
        self.assertEqual(treatment.days_late, 10)
        activity_type = self.env.ref('al_pharmacy_care.mail_activity_type_refill')
        activities = treatment.activity_ids.filtered(lambda a: a.activity_type_id == activity_type)
        self.assertEqual(len(activities), 1)
        self.assertIn('se terminó', activities.note)
        self.assertEqual(self.env['mail.mail'].search_count([]), mails_before + 1)
        # Al día siguiente no se repite el recordatorio.
        self.env['pharmacy.treatment']._cron_refill_reminders()
        self.assertEqual(len(treatment.activity_ids), 1)

    def test_pos_sale_updates_the_treatment(self):
        """Lo que el TPV llama al guardar una venta pagada del cliente."""
        self.open_new_session()
        treatment = self._treatment()
        order = self._pos_purchase(self.generic, 30, 0)
        self.env['pharmacy.treatment']._update_for_partners(
            order.partner_id, order.lines.product_id, order.company_id)
        self.assertEqual(treatment.covered_until, self.today + timedelta(days=30))

    def test_sale_order_counts_as_a_purchase(self):
        treatment = self._treatment(daily_units=2)
        order = self.env['sale.order'].create({
            'partner_id': self.patient.id,
            'order_line': [(0, 0, {'product_id': self.generic.id, 'product_uom_qty': 60})],
        })
        order.action_confirm()
        self.assertEqual(treatment.covered_until, self.today + timedelta(days=30))
        self.assertEqual(treatment.refill_state, 'ok')

    def test_due_treatments_for_the_pos(self):
        self.open_new_session()
        treatment = self._treatment()
        self._pos_purchase(self.brand, 30, 27)
        cashier = self.env['res.users'].create({
            'name': 'Cajera', 'login': 'cajera_care',
            'group_ids': [(6, 0, [self.env.ref('point_of_sale.group_pos_user').id])]})
        due = self.env['pharmacy.treatment'].with_user(cashier).get_pos_due_treatments(
            self.patient.id, self.config.id)
        self.assertEqual([d['id'] for d in due], [treatment.id])
        self.assertEqual(due[0]['refill_state'], 'due')
        self.assertEqual(due[0]['product_tmpl_id'], self.brand.product_tmpl_id.id)

    def test_due_treatments_only_for_pos_staff(self):
        self.open_new_session()
        self._treatment()
        outsider = self.env['res.users'].create({
            'name': 'Sin caja', 'login': 'sin_caja_care',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        with self.assertRaises(AccessError):
            self.env['pharmacy.treatment'].with_user(outsider).get_pos_due_treatments(
                self.patient.id, self.config.id)

    def test_whatsapp_link(self):
        treatment = self._treatment()
        self.assertTrue(treatment.whatsapp_url.startswith('https://wa.me/51987654321?text='))
        action = treatment.action_whatsapp()
        self.assertEqual(action['url'], treatment.whatsapp_url)

    def test_one_active_treatment_per_product(self):
        self._treatment()
        with self.assertRaises(ValidationError):
            self._treatment()

    def test_create_from_prescription(self):
        prescriber = self.env['res.partner'].create({
            'name': 'Dra. Ana Torres', 'pharmacy_is_prescriber': True,
            'pharmacy_prescriber_license': '067890'})
        prescription = self.env['pharmacy.prescription'].create({
            'prescriber_id': prescriber.id, 'patient_id': self.patient.id,
            'line_ids': [(0, 0, {'product_id': self.generic.id, 'quantity': 30,
                                 'posology': '1 tableta cada 24 horas'})],
        })
        prescription.action_validate()
        prescription.action_create_treatments()
        treatment = prescription.treatment_ids
        self.assertEqual(len(treatment), 1)
        self.assertEqual(treatment.product_id, self.generic)
        self.assertEqual(treatment.posology, '1 tableta cada 24 horas')
        # Otra vez: no duplica el tratamiento activo.
        prescription.action_create_treatments()
        self.assertEqual(len(prescription.treatment_ids), 1)
        other = prescription.copy()
        other.action_validate()
        with self.assertRaises(UserError):
            other.action_create_treatments()
