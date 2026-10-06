# -*- coding: utf-8 -*-
from odoo import models


class AccountEdiDocument(models.Model):
    _inherit = 'account.edi.document'

    def _process_documents_web_services(self, job_count=None, with_commit=True):
        """Los comprobantes retenidos desde el TPV («Emitir a SUNAT: No»)
        no se envían: ni el cron ni el botón «Procesar ahora» los procesan
        mientras la casilla «Emisión SUNAT retenida» siga marcada en la
        factura. Otro usuario la desmarca desde el backend para liberar."""
        docs = self.filtered(lambda d: not d.move_id.l10n_pe_edi_hold)
        return super(AccountEdiDocument, docs)._process_documents_web_services(
            job_count=job_count, with_commit=with_commit)
