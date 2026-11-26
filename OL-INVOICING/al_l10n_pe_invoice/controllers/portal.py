# -*- coding: utf-8 -*-
from odoo.http import request

from odoo.addons.account.controllers.portal import PortalAccount


class PortalAccountPE(PortalAccount):

    def _show_report(self, model, report_type, report_ref, download=False):
        """Vista previa de la factura con el mismo formato que Imprimir y Enviar.

        El portal nativo solo mira el formato del cliente y, si no hay, usa el
        genérico ``account.account_invoices``. Cuando cae en el genérico se
        pregunta a ``account.move.send`` por el formato predeterminado, que en
        compañías peruanas es el comprobante electrónico (A4) y respeta el
        formato elegido en el diario.
        """
        if (
            model._name == 'account.move'
            and len(model) == 1
            and report_ref == 'account.account_invoices'
        ):
            # ``model`` ya llega en sudo tras validar el acceso o el token
            # (_document_check_access): solo se lee el nombre del reporte.
            default_report = request.env['account.move.send'].sudo()\
                ._get_default_pdf_report_id(model)
            if default_report:
                report_ref = default_report.report_name
        return super()._show_report(model, report_type, report_ref, download=download)
