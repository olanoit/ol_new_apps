# -*- coding: utf-8 -*-
"""Colores del Gantt por estado de tarea, administrables (no incrustados)."""
from odoo import api, fields, models

#: Color de reserva para estados sin fila configurada.
FALLBACK_COLOR = '#9e9e9e'
FALLBACK_TEXT_COLOR = '#ffffff'


class GanttStateColor(models.Model):
    _name = 'al.gantt.state.color'
    _description = 'Gantt — color por estado de tarea'
    _order = 'sequence, id'

    name = fields.Char(string='Etiqueta', required=True, translate=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    state_key = fields.Char(
        string='Estado', required=True,
        help="Valor técnico de project.task.state (p. ej. 01_in_progress).",
    )
    color = fields.Char(
        string='Color de la barra', required=True, default='#7c7bad',
        help="Color CSS de la barra de la tarea (hexadecimal o nombre CSS).",
    )
    text_color = fields.Char(
        string='Color del texto', default=FALLBACK_TEXT_COLOR,
        help="Color CSS del texto sobre la barra.",
    )
    active = fields.Boolean(string='Activo', default=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía',
        help="Vacío: aplica a todas las compañías. Con valor: sobreescribe el "
             "color global para esa compañía.",
    )

    # Odoo 19 sustituyó _sql_constraints por models.Constraint.
    _state_company_uniq = models.Constraint(
        'UNIQUE(state_key, company_id)',
        'Ya existe un color para ese estado en esa compañía.',
    )

    @api.model
    def get_color_map(self):
        """Mapa ``{state_key: {'color', 'text_color'}}`` para el usuario actual.

        Las filas de la compañía activa tienen prioridad sobre las globales.
        Punto de extensión: sobrescribir para colorear por etapa, etiqueta, etc.
        """
        records = self.search([
            ('company_id', 'in', [False] + self.env.companies.ids),
        ])
        company_ids = self.env.companies.ids
        result = {}
        for record in records.sorted(key=lambda r: bool(r.company_id and r.company_id.id in company_ids)):
            result[record.state_key] = {
                'color': record.color,
                'text_color': record.text_color or FALLBACK_TEXT_COLOR,
            }
        return result

    @api.model
    def get_fallback(self):
        return {'color': FALLBACK_COLOR, 'text_color': FALLBACK_TEXT_COLOR}
