# -*- coding: utf-8 -*-
"""Datos del informe PDF del diagrama.

El PDF se compone en el servidor con QWeb y wkhtmltopdf: dibuja las mismas
filas y columnas de periodo que el Excel (`build_matrix`), de modo que los dos
formatos cuentan lo mismo.
"""
from odoo import api, models


class ReportGantt(models.AbstractModel):
    _name = 'report.al_project_gantt_base.report_gantt'
    _description = 'Gantt — informe PDF'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        options = data.get('options') or {}
        project_ids = data.get('project_ids') or list(docids or [])

        matrix = self.env['al.gantt.data'].build_matrix(project_ids or None, options)
        payload = matrix['payload']

        # Cabecera superior agrupada (mes o año). Se calcula aquí y no en la
        # plantilla: QWeb no es el sitio para acumular estado.
        groups = []
        for period in matrix['periods']:
            if groups and groups[-1]['label'] == period['group']:
                groups[-1]['count'] += 1
            else:
                groups.append({'label': period['group'], 'count': 1})

        colors = payload['colors']['states']
        legend = [{
            'label': state['label'],
            'color': (colors.get(state['value']) or payload['colors']['fallback'])['color'],
        } for state in payload['filters']['states']]

        return {
            'doc_ids': project_ids,
            'doc_model': 'project.project',
            'docs': self.env['project.project'].browse(project_ids),
            'matrix': matrix,
            'rows': matrix['rows'],
            'periods': matrix['periods'],
            'period_groups': groups,
            'legend': legend,
            'payload': matrix['payload'],
            'title': matrix['title'],
            'generated_on': matrix['generated_on'],
            # Ancho de cada columna de periodo: la tabla debe caber en la hoja.
            'period_width': round(62.0 / max(len(matrix['periods']), 1), 4),
        }
