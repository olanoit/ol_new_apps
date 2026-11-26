# -*- coding: utf-8 -*-
from odoo import api, fields, models

PREVIEW_SCOPE_PARAM = 'al_report_preview.scope'
PREVIEW_SCOPE_DEFAULT = 'all'


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    al_preview_mode = fields.Selection(
        selection=[
            ('default', 'Según el ajuste general'),
            ('preview', 'Abrir en el navegador'),
            ('download', 'Descargar'),
        ],
        string='Al imprimir',
        default='default', required=True,
        help="Qué hace Odoo con el PDF de este reporte.\n"
             "• Según el ajuste general: lo que diga Ajustes ▸ Ajustes "
             "generales ▸ Reportes PDF.\n"
             "• Abrir en el navegador: se muestra en una pestaña nueva.\n"
             "• Descargar: se descarga, como en Odoo estándar.")
    al_preview_in_browser = fields.Boolean(
        string='Se abre en el navegador',
        compute='_compute_al_preview_in_browser',
        help="Resultado de combinar la opción del reporte con el ajuste general.")

    @api.depends('al_preview_mode', 'report_type')
    def _compute_al_preview_in_browser(self):
        # sudo: el parámetro del sistema es un ajuste global que cualquier
        # usuario que imprime necesita conocer; solo se lee ese valor.
        param_sudo = self.env['ir.config_parameter'].sudo()
        preview_all = param_sudo.get_param(
            PREVIEW_SCOPE_PARAM, PREVIEW_SCOPE_DEFAULT) == 'all'
        for report in self:
            if report.report_type != 'qweb-pdf':
                report.al_preview_in_browser = False
            elif report.al_preview_mode == 'default':
                report.al_preview_in_browser = preview_all
            else:
                report.al_preview_in_browser = report.al_preview_mode == 'preview'

    def _get_readable_fields(self):
        # El cliente web lee esta marca al cargar la acción del menú Imprimir.
        return super()._get_readable_fields() | {'al_preview_in_browser'}

    def report_action(self, docids, data=None, config=True):
        """Marca la acción que devuelven los botones (p. ej. Imprimir de la factura).

        Estas acciones se arman en Python y no pasan por la lectura de
        ``_get_readable_fields``; sin la marca el cliente las descargaría.
        """
        action = super().report_action(docids, data=data, config=config)
        if len(self) != 1 or not isinstance(action, dict):
            return action
        if action.get('type') == 'ir.actions.report':
            action['al_preview_in_browser'] = self.al_preview_in_browser
        else:
            # Asistente de diseño del documento: la acción del reporte viaja
            # dentro de su contexto y se ejecuta al cerrarlo.
            context = action.get('context')
            nested = isinstance(context, dict) and context.get('report_action')
            if isinstance(nested, dict):
                nested['al_preview_in_browser'] = self.al_preview_in_browser
        return action
