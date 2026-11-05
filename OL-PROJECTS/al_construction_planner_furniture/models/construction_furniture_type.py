# -*- coding: utf-8 -*-
"""Catálogo de tipos de mueble y de módulo (paquete 1.17, M117-24).

Oficina Técnica agrega un tipo sin programar. Como en las etapas, el dato guardado
en reglas, actividades y tareas sigue siendo el código: el catálogo dice qué códigos
existen y cómo se comportan.
"""
from odoo import api, fields, models

from odoo.addons.al_construction_planner.models.common import norm

LEGACY_VALUES = {'mueble bajo': 'low', 'mueble alto': 'high'}


def special_kind_selection(model):
    """Códigos de los tipos de módulo especiales del catálogo."""
    return model.env['construction.furniture.type']._selection('module', special=True)


def furniture_kind_selection(model):
    return model.env['construction.furniture.type']._selection('furniture')


class ConstructionFurnitureType(models.Model):
    _name = 'construction.furniture.type'
    _description = 'Tipo de mueble o de módulo'
    _order = 'level, sequence, id'

    name = fields.Char(string='Nombre', required=True, translate=True)
    code = fields.Char(string='Código', required=True, copy=False,
                       default=lambda self: self.env['ir.sequence'].next_by_code(
                           'construction.furniture.type') or 'tipo',
                       help='El que guardan reglas, actividades y tareas.')
    sequence = fields.Integer(string='Secuencia', default=100)
    level = fields.Selection([('furniture', 'Mueble'), ('module', 'Módulo')], string='Nivel',
                             required=True, default='module')
    ml_group = fields.Selection(
        [('low', 'Mueble bajo'), ('high', 'Mueble alto'), ('full', 'Mueble completo'),
         ('none', 'Sin ML')], string='Grupo de ML sugerido',
        help='Se propone al elegir el tipo y se puede cambiar en cada módulo.')
    module_class = fields.Selection(
        [('standard', 'Estándar'), ('special', 'Especial')], string='Clase', default='standard',
        help='Solo módulos.')
    keywords = fields.Char(string='Palabras que lo delatan',
                           help='En el nombre del módulo, separadas por punto y coma.')
    activity_id = fields.Many2one('construction.labor.activity',
                                  string='Actividad de armado por defecto',
                                  help='Para los especiales.')
    not_counted = fields.Boolean(string='No cuenta como módulo a armar')
    active = fields.Boolean(string='Activo', default=True)

    _code_unique = models.Constraint('unique(level, code)',
                                     'Ya hay un tipo con ese código en ese nivel.')

    @api.model
    def _selection(self, level, special=False):
        """[(código, nombre)], también los inactivos: conservan sus módulos."""
        domain = [('level', '=', level)]
        if special:
            domain.append(('module_class', '=', 'special'))
        return [(kind.code, kind.name)
                for kind in self.sudo().with_context(active_test=False).search(domain)]

    @api.model
    def _by_code(self, level, code):
        if not code:
            return self.browse()
        return self.with_context(active_test=False).search(
            [('level', '=', level), ('code', '=', code)], limit=1)

    @api.model
    def _from_name(self, text):
        """El tipo especial o con palabras que delata el nombre del módulo."""
        key = norm(text or '').upper()
        if not key:
            return self.browse()
        for kind in self.search([('level', '=', 'module'), ('keywords', '!=', False)]):
            words = [norm(word).upper() for word in kind.keywords.split(';') if word.strip()]
            if any(word in key for word in words):
                return kind
        return self.browse()

    @api.model
    def _resolve(self, value, name=False):
        """El tipo de un módulo que llega en un libro: lo que delata su nombre, el
        valor escrito (nombre, código o sus palabras) o, sin nada, vacío."""
        by_name = self._from_name(name)
        if by_name:
            return by_name
        text = norm(value or '')
        if not text:
            return self.browse()
        code = LEGACY_VALUES.get(text)
        for kind in self.search([('level', '=', 'module')]):
            if kind.code == code or norm(kind.name) == text or kind.code == text:
                return kind
        return self._from_name(value)

    @api.model
    def _construction_module_values(self, kind, ml_group=False, explicit_class=False):
        """Lo que el tipo fija en el módulo (conserva lo escrito): clase, especial,
        tipo anterior y grupo ML sugerido."""
        from odoo.addons.al_construction_planner.models.common import MODULE_TYPES
        values = {}
        module_class = explicit_class or kind.module_class or 'standard'
        values['module_class'] = module_class
        values['special_kind'] = kind.code if module_class == 'special' \
            and kind.module_class == 'special' else False
        group = ml_group or kind.ml_group
        if group and not ml_group:
            values['ml_group'] = group
        if kind.code in dict(MODULE_TYPES):
            values['module_type'] = kind.code
        else:
            values['module_type'] = {'low': 'low', 'high': 'high'}.get(group, 'other')
        return values
