# -*- coding: utf-8 -*-
"""Plantilla de niveles de la obra (v1.5, M15-01).

Cada obra elige cuántos niveles tiene su árbol y cómo se llaman: Torre ›
Piso › Departamento › Ambiente › Mueble › Módulo, Etapa › Sótano ›
Estacionamiento, etc. Cada nivel tiene una *función* (agrupador, unidad,
ambiente, mueble o módulo) que es la que entiende el planificador; el
nombre es solo lo que se ve.

Reglas: una sola Unidad, un solo Ambiente y un solo Módulo por plantilla;
el Mueble es opcional; los agrupadores van siempre encima de la Unidad. El
último agrupador (el que agrupa unidades) cumple la función de piso.
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .common import LEVEL_ROLES, LEVELS

ROLE_ORDER = {'group': 0, 'unit': 1, 'space': 2, 'furniture': 3, 'module': 4}


class ConstructionLevelTemplate(models.Model):
    _name = 'construction.level.template'
    _description = 'Plantilla de niveles de la obra'
    _order = 'sequence, name, id'

    name = fields.Char(string='Plantilla', required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    line_ids = fields.One2many(
        'construction.level.template.line', 'template_id', string='Niveles', copy=True)
    summary = fields.Char(string='Niveles en orden', compute='_compute_summary')

    @api.depends('line_ids.name', 'line_ids.sequence')
    def _compute_summary(self):
        for template in self:
            template.summary = ' › '.join(template.line_ids.sorted('sequence').mapped('name'))

    @api.constrains('line_ids')
    def _check_lines(self):
        for template in self:
            lines = template.line_ids.sorted('sequence')
            roles = lines.mapped('role')
            for role in ('unit', 'space', 'module'):
                if roles.count(role) != 1:
                    raise ValidationError(self.env._(
                        'La plantilla %(template)s debe tener un solo nivel con la función '
                        '%(role)s.', template=template.name, role=dict(LEVEL_ROLES)[role]))
            if roles.count('furniture') > 1:
                raise ValidationError(self.env._(
                    'La plantilla %s tiene más de un nivel Mueble.', template.name))
            ranks = [ROLE_ORDER[role] for role in roles]
            if ranks != sorted(ranks):
                raise ValidationError(self.env._(
                    'Los niveles de la plantilla %s van en este orden: agrupadores, unidad, '
                    'ambiente, mueble (opcional) y módulo.', template.name))

    def _first_line(self, role):
        self.ensure_one()
        return self.line_ids.filtered(lambda l: l.role == role).sorted('sequence')[:1]


class ConstructionLevelTemplateLine(models.Model):
    _name = 'construction.level.template.line'
    _description = 'Nivel de la plantilla de la obra'
    _order = 'template_id, sequence, id'

    template_id = fields.Many2one(
        'construction.level.template', string='Plantilla', required=True, ondelete='cascade',
        index=True)
    sequence = fields.Integer(string='Orden', default=10)
    name = fields.Char(
        string='Nombre del nivel', required=True, translate=True,
        help='El que se ve en el árbol: Torre, Etapa, Bloque, Sótano, Piso…')
    role = fields.Selection(
        LEVEL_ROLES, string='Función', required=True, default='group',
        help='Agrupador: torre, etapa, piso, sótano (sin límite, siempre encima de la '
             'unidad). Unidad: departamento, ducto, estacionamiento… Ambiente: cocina, '
             'closet, baño. Mueble (opcional): mueble bajo, alto, torre de horno. Módulo: lo '
             'que se arma e instala.')
    level = fields.Selection(
        LEVELS, string='Nivel del planificador', compute='_compute_level',
        help='Función interna: el último agrupador (el que agrupa unidades) hace de piso.')

    @api.depends('role', 'sequence', 'template_id.line_ids.role', 'template_id.line_ids.sequence')
    def _compute_level(self):
        mapping = {'unit': 'apartment', 'space': 'space', 'furniture': 'furniture',
                   'module': 'module'}
        for line in self:
            if line.role != 'group':
                line.level = mapping.get(line.role, False)
                continue
            groups = line.template_id.line_ids.filtered(lambda l: l.role == 'group')
            last = max(groups, key=lambda l: (l.sequence, l.id), default=line)
            line.level = 'floor' if last == line else 'group'

    def _previous(self):
        """Nivel inmediatamente superior en la plantilla (vacío: la obra)."""
        self.ensure_one()
        lines = self.template_id.line_ids.sorted(lambda l: (l.sequence, l.id))
        index = list(lines).index(self)
        return lines[index - 1] if index else self.browse()
