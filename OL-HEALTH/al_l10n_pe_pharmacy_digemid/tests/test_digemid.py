# -*- coding: utf-8 -*-
import io
from datetime import date, datetime, timedelta

import openpyxl

from odoo import fields
from odoo.exceptions import UserError

from odoo.addons.al_l10n_pe_pharmacy_digemid.models.pharmacy_observatory import add_business_days
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
        # Un principio activo que no está en los datos de demostración: así el
        # listado de genéricos y las existencias son solo los de la prueba.
        cls.ingredient = cls.env['pharmacy.ingredient']._get_or_create('Sitagliptina')
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
        product = self._product('Glucophage 850 mg', 'innovator', 1.5, code='DIG-0001', qty=10)
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

    def test_linked_company_poster(self):
        own = self._product('Metformina Botica 850 mg', 'generic_brand', 0.4)
        own.pharmacy_linked_company = True
        self._product('Glucophage 850 mg', 'innovator', 1.5)
        html, _ = self.env['ir.actions.report']._render_qweb_html(
            'al_l10n_pe_pharmacy_digemid.report_linked_poster', self.env.company.ids)
        self.assertIn(b'Metformina Botica 850 mg', html)
        self.assertNotIn(b'Glucophage 850 mg', html)

    # Envíos al Observatorio ----------------------------------------------
    def _rows_of(self, wizard):
        workbook = openpyxl.load_workbook(io.BytesIO(wizard.file_data.content))
        sheet = workbook['Hoja1']
        return [[cell.value for cell in row] for row in sheet.iter_rows()]

    def test_observatory_full_load_then_changes(self):
        tax = self.env['account.tax'].create({
            'name': 'IGV 18 % (prueba)', 'amount': 18, 'type_tax_use': 'sale',
            'company_id': self.env.company.id})
        product = self._product('Sitagliptina 50 mg', 'generic_dci', 10.0, code='DIG-0100', qty=20)
        product.taxes_id = tax
        device = self._product('Glucómetro', 'generic_dci', 50.0, code='DIG-0101', qty=5)
        device.pharmacy_digemid_class = 'device'
        Export = self.env['pharmacy.observatory.export']
        Submission = self.env['pharmacy.observatory.submission']
        first = Export.create({'warehouse_id': self.warehouse.id})
        self.assertTrue(first.needs_full)
        self.assertEqual(first.scope, 'all')
        first.action_export()
        rows = self._rows_of(first)
        self.assertEqual(rows[0], ['CodEstab', 'CodProd', 'Precio 1', 'Precio 2'])
        mine = [row for row in rows[1:] if row[1] in ('DIG-0100', 'DIG-0101')]
        # Con IGV, el código del establecimiento como texto y sin el dispositivo médico.
        self.assertEqual(mine, [['0012345', 'DIG-0100', 11.8, 11.8]])
        sent = Submission.search([('warehouse_id', '=', self.warehouse.id)])
        self.assertEqual((sent.state, sent.mode), ('sent', 'full'))
        self.assertEqual(sent.rectification_deadline,
                         self.env.company._pharmacy_add_business_days(fields.Date.today(), 7))

        # Como si la carga hubiera sido hace un rato.
        sent.date_sent = fields.Datetime.now() - timedelta(minutes=5)
        self.env['pharmacy.observatory.price'].search([]).filtered(
            lambda p: p.date >= sent.date_sent and p.product_tmpl_id != product.product_tmpl_id
        ).write({'date': sent.date_sent - timedelta(minutes=1)})
        second = Export.create({'warehouse_id': self.warehouse.id})
        self.assertFalse(second.needs_full)
        self.assertEqual(second.scope, 'pending')
        product.list_price = 12.0
        second.action_export()
        self.assertEqual([row for row in self._rows_of(second)[1:]],
                         [['0012345', 'DIG-0100', 14.16, 14.16]])
        self.assertEqual(Submission.search([('warehouse_id', '=', self.warehouse.id)]).mapped('mode'),
                         ['changes', 'full'])

    def test_first_load_of_the_month_is_full(self):
        self._product('Sitagliptina 50 mg', 'generic_dci', 10.0, code='DIG-0102', qty=5)
        wizard = self.env['pharmacy.observatory.export'].create({'warehouse_id': self.warehouse.id})
        wizard.scope = 'pending'
        with self.assertRaises(UserError):
            wizard.action_export()

    def test_monthly_reminder_for_the_director(self):
        user = self.env['res.users'].create({'name': 'Q.F. Directora', 'login': 'qf_directora_obs'})
        director = self.env['hr.employee'].create({
            'name': 'Q.F. Directora', 'user_id': user.id, 'pharmacy_role': 'pharmacist'})
        self.warehouse.pharmacy_director_id = director
        self.env.company.pharmacy_observatory_reminder_day = 1
        Submission = self.env['pharmacy.observatory.submission']
        Submission._cron_monthly_reminder()
        draft = Submission.search([('warehouse_id', '=', self.warehouse.id)])
        self.assertEqual(draft.state, 'draft')
        self.assertEqual(draft.period, fields.Date.today().replace(day=1))
        self.assertEqual(draft.activity_ids.user_id, user)
        # Una sola vez por mes.
        Submission._cron_monthly_reminder()
        self.assertEqual(Submission.search_count([('warehouse_id', '=', self.warehouse.id)]), 1)

    def test_rectification_counts_business_days(self):
        # Viernes 16/10/2026 + 7 días hábiles = martes 27/10/2026.
        self.assertEqual(add_business_days(date(2026, 10, 16), 7), date(2026, 10, 27))

    def test_rectification_skips_company_holidays(self):
        company = self.env.company
        calendar = company.resource_calendar_id or self.env['resource.calendar'].create(
            {'name': 'Lima', 'tz': 'America/Lima'})
        company.resource_calendar_id = calendar
        calendar.tz = 'America/Lima'
        # Feriado el martes 20/10/2026: de 00:00 a 00:00 del día siguiente en Lima (UTC−5).
        leave = self.env['resource.calendar.leaves'].create({
            'name': 'Feriado de prueba', 'calendar_id': calendar.id, 'company_id': company.id,
            'date_from': datetime(2026, 10, 20, 5, 0), 'date_to': datetime(2026, 10, 21, 5, 0)})
        # Otros módulos ajustan las horas al crear según el huso del usuario.
        leave.write({'date_from': datetime(2026, 10, 20, 5, 0), 'date_to': datetime(2026, 10, 21, 5, 0)})
        self.assertEqual((leave.date_from, leave.date_to),
                         (datetime(2026, 10, 20, 5, 0), datetime(2026, 10, 21, 5, 0)))
        self.assertEqual(company._pharmacy_holidays(date(2026, 10, 16), date(2026, 10, 31)),
                         {date(2026, 10, 20)})
        # Viernes 16/10 + 7 días hábiles sin el feriado = miércoles 28/10.
        self.assertEqual(company._pharmacy_add_business_days(date(2026, 10, 16), 7), date(2026, 10, 28))

