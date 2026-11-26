# -*- coding: utf-8 -*-
from odoo import api, models


class AccountMoveSend(models.AbstractModel):
    _inherit = 'account.move.send'

    @api.model
    def _get_default_pdf_report_id(self, move):
        """Comprobante electrónico (A4) como formato predeterminado de las facturas peruanas.

        El botón Imprimir (``action_print_pdf``) y el asistente de envío por
        correo toman de aquí el reporte. Se respeta el orden nativo: si el
        cliente o el diario ya tienen un formato elegido, manda ese; solo se
        cambia el respaldo genérico ``account.account_invoices``.
        """
        partner = move.commercial_partner_id.with_company(move.company_id)
        journal = move.journal_id.with_company(move.company_id)
        if (
            move.country_code == 'PE'
            and not partner.invoice_template_pdf_report_id
            and not journal.invoice_template_pdf_report_id
        ):
            cpe_report = self.env.ref(
                'al_l10n_pe_invoice.report_cpe_invoice_a4', raise_if_not_found=False)
            if cpe_report and move._is_action_report_available(cpe_report):
                return cpe_report
        return super()._get_default_pdf_report_id(move)
