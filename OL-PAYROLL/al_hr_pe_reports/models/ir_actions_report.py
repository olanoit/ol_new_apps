# -*- coding: utf-8 -*-
"""Boleta enviada por correo, cifrada con el documento del trabajador.

v18 cifraba el PDF con reportlab (``encrypt=``). QWeb-PDF no cifra: se
post-procesa el PDF ya renderizado, solo cuando lo pide el envío por
correo (contexto ``l10n_pe_encrypt_voucher``) y la compañía lo activó en
Parámetros principales. La impresión normal no cambia.
"""
import io

from odoo import models
from odoo.tools.pdf import PdfFileReader, PdfFileWriter


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        content, report_type = super()._render_qweb_pdf(
            report_ref, res_ids=res_ids, data=data)
        if not self.env.context.get('l10n_pe_encrypt_voucher') \
                or report_type != 'pdf' or not res_ids or len(res_ids) != 1:
            return content, report_type
        report = self._get_report(report_ref)
        if report.xml_id != 'al_hr_pe_reports.action_report_boleta_pago':
            return content, report_type
        payslip = self.env['hr.payslip'].browse(res_ids)
        password = (payslip.employee_id.sudo().identification_id or '').strip()
        if not password:
            return content, report_type
        return self._l10n_pe_encrypt_pdf(content, password), report_type

    @staticmethod
    def _l10n_pe_encrypt_pdf(content, password):
        reader = PdfFileReader(io.BytesIO(content), strict=False)
        writer = PdfFileWriter()
        for page in reader.pages:
            writer.add_page(page)
        writer.encrypt(password)
        stream = io.BytesIO()
        writer.write(stream)
        return stream.getvalue()
