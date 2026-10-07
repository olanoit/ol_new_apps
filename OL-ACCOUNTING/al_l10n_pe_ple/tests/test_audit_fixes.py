# -*- coding: utf-8 -*-
"""Correcciones de la auditoría del 27/09/2026 (PLE y RCE/RVIE)."""
import base64
from datetime import date
from types import SimpleNamespace

from odoo.exceptions import UserError, ValidationError
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase

from odoo.addons.al_l10n_pe_ple.models.rce_extractor import RCE_EXCLUDED_DOC_TYPES

from .test_rce_84_export import RceExportCommon

RUC_TEST = '20512528458'


@tagged('post_install', '-at_install')
class TestRceSelection(RceExportCommon):
    """Qué comprobantes van a cada registro y en qué periodo."""

    def _moves(self, month=3, non_domiciled=False):
        return self.env['l10n_pe.rce.extractor']._rce_moves(
            self.company, date(2026, month, 1), date(2026, month, 28),
            non_domiciled=non_domiciled)

    def _doc_bill(self, doc_code):
        doc = self.env['l10n_latam.document.type'].search(
            [('code', '=', doc_code), ('country_id', '=', self.env.ref('base.pe').id)],
            limit=1)
        if not doc:
            self.skipTest('sin tipo de documento %s en la localización' % doc_code)
        bill = self._create_bill(doc_code=doc_code, post=False)
        try:
            with self.env.cr.savepoint():
                bill.action_post()
        except (UserError, ValidationError):
            self.skipTest('la localización no admite el tipo %s en compras' % doc_code)
        return bill

    def test_excluded_types_constant(self):
        self.assertEqual(set(RCE_EXCLUDED_DOC_TYPES), {'00', '02', '91', '97', '98'})

    def test_doc_00_goes_only_to_85(self):
        """El tipo 00 es del 8.5: antes salía duplicado en los dos archivos."""
        bill = self._doc_bill('00')
        self.assertNotIn(bill, self._moves())
        self.assertIn(bill, self._moves(non_domiciled=True))

    def test_fee_receipt_02_is_not_in_84(self):
        """Los recibos por honorarios van al RHE, no al RCE."""
        bill = self._doc_bill('02')
        self.assertNotIn(bill, self._moves())

    def test_period_is_the_accounting_date(self):
        """Factura de febrero anotada en marzo: va al RCE de marzo."""
        bill = self._create_bill(post=False)
        bill.invoice_date = date(2026, 2, 25)
        bill.date = date(2026, 3, 2)
        bill.action_post()
        self.assertEqual(bill.date, date(2026, 3, 2))
        self.assertIn(bill, self._moves(month=3))
        self.assertNotIn(bill, self._moves(month=2))

    def test_cancelled_bills_are_not_reported(self):
        """Ni el borrador cancelado ni el emitido y anulado van al RCE: la
        nota 2 del anexo 11 (RS 040-2022) prohíbe anotar los anulados (la
        regla de anotarlos en cero es solo del RVIE)."""
        draft = self._create_bill(post=False)
        draft.button_cancel()
        issued = self._create_bill()
        issued.button_draft()
        issued.button_cancel()
        moves = self._moves()
        self.assertNotIn(draft, moves)
        self.assertNotIn(issued, moves)

    def test_report_header_line_is_empty(self):
        """La línea cabecera del informe no muestra los datos de una factura."""
        self._create_bill(price=777.0)
        handler = self.env['l10n_pe.tax.ple.8.1.report.handler'].with_company(
            self.company)
        options = self.report.get_options({
            'date': {'date_from': '2026-03-01', 'date_to': '2026-03-31',
                     'filter': 'custom', 'mode': 'range'},
            'selected_variant_id': self.report.id,
        })
        header = handler._get_ple_report_data(options, None)
        self.assertIsInstance(header, dict)
        self.assertFalse(any(header.values()), header)
        self.assertTrue(handler._get_ple_report_data(options, 'move_id'))

    def test_posted_classification_is_not_rewritten(self):
        """Cambiar la clasificación del producto no toca lo ya publicado."""
        bill = self._create_bill()
        self.assertEqual(bill.l10n_pe_rce_classification, '5')
        self.product.product_tmpl_id.l10n_pe_rce_classification = '1'
        self.assertEqual(bill.l10n_pe_rce_classification, '5')
        draft = self._create_bill(post=False)
        self.assertEqual(draft.l10n_pe_rce_classification, '1')


@tagged('post_install', '-at_install')
class TestPleWizardFixes(TransactionCase):
    """Formatos del asistente: moneda, apuntes de sección, series y compañías."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        if not (cls.company.vat and len(cls.company.vat) == 11):
            cls.company.vat = RUC_TEST
        cls.company.l10n_pe_ple_simplified = True
        cls.journal = cls.env['account.journal'].create({
            'name': 'PLE auditoría ventas', 'code': 'PAV', 'type': 'sale',
            'company_id': cls.company.id, 'l10n_latam_use_documents': False,
        })
        cls.tax = cls.env['account.tax'].search([
            ('company_id', '=', cls.company.id), ('type_tax_use', '=', 'sale'),
            ('amount', '=', 18.0), ('amount_type', '=', 'percent'),
        ], limit=1)
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente Auditoría SAC', 'vat': '20131312955'})
        cls.usd = cls.env.ref('base.USD')
        cls.usd.active = True
        # 1 USD = 4 soles el día de la factura (la base puede traer tasas)
        Rate = cls.env['res.currency.rate']
        rate = Rate.search([('name', '=', date(2025, 3, 20)),
                            ('currency_id', '=', cls.usd.id),
                            ('company_id', '=', cls.company.id)])
        if rate:
            rate.rate = 0.25
        else:
            Rate.create({'name': date(2025, 3, 20), 'rate': 0.25,
                         'currency_id': cls.usd.id, 'company_id': cls.company.id})

    def _wizard(self, **kwargs):
        values = {'year': 2025, 'month': '03', 'export_71': False,
                  'generate_xlsx': False}
        values.update(kwargs)
        return self.env['l10n_pe.ple.export.wizard'].create(values)

    def _rows(self, wizard, move):
        content = base64.b64decode(wizard.file_data).decode()
        return [line[:-1].split('|') for line in content.split('\r\n')
                if line and (str(move.id) in line.split('|')
                             or 'M%d' % move.id in line.split('|'))]

    def _invoice(self, currency=None, extra_lines=()):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'journal_id': self.journal.id,
            'currency_id': (currency or self.company.currency_id).id,
            'invoice_date': date(2025, 3, 20),
            'date': date(2025, 3, 20),
            'ref': 'F001-00000999',
            'invoice_line_ids': list(extra_lines) + [(0, 0, {
                'name': 'Servicio', 'quantity': 1.0, 'price_unit': 100.0,
                'tax_ids': [(6, 0, self.tax.ids)],
            })],
        })
        invoice.action_post()
        return invoice

    def test_142_foreign_currency_is_in_soles(self):
        """Base, IGV y total en soles aunque la factura esté en dólares."""
        if not self.tax:
            self.skipTest('sin IGV 18% en la compañía')
        invoice = self._invoice(currency=self.usd)
        wizard = self._wizard(export_142=True)
        wizard.action_export()
        row = self._rows(wizard, invoice)[0]
        self.assertEqual(row[12], '400.00', 'BI gravada en soles')
        self.assertEqual(row[13], '72.00', 'IGV en soles')
        self.assertEqual(row[16], '472.00', 'total en soles')
        self.assertEqual(row[17], 'USD')
        self.assertEqual(row[18], '4.000')

    def test_52_skips_subsection_lines(self):
        invoice = self._invoice(extra_lines=[
            (0, 0, {'display_type': 'line_section', 'name': 'Sección'}),
            (0, 0, {'display_type': 'line_subsection', 'name': 'Subsección'}),
        ])
        wizard = self._wizard(export_52=True)
        wizard.action_export()
        rows = self._rows(wizard, invoice)
        self.assertTrue(rows)
        self.assertFalse([row for row in rows if not row[3]],
                         'ninguna fila del 5.2 sin cuenta contable')

    def test_91_series_come_from_the_document_number(self):
        """El name LATAM («F F001-…») no contamina la serie del CdP."""

        class Invoices(list):
            def filtered(self, func):
                return Invoices(item for item in self if func(item))

        invoice = SimpleNamespace(
            state='posted', name='F F001-00000045',
            l10n_latam_document_number='F001-00000045',
            l10n_latam_document_type_id=SimpleNamespace(code='01'),
            invoice_date=date(2025, 3, 5))
        picking = SimpleNamespace(
            l10n_pe_consignment='out_sale',
            sale_id=SimpleNamespace(invoice_ids=Invoices([invoice])))
        cdp = self._wizard()._consignment_cdp(picking)
        self.assertEqual(cdp, ('01', '05/03/2025', 'F001', '00000045'))

    def test_capture_records_are_isolated_by_company(self):
        other = self.env['res.company'].create({'name': 'Otra compañía PLE'})
        user = new_test_user(
            self.env, login='ple_accountant', groups='account.group_account_user',
            company_id=self.company.id)
        Withholding = self.env['l10n_pe.ple.withholding']
        own = Withholding.create({
            'date': date(2025, 3, 5), 'partner_id': self.partner.id,
            'gross_amount': 100.0, 'company_id': self.company.id})
        foreign = Withholding.create({
            'date': date(2025, 3, 5), 'partner_id': self.partner.id,
            'gross_amount': 100.0, 'company_id': other.id})
        visible = Withholding.with_user(user).search([('id', 'in', (own | foreign).ids)])
        self.assertEqual(visible, own)
