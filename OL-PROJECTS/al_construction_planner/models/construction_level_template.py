# -*- coding: utf-8 -*-
"""Plantilla de niveles de la obra (v1.5, M15-01; libre por rubro en v1.7,
M17-01).

Cada obra elige cuántos niveles tiene su árbol y cómo se llaman: Torre ›
Piso › Departamento › Ambiente › Mueble › Módulo en mobiliario, Disciplina ›
Subpartida › Partida › Actividad en una constructora, Área › Línea › Spool
en tuberías. Cada nivel tiene una *función* (agrupador, unidad de entrega,
nivel con etapas, subnivel o nivel de detalle) que es la que entiende el
planificador, y casillas con su comportamiento (lleva receta, se mide, se
valoriza, recibe avance); el nombre es solo lo que se ve.

Reglas: un solo nivel con etapas; a lo sumo una unidad de entrega, un
subnivel y un nivel de detalle; los agrupadores van siempre arriba y el
último de ellos cumple la función de piso (agrupa las unidades).
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .common import LEVEL_ROLES, LEVELS, PURCHASE_DESTINATIONS

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
    purchase_destination = fields.Selection(
        PURCHASE_DESTINATIONS, string='Destino de la compra masiva', default='general',
        required=True,
        help='Valor por defecto de las obras con esta plantilla. Stock general: sin analítica, '
             'descuenta lo libre en el central y el costo cae a la obra al consumir. Directo a '
             'la obra: con la analítica de la obra y sin descontar el central.')

    @api.depends('line_ids.name', 'line_ids.sequence')
    def _compute_summary(self):
        for template in self:
            template.summary = ' › '.join(template.line_ids.sorted('sequence').mapped('name'))

    @api.constrains('line_ids')
    def _check_lines(self):
        for template in self:
            lines = template.line_ids.sorted('sequence')
            roles = lines.mapped('role')
            if roles.count('space') != 1:
                raise ValidationError(self.env._(
                    'La plantilla %(template)s debe tener un solo nivel con la función '
                    '%(role)s.', template=template.name, role=dict(LEVEL_ROLES)['space']))
            for role in ('unit', 'furniture', 'module'):
                if roles.count(role) > 1:
                    raise ValidationError(self.env._(
                        'La plantilla %(template)s tiene más de un nivel con la función '
                        '%(role)s.', template=template.name, role=dict(LEVEL_ROLES)[role]))
            ranks = [ROLE_ORDER[role] for role in roles]
            if ranks != sorted(ranks):
                raise ValidationError(self.env._(
                    'Los niveles de la plantilla %s van en este orden: agrupadores, unidad de '
                    'entrega, nivel con etapas, subnivel y nivel de detalle.', template.name))

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
        help='Agrupador: torre, piso, disciplina, área (sin límite, siempre arriba). Unidad de '
             'entrega: departamento, estacionamiento (opcional). Nivel con etapas: ambiente, '
             'partida, spool; es el que programa el cronograma. Subnivel: mueble (opcional). '
             'Nivel de detalle: módulo, actividad (opcional).')
    level = fields.Selection(
        LEVELS, string='Nivel del planificador', compute='_compute_level',
        help='Función interna: el último agrupador (el que agrupa unidades) hace de piso.')
    # Comportamiento del nivel (v1.7, M17-01). Las etapas y la unidad de
    # entrega son la función; lo demás se marca por rubro.
    has_stages = fields.Boolean(
        string='Lleva etapas', compute='_compute_role_flags',
        help='Sus tareas tienen las etapas del cronograma (el ambiente, la partida, el spool).')
    is_delivery_unit = fields.Boolean(
        string='Unidad de entrega', compute='_compute_role_flags',
        help='Lo que se entrega y se cobra por hitos al cliente (el departamento).')
    has_recipe = fields.Boolean(
        string='Lleva receta', compute='_compute_has_recipe', store=True, readonly=False,
        help='El plan se genera desde la receta del nivel (tipología o plantilla de ejecución).')
    is_measured = fields.Boolean(
        string='Se mide con metrado', compute='_compute_is_measured', store=True,
        readonly=False, help='El supervisor registra su medida real frente a lo planificado.')
    is_billable = fields.Boolean(
        string='Se valoriza o factura', compute='_compute_is_billable', store=True,
        readonly=False, help='Su avance entra en la valorización con el cliente.')
    receives_progress = fields.Boolean(
        string='Recibe avance', compute='_compute_receives_progress', store=True,
        readonly=False,
        help='La contrata o la cuadrilla reportan el avance en este nivel (portal incluido).')
    measure_uom_id = fields.Many2one(
        'uom.uom', string='Unidad del metrado',
        help='m², und, ml, kg… La del nivel que se mide; vacía: la de cada línea.')
    stage_ids = fields.Many2many(
        'construction.stage', 'construction_level_line_stage_rel', 'level_line_id', 'stage_id',
        string='Etapas del nivel',
        help='Las del catálogo que lleva este nivel; vacía: todas las de la obra.')

    @api.depends('role')
    def _compute_role_flags(self):
        for line in self:
            line.has_stages = line.role == 'space'
            line.is_delivery_unit = line.role == 'unit'

    # Valores por defecto de cada función, los de mobiliario: el ambiente lleva
    # la tipología y se mide, la unidad se valoriza y el módulo recibe el
    # avance del armado (la instalación se reporta en el ambiente).
    @api.depends('role')
    def _compute_has_recipe(self):
        for line in self:
            line.has_recipe = line.role == 'space'

    @api.depends('role')
    def _compute_is_measured(self):
        for line in self:
            line.is_measured = line.role == 'space'

    @api.depends('role')
    def _compute_is_billable(self):
        for line in self:
            line.is_billable = line.role == 'unit'

    @api.depends('role')
    def _compute_receives_progress(self):
        for line in self:
            line.receives_progress = line.role in ('space', 'module')

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
