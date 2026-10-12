# -*- coding: utf-8 -*-
"""Importación masiva de constancias de depósito de detracciones."""
import base64
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.addons.al_account_base.tests.common import use_pe_company

HEADER = ('Tipo de Cuenta,Numero de Cuenta,Numero Constancia,Periodo Tributario,RUC Proveedor,'
          'Nombre Proveedor,Tipo de Documento Adquiriente,Numero de Documento Adquiriente,'
          'Nombre/Razon Social del Adquiriente,Fecha Pago,Monto Deposito,Tipo Bien,Tipo Operacion,'
          'Tipo de Comprobante,Serie de Comprobante,Numero de Comprobante,Numero de pago de Detracciones')


@tagged('post_install', '-at_install')
class TestDetractionImport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        cls.company = cls.env.company
        if not (cls.company.vat and len(cls.company.vat) == 11):
            cls.company.vat = '20512528458'
        Account = cls.env['account.account'].with_company(cls.company)
        cls.account_exp = Account.search([('account_type', '=', 'expense')], limit=1)
        cls.tax_purchase = cls.env['account.tax'].search([
            ('company_id', '=', cls.company.id), ('type_tax_use', '=', 'purchase'),
            ('amount', '=', 18.0)], limit=1)
        cls.journal_purchase = cls.env['account.journal'].create({
            'name': 'DET Importación Test', 'code': 'DTI', 'type': 'purchase',
            'company_id': cls.company.id, 'l10n_latam_use_documents': False})
        cls.journal_bank = cls.env['account.journal'].search(
            [('company_id', '=', cls.company.id), ('type', '=', 'bank')], limit=1)
        cls.partner = cls.env['res.partner'].create({
            'name': 'Detracción Importación SAC', 'vat': '20131312955'})
        cls.service = cls.env['product.product'].create({
            'name': 'Servicio Detracción Importación', 'type': 'service',
            'l10n_pe_detraction_type_id': cls.env.ref('al_l10n_pe_detraction.detraction_037').id})

    def _invoice(self, move_type, price):
        return self.env['account.move'].create({
            'move_type': move_type, 'partner_id': self.partner.id,
            'journal_id': self.journal_purchase.id, 'invoice_date': date(2025, 6, 10),
            'date': date(2025, 6, 10), 'ref': 'F001-00000555',
            'invoice_line_ids': [(0, 0, {
                'name': self.service.name, 'product_id': self.service.id, 'quantity': 1.0,
                'price_unit': price, 'account_id': self.account_exp.id,
                'tax_ids': [(6, 0, self.tax_purchase.ids)]})],
        })

    def _wizard(self, rows, **vals):
        content = '\n'.join([HEADER] + rows).encode()
        return self.env['l10n_pe.detraction.import.wizard'].create(dict({
            'file': base64.b64encode(content), 'filename': 'constancias.csv'}, **vals))

    def _row(self, constancy, supplier, buyer, serie, number, amount=120):
        return ('D,00-000-123456,%s,202506,%s,PROVEEDOR,6,%s,ADQUIRIENTE,15/06/2025,%s,037,01,01,%s,%s,'
                % (constancy, supplier, buyer, amount, serie, number))

    def test_import_purchase_constancy(self):
        bill = self._invoice('in_invoice', 1000.0)
        bill.action_post()
        wizard = self._wizard([self._row('231234567', self.partner.vat, self.company.vat,
                                         'F001', '555', bill.l10n_pe_detraction_amount)])
        self.assertIn('Por registrar', wizard.preview_html)
        wizard.action_import()
        self.assertEqual(bill.l10n_pe_detraction_number, '231234567')
        self.assertEqual(bill.l10n_pe_detraction_date, date(2025, 6, 15))
        # Volver a importar la misma constancia no la duplica.
        again = self._wizard([self._row('231234567', self.partner.vat, self.company.vat, 'F001', '555')])
        self.assertIn('Ya registrada', again.preview_html)
        with self.assertRaises(UserError):
            again.action_import()

    def test_import_with_deposit(self):
        bill = self._invoice('in_invoice', 1000.0)
        bill.action_post()
        self._wizard([self._row('231234568', self.partner.vat, self.company.vat, 'F001', '00000555',
                                bill.l10n_pe_detraction_amount)],
                     register_deposit=True, journal_id=self.journal_bank.id).action_import()
        self.assertEqual(bill.l10n_pe_detraction_number, '231234568')
        self.assertIn(bill.payment_state, ('partial', 'in_payment'))

    def test_unknown_document_and_bad_file(self):
        wizard = self._wizard([self._row('231234569', '20100070970', self.company.vat, 'F009', '1')])
        self.assertIn('No encontrado', wizard.preview_html)
        bad = self.env['l10n_pe.detraction.import.wizard'].create({
            'file': base64.b64encode(b'a,b,c\n1,2,3')})
        self.assertIn('alert-danger', bad.preview_html)
