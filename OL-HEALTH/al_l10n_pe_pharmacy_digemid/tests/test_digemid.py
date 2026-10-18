# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestDigemid(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.env.company.id)], limit=1)
        cls.warehouse.pharmacy_establishment_code = '0012345'
        cls.ingredient = cls.env['pharmacy.ingredient']._get_or_create('Metformina')
        cls.tablet = cls.env.ref('al_pharmacy_base.dosage_form_tablet')

    def _product(self, name, product_type, price, code=False, qty=0):
        product = self.env['product.product'].create({
            'name': name, 'is_storable': True, 'pharmacy_ok': True, 'list_price': price,
            'pharmacy_product_type': product_type, 'pharmacy_digemid_code': code,
            'pharmacy_dosage_form_id': self.tablet.id,
            'pharmacy_ingredient_line_ids': [(0, 0, {'ingredient_id': self.ingredient.id,
                                                     'strength': 850, 'strength_unit': 'mg'})],
        })
        if qty:
            self.env['stock.quant']._update_available_quantity(product, self.warehouse.lot_stock_id, qty)
        return product

    # Observatorio ----------------------------------------------------------
    def test_price_change_is_pending_until_exported(self):
        product = self._product('Glucophage 850 mg', 'innovator', 1.5, code='DIG-0001')
        Price = self.env['pharmacy.observatory.price']
        pending = Price.search([('product_tmpl_id', '=', product.product_tmpl_id.id)])
        self.assertEqual((pending.state, pending.unit_price), ('pending', 1.5))
        product.list_price = 1.8
        pending = Price.search([('product_tmpl_id', '=', product.product_tmpl_id.id)])
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending.unit_price, 1.8)
        self.env['pharmacy.presentation'].create({
            'product_tmpl_id': product.product_tmpl_id.id, 'name': 'Caja', 'factor': 100,
            'price': 150.0}).price = 140.0
        self.assertEqual(pending.package_price, 140.0)
        wizard = self.env['pharmacy.observatory.export'].create({'warehouse_id': self.warehouse.id})
        wizard.action_export()
        self.assertTrue(wizard.file_data)
        self.assertEqual(pending.state, 'reported')

    def test_export_needs_establishment_code(self):
        self._product('Glucophage 850 mg', 'innovator', 1.5, code='DIG-0002')
        self.warehouse.pharmacy_establishment_code = False
        wizard = self.env['pharmacy.observatory.export'].create({'warehouse_id': self.warehouse.id})
        with self.assertRaises(UserError):
            wizard.action_export()

    # Genéricos -------------------------------------------------------------
    def test_generic_compliance(self):
        self.env['pharmacy.essential.medicine'].create({
            'ingredient_id': self.ingredient.id, 'strength': '850 mg', 'dosage_form_id': self.tablet.id})
        self._product('Glucophage 850 mg', 'innovator', 1.5, qty=50)
        generic = self._product('Metformina 850 mg tableta', 'generic_dci', 0.3, qty=100)
        report = self.env['pharmacy.generic.compliance'].create({'warehouse_id': self.warehouse.id})
        report.action_compute()
        line = report.line_ids.filtered(lambda l: l.item_id.ingredient_id == self.ingredient)
        self.assertTrue(line.compliant)
        self.assertIn(generic.product_tmpl_id, line.generic_product_ids)
        self.env['stock.quant']._update_available_quantity(generic, self.warehouse.lot_stock_id, -100)
        report.action_compute()
        line = report.line_ids.filtered(lambda l: l.item_id.ingredient_id == self.ingredient)
        self.assertFalse(line.compliant)

    # Reacciones adversas ---------------------------------------------------
    def test_adverse_event_deadline_and_logbook(self):
        product = self._product('Metformina 850 mg tableta', 'generic_dci', 0.3)
        detected = fields.Datetime.now()
        Event = self.env['pharmacy.adverse.event']
        serious = Event.create({'patient_initials': 'R.M.Q.', 'product_id': product.id,
                                'reaction': 'Acidosis láctica', 'severity': 'serious',
                                'date_detected': detected})
        self.assertEqual(serious.deadline, detected + timedelta(hours=24))
        mild = Event.create({'patient_initials': 'J.P.', 'product_id': product.id,
                             'reaction': 'Náuseas', 'date_detected': detected - timedelta(days=20)})
        self.assertTrue(mild.overdue)
        entry = self.env['pharmacy.logbook.entry'].search(
            [('res_model', '=', 'pharmacy.adverse.event'), ('res_id', '=', serious.id)])
        self.assertEqual(entry.entry_type, 'adverse_event')
        serious.action_mark_notified()
        self.assertEqual(serious.state, 'notified')

    # IGV y reportes --------------------------------------------------------
    def test_igv_regime_sets_exonerated_tax(self):
        tax = self.env['product.template']._pharmacy_exonerated_sale_tax()
        if not tax:
            self.skipTest('La compañía de la prueba no tiene el plan contable peruano.')
        with Form(self.env['product.template']) as form:
            form.name = 'Imatinib 400 mg tableta'
            form.pharmacy_igv_regime = 'oncology_hiv'
            self.assertEqual(form.taxes_id[:], tax)

    def test_price_list_report(self):
        self._product('Glucophage 850 mg', 'innovator', 1.5)
        self._product('Metformina 850 mg tableta', 'generic_dci', 0.3)
        html, _ = self.env['ir.actions.report']._render_qweb_html(
            'al_l10n_pe_pharmacy_digemid.report_price_list', self.env.company.ids)
        self.assertLess(html.index(b'Metformina 850 mg tableta'), html.index(b'Glucophage 850 mg'))
