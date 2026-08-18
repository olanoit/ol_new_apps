# -*- coding: utf-8 -*-
"""Asistente de depósito masivo de detracciones."""
import base64
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from odoo.addons.al_l10n_pe_detraction.services import bn_txt

RUC_COMPANY = '20512528458'
RUC_SUPPLIER = '20601034809'
BN_ACCOUNT = '00071234567'


@tagged('post_install', '-at_install')
class TestDetractionTxtWizard(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.company.vat = RUC_COMPANY
        cls.company.partner_id.name = 'SERVICIOS ANDINOS DEMO S.A.C.'
        cls.company.partner_id.l10n_pe_detraction_account = BN_ACCOUNT
        cls.detraction_type = cls.env['l10n_pe.detraction.type'].search(
            [], limit=1)
        cls.supplier = cls.env['res.partner'].create({
            'name': 'PROVEEDOR SPOT S.A.C.',
            'vat': RUC_SUPPLIER,
            'country_id': cls.env.ref('base.pe').id,
            'l10n_latam_identification_type_id': cls.env.ref('l10n_pe.it_RUC').id,
            'l10n_pe_detraction_account': BN_ACCOUNT,
        })
        cls.product = cls.env['product.product'].create({'name': 'Servicio SPOT'})
        cls.product.product_tmpl_id.l10n_pe_detraction_type_id = \
            cls.detraction_type.id
        cls.purchase_tax = cls.env['account.tax'].search([
            ('company_id', '=', cls.company.id),
            ('type_tax_use', '=', 'purchase'),
            ('amount', '=', 18),
        ], limit=1)

    _sequence = 0

    def _create_bill(self, price=5000.0, post=True):
        doc_type = self.env['l10n_latam.document.type'].search(
            [('code', '=', '01'),
             ('country_id', '=', self.env.ref('base.pe').id)], limit=1)
        type(self)._sequence += 1
        bill = self.env['account.move'].with_company(self.company).create({
            'move_type': 'in_invoice',
            'partner_id': self.supplier.id,
            'invoice_date': date(2026, 3, 9),
            'date': date(2026, 3, 9),
            'l10n_latam_document_type_id': doc_type.id,
            'l10n_latam_document_number': 'F001-%08d' % self._sequence,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 1,
                'price_unit': price,
                'tax_ids': [(6, 0, self.purchase_tax.ids)]
                if self.purchase_tax else False,
            })],
        })
        if post:
            bill.action_post()
        return bill

    def _wizard(self, **kwargs):
        values = {
            'company_id': self.company.id,
            'mode': 'acquirer',
            'batch_number': '260001',
            'date_from': date(2026, 3, 1),
            'date_to': date(2026, 3, 31),
        }
        values.update(kwargs)
        return self.env['l10n_pe.detraction.txt.wizard'].with_company(
            self.company).create(values)

    def _content(self, wizard):
        return base64.b64decode(wizard.file_data).decode('latin-1')

    # ------------------------------------------------------------------
    # Generación
    # ------------------------------------------------------------------
    def test_generates_valid_file(self):
        self._create_bill()
        wizard = self._wizard()
        wizard.action_generate()
        content = self._content(wizard)
        self.assertEqual(bn_txt.check_structure(content), [],
                         'el archivo debe cumplir la estructura del banco')
        lines = [line for line in content.split('\r\n') if line]
        self.assertEqual(len(lines), 2, 'cabecera más un detalle')
        self.assertEqual(len(lines[0]), 68)
        self.assertEqual(len(lines[1]), 107)

    def test_header_totals_the_deposits(self):
        bill_a = self._create_bill()
        bill_b = self._create_bill()
        wizard = self._wizard()
        wizard.action_generate()
        header = self._content(wizard).split('\r\n')[0]
        total = (bill_a.l10n_pe_detraction_amount
                 + bill_b.l10n_pe_detraction_amount)
        self.assertEqual(header[53:68], bn_txt.amount(total),
                         'la cabecera totaliza los depósitos del lote')

    def test_acquirer_and_supplier_modes(self):
        self._create_bill()
        acquirer = self._wizard(mode='acquirer')
        acquirer.action_generate()
        self.assertEqual(self._content(acquirer)[0], '*')

        supplier = self._wizard(mode='supplier', batch_number='260002')
        # En modalidad proveedor se depositan las ventas propias; sin ventas
        # con detracción el asistente avisa en vez de generar un archivo vacío.
        with self.assertRaises(UserError):
            supplier.action_generate()

    def test_filename_includes_ruc_and_batch(self):
        self._create_bill()
        wizard = self._wizard()
        wizard.action_generate()
        self.assertEqual(wizard.file_name, 'D%s260001.txt' % RUC_COMPANY)

    # ------------------------------------------------------------------
    # Validaciones
    # ------------------------------------------------------------------
    def test_batch_number_must_be_six_digits(self):
        for wrong in ('26001', 'ABCDEF', '2600011'):
            with self.assertRaises(UserError,
                                   msg='«%s» no es un lote válido' % wrong):
                self._wizard(batch_number=wrong)

    def test_dates_must_be_ordered(self):
        with self.assertRaises(UserError):
            self._wizard(date_from=date(2026, 3, 31), date_to=date(2026, 3, 1))

    def test_supplier_without_bank_account_is_excluded(self):
        self._create_bill()
        self.supplier.l10n_pe_detraction_account = False
        wizard = self._wizard()
        with self.assertRaises(UserError):
            wizard.action_generate()

    def test_excluded_moves_are_reported(self):
        """Los comprobantes que no pueden incluirse se listan, no se ocultan."""
        self._create_bill()
        other = self.env['res.partner'].create({
            'name': 'PROVEEDOR SIN CUENTA S.A.C.',
            'vat': '20100070970',
            'country_id': self.env.ref('base.pe').id,
            'l10n_latam_identification_type_id': self.env.ref('l10n_pe.it_RUC').id,
        })
        bill = self._create_bill()
        bill.button_draft()
        bill.partner_id = other
        bill.action_post()

        wizard = self._wizard()
        wizard.action_generate()
        self.assertTrue(wizard.excluded_html,
                        'debe informarse por qué se excluyó el comprobante')
        self.assertIn('cuenta de detracciones', wizard.excluded_html)

    def test_no_moves_raises(self):
        wizard = self._wizard(date_from=date(2026, 7, 1),
                              date_to=date(2026, 7, 31))
        with self.assertRaises(UserError):
            wizard.action_generate()
