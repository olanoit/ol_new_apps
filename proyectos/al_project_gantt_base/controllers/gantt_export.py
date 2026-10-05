# -*- coding: utf-8 -*-
"""Descarga del diagrama en Excel.

Vive en el módulo base —y no en cada interfaz— porque el fichero es el mismo
para las dos: duplicar la ruta solo abriría dos superficies que mantener. El
control de acceso lo hace el propio servicio de datos (`_check_gantt_access` y
las reglas de `project`), igual que en la pantalla.
"""
import json
from datetime import datetime

from odoo import _, http
from odoo.exceptions import UserError
from odoo.http import content_disposition, request


class GanttExportController(http.Controller):

    @http.route('/al_project_gantt/export/xlsx', type='http', auth='user')
    def export_xlsx(self, project_ids=None, options=None, **kwargs):
        """Devuelve el libro de Excel del conjunto que se está viendo."""
        try:
            ids = [int(value) for value in (project_ids or '').split(',') if value.strip()]
        except ValueError:
            raise UserError(_("Lista de proyectos no válida."))
        try:
            parsed_options = json.loads(options) if options else {}
        except ValueError:
            raise UserError(_("Opciones de exportación no válidas."))

        content = request.env['al.gantt.data'].export_xlsx(ids or None, parsed_options)
        filename = "gantt_%s.xlsx" % datetime.now().strftime('%Y%m%d_%H%M')
        return request.make_response(content, headers=[
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Length', len(content)),
            ('Content-Disposition', content_disposition(filename)),
        ])
