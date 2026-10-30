# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestPharmacyTreatmentTour(TestPointOfSaleHttpCommon):

    def start_tour(self, url_path, tour_name, step_delay=None, **kwargs):
        # Los pasos de los tours del núcleo usan los textos en inglés; la base
        # de migración está en es_PE y los usuarios de prueba lo heredan.
        if kwargs.get('login'):
            self.env['res.users'].search([('login', '=', kwargs['login'])]).lang = 'en_US'
        return super().start_tour(url_path, tour_name, step_delay=step_delay, **kwargs)

    def test_refill_offered_when_choosing_the_customer(self):
        product = self.env['product.product'].create({
            'name': 'Levotiroxina 100 mcg tableta', 'type': 'consu', 'available_in_pos': True,
            'list_price': 0.50, 'taxes_id': [(6, 0, [])],
        })
        patient = self.env['res.partner'].create({'name': 'Julia Ramos'})
        # Compró hace 40 días para 30: el tratamiento está atrasado.
        # Datos de la botica preparados por el administrador.
        env_sudo = self.env['base'].sudo().env
        order = env_sudo['sale.order'].create({
            'partner_id': patient.id,
            'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': 30})],
        })
        order.action_confirm()
        order.date_order = fields.Datetime.now() - timedelta(days=40)
        treatment = env_sudo['pharmacy.treatment'].create({
            'patient_id': patient.id, 'product_id': product.id, 'daily_units': 1,
            'date_start': fields.Date.today() - timedelta(days=60)})
        self.assertEqual(treatment.refill_state, 'late')

        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour('al_pharmacy_care_refill')

        pos_order = self.env['pos.order'].search(
            [('session_id', '=', self.main_pos_config.current_session_id.id)], limit=1)
        self.assertEqual(pos_order.partner_id, patient)
        self.assertEqual(pos_order.lines.product_id, product)
        # La venta de la caja cuenta como compra (la fecha exacta depende del
        # huso del navegador de la prueba).
        self.assertGreater(treatment.last_purchase_date,
                           fields.Date.today() - timedelta(days=2))
        self.assertEqual(treatment.refill_state, 'due')
