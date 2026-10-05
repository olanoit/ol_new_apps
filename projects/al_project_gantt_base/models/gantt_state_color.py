# -*- coding: utf-8 -*-
"""Colores del Gantt por estado de tarea, administrables (no incrustados)."""
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

#: Hexadecimal (#rgb, #rrggbb, con alfa) o un nombre CSS simple. Nada más:
#: el valor acaba en atributos `style` (pantalla y PDF) y un `;` o un `url()`
#: permitiría inyectar reglas o que wkhtmltopdf cargue recursos externos.
COLOR_RE = re.compile(r'^(#[0-9a-fA-F]{3,8}|[a-zA-Z]{3,30})$')

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
    # En SQL dos NULL son distintos: la restricción anterior no impide dos
    # colores globales (sin compañía) para el mismo estado.
    _state_global_uniq = models.UniqueIndex(
        '(state_key) WHERE company_id IS NULL',
        'Ya existe un color global para ese estado.',
    )

    @api.constrains('color', 'text_color')
    def _check_css_colors(self):
        for record in self:
            for value in (record.color, record.text_color):
                if value and not COLOR_RE.match(value.strip()):
                    raise ValidationError(_(
                        "«%s» no es un color válido: use hexadecimal (#1a7d3d) o un nombre CSS (red).",
                        value,
                    ))

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
