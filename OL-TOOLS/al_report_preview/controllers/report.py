# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import content_disposition, request
from odoo.tools.safe_eval import safe_eval, time

from odoo.addons.web.controllers.report import ReportController


class ReportPreviewController(ReportController):

    @http.route()
    def report_routes(self, reportname, docids=None, converter=None, **data):
        """PDF en línea con su nombre de archivo cuando el cliente pide la vista previa.

        El reporte lo genera la ruta nativa. Solo con ``al_preview`` en la
        URL se agrega la cabecera ``inline``: ``/report/download`` llama a
        este mismo método sin ese parámetro y pone su propia cabecera de
        descarga (dos Content-Disposition distintos hacen que Chrome
        rechace la respuesta).
        """
        preview = data.pop('al_preview', None)
        response = super().report_routes(
            reportname, docids=docids, converter=converter, **data)
        if preview and converter == 'pdf':
            filename = self._al_preview_filename(reportname, docids)
            response.headers['Content-Disposition'] = content_disposition(
                f'{filename}.pdf', disposition_type='inline')
        return response

    def _al_preview_filename(self, reportname, docids):
        """Mismo nombre que la descarga nativa: ``print_report_name`` con un solo registro."""
        report = request.env['ir.actions.report']._get_report_from_name(reportname)
        ids = [int(i) for i in (docids or '').split(',') if i.isdigit()]
        if len(ids) == 1 and report.print_report_name:
            record = request.env[report.model].browse(ids)
            return safe_eval(report.print_report_name, {'object': record, 'time': time})
        return report.name
