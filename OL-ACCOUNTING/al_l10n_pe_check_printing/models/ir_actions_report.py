from odoo import models

from .check_layout import REPORT_NAME


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def get_paperformat(self):
        # El cheque se imprime en el tamaño de la hoja de su formato.
        paperformat_id = self.env.context.get('l10n_pe_check_paperformat_id')
        if paperformat_id and self.report_name == REPORT_NAME:
            return self.env['report.paperformat'].browse(paperformat_id)
        return super().get_paperformat()

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        report = self._get_report(report_ref)
        if report.report_name == REPORT_NAME:
            test_layout_id = (data or {}).get('l10n_pe_test_layout_id')
            if test_layout_id:
                layout = self.env['l10n_pe.check.layout'].browse(test_layout_id)
            else:
                ids = [res_ids] if isinstance(res_ids, int) else (res_ids or [])
                layout = self.env['l10n_latam.check'].browse(ids)._l10n_pe_check_layout()
            self = self.with_context(l10n_pe_check_paperformat_id=layout.paperformat_id.id)
        return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
