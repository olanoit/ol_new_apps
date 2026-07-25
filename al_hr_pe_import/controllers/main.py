# -*- coding: utf-8 -*-
"""Descarga HTTP de las plantillas Excel de los importadores.

El botón de descarga NO puede ser ``type="object"``: el cliente web
guarda el asistente antes de invocar el método, y en el paso 1 aún no
hay archivo ni configuración (``struct_id``, ``payslip_run_id``...), con
lo que el guardado falla y la plantilla nunca se genera. Como la
plantilla es justamente lo que se necesita ANTES de tener el archivo,
se sirve por una ruta HTTP que no depende de ningún registro guardado.
"""
import logging

from odoo import http
from odoo.http import content_disposition, request

_logger = logging.getLogger(__name__)

XLSX_MIMETYPE = ('application/vnd.openxmlformats-officedocument'
                 '.spreadsheetml.sheet')


class AlImportPayrollTemplateController(http.Controller):

    @http.route('/al_hr_pe_import/template/<string:wizard_model>',
                type='http', auth='user', methods=['GET'], readonly=False)
    def download_template(self, wizard_model, **kwargs):
        """Devuelve la plantilla del asistente ``wizard_model``.

        Solo se aceptan modelos transitorios que hereden el mixin de
        importación, y se exige al usuario permiso de creación sobre el
        asistente (mismo permiso que necesita para importar).
        """
        Model = request.env.get(wizard_model)
        if Model is None or not Model._transient or not hasattr(
                Model, '_build_xlsx_template'):
            raise request.not_found()

        Model.check_access('create')

        # Registro en memoria: la plantilla se construye solo con los
        # metadatos de la clase, no necesita datos del asistente.
        data, filename = Model.new({})._build_xlsx_template()
        return request.make_response(data, headers=[
            ('Content-Type', XLSX_MIMETYPE),
            ('Content-Disposition', content_disposition(filename)),
            ('Content-Length', len(data)),
        ])
