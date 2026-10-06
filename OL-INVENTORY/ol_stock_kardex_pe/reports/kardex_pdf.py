from odoo import api, models


class ReportKardex(models.AbstractModel):
    """PDF del kardex: sin datos no se imprime un documento en blanco."""
    _name = 'report.ol_stock_kardex_pe.report_kardex'
    _description = 'Kardex SUNAT (PDF)'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['l10n_pe.kardex.report.wizard'].browse(docids)
        docs._check_has_data()
        return {
            'doc_ids': docids,
            'doc_model': 'l10n_pe.kardex.report.wizard',
            'docs': docs,
        }
