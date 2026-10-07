# -*- coding: utf-8 -*-
"""Boleta por correo cifrada con el documento del trabajador."""
import io

from odoo.tests import TransactionCase, tagged
from odoo.tools.pdf import PdfFileReader

from .test_audit_fixes import _PayslipCase


@tagged('post_install', '-at_install')
class TestVoucherEncrypt(TransactionCase, _PayslipCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_payslip()
        cls.env['hr.main.parameter'].create({'company_id': cls.company.id})
        cls.employee.identification_id = '70112233'
        cls.slip.compute_sheet()

    def _render(self, **context):
        Report = self.env['ir.actions.report'].with_context(
            force_report_rendering=True, **context)
        content, _type = Report._render_qweb_pdf(
            'al_hr_pe_reports.action_report_boleta_pago', [self.slip.id])
        return PdfFileReader(io.BytesIO(content), strict=False)

    def test_mail_copy_is_encrypted_with_the_document(self):
        reader = self._render(l10n_pe_encrypt_voucher=True)
        self.assertTrue(reader.is_encrypted)
        self.assertTrue(reader.decrypt('70112233'))

    def test_print_is_not_encrypted(self):
        self.assertFalse(self._render().is_encrypted)
