# -*- coding: utf-8 -*-
"""Catálogos de etapas y de tipos de recurso (v1.7, M17-02 y M17-03).

Las etapas y los tipos de recurso se configuran por rubro; el código solo
conoce su comportamiento: el tipo de la etapa (fabricación, campo o
control) y el comportamiento del tipo de recurso (material, contrata…).

Los campos ``stage`` del planificador siguen guardando el código de la etapa
y toman su lista de este catálogo: las etapas de mobiliario son registros con
los códigos de siempre (production, assembly, installation, finishing).
Son catálogos de configuración comunes a todas las compañías, como la
plantilla de niveles.
"""
from odoo import api, fields, models, tools
from odoo.exceptions import UserError, ValidationError

from .common import RESOURCE_TYPES

STAGE_KINDS = [
    ('production', 'Fabricación'),
    ('field', 'Ejecución en campo'),
    ('control', 'Control'),
]

SUPPLY_METHODS = [
    ('purchase', 'Compra'),
    ('stock', 'Almacén'),
    ('production', 'Fabricación'),
    ('contract', 'Contrata'),
    ('crew', 'Cuadrilla propia'),
]


class ConstructionStage(models.Model):
    _name = 'construction.stage'
    _description = 'Etapa de ejecución'
    _order = 'sequence, id'

    name = fields.Char(string='Etapa', required=True, translate=True)
    code = fields.Char(
        string='Código', required=True,
        help='Lo que guardan el plan, el cronograma y los avances. No se cambia una vez usado.')
    sequence = fields.Integer(string='Orden', default=10)
    active = fields.Boolean(default=True)
    kind = fields.Selection(
        STAGE_KINDS, string='Tipo', required=True, default='field',
        help='Fabricación: la etapa se hace en taller y habilita la orden de fabricación. '
             'Ejecución en campo: se asigna a una contrata o a una cuadrilla. Control: '
             'pruebas, protocolos o entregas sin recurso propio.')
    production_consumption = fields.Boolean(
        string='Consume en la orden de fabricación',
        help='Los materiales de esta etapa salen con la orden de fabricación aunque la etapa '
             'se ejecute en campo (armado de mobiliario).')
    previous_stage_id = fields.Many2one(
        'construction.stage', string='Etapa anterior',
        help='La que va antes por defecto en el cronograma: esta empieza cuando termina aquella.')
    duration_days = fields.Integer(
        string='Duración (días hábiles)', default=5,
        help='Duración por defecto al programar la etapa.')
    color = fields.Char(string='Color en el cronograma', default='#3d85c6')
    level_line_ids = fields.Many2many(
        'construction.level.template.line', 'construction_level_line_stage_rel',
        'stage_id', 'level_line_id', string='Niveles',
        help='Niveles de las plantillas de los que cuelga la etapa. Vacío: cualquier nivel '
             'que lleve etapas.')
    note = fields.Text(string='Descripción')

    _code_unique = models.Constraint('UNIQUE(code)', 'Ya hay una etapa con ese código.')

    @api.model
    @tools.ormcache('self.env.lang')
    def _get_selection(self):
        # Con las archivadas: lo ya registrado con ellas se sigue leyendo.
        stages = self.with_context(active_test=False).search([])
        return [(stage.code, stage.name) for stage in stages]

    @api.model
    def _codes(self):
        return [code for code, _label in self._get_selection()]

    @api.model
    def _by_code(self, codes=None):
        domain = [('code', 'in', list(codes))] if codes is not None else []
        return self.with_context(active_test=False).search(domain)

    @api.model
    def _production_codes(self):
        """Etapas cuyos materiales consume la orden de fabricación."""
        return tuple(self.with_context(active_test=False).search([
            '|', ('kind', '=', 'production'), ('production_consumption', '=', True),
        ]).mapped('code'))

    @api.model
    def _consumption_code(self, where):
        """Etapa del consumo sin etapa propia: ``production`` la de la OF (la
        primera de fabricación), ``site`` la del consumo en obra (la primera
        de campo cuyos materiales no salen con la OF)."""
        if where == 'production':
            domain = [('kind', '=', 'production')]
        else:
            domain = [('kind', '=', 'field'), ('production_consumption', '=', False)]
        return self.search(domain, limit=1).code or False

    @api.model
    def _field_codes(self):
        """Etapas que se asignan a una contrata o a una cuadrilla."""
        return tuple(self.search([('kind', '=', 'field')]).mapped('code'))

    @api.model
    def _check_codes(self, records, fname='stage'):
        """La lista de los campos de etapa es dinámica y Odoo no la valida:
        lo hace esta restricción en los modelos que la escriben."""
        codes = set(self._codes())
        wrong = {code for code in records.mapped(fname) if code and code not in codes}
        if wrong:
            raise ValidationError(self.env._(
                'Etapa desconocida: %s. Las etapas salen del catálogo de etapas.',
                ', '.join(sorted(wrong))))

    @api.model_create_multi
    def create(self, vals_list):
        self.env.registry.clear_cache()
        return super().create(vals_list)

    def write(self, vals):
        if 'code' in vals and any(stage.code != vals['code'] for stage in self) \
                and self._is_used():
            raise UserError(self.env._(
                'El código de la etapa ya está en uso: cree otra etapa y archive esta.'))
        if {'code', 'name', 'active', 'sequence'} & set(vals):
            self.env.registry.clear_cache()
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_if_unused(self):
        if self._is_used():
            raise UserError(self.env._(
                'La etapa ya se usa en planes o actividades: archívela en lugar de borrarla.'))

    def unlink(self):
        self.env.registry.clear_cache()
        return super().unlink()

    def _is_used(self):
        codes = self.mapped('code')
        for model in ('construction.resource.plan.line', 'construction.labor.activity',
                      'construction.space.stage'):
            # Solo cuenta: el código se usa en obras de cualquier compañía, aunque
            # quien configura no las vea.
            records_sudo = self.env[model].sudo().with_context(active_test=False)
            if records_sudo.search_count([('stage', 'in', codes)], limit=1):
                return True
        return False


class ConstructionResourceType(models.Model):
    _name = 'construction.resource.type'
    _description = 'Tipo de recurso'
    _order = 'sequence, id'

    name = fields.Char(string='Tipo de recurso', required=True, translate=True)
    code = fields.Char(string='Código', required=True)
    sequence = fields.Integer(string='Orden', default=10)
    active = fields.Boolean(default=True)
    behavior = fields.Selection(
        RESOURCE_TYPES, string='Comportamiento', required=True, default='material',
        help='Lo que hace el planificador con la línea: material y equipo se compran o salen '
             'del almacén, la contrata se asigna y se liquida por avance, el personal propio '
             'se asigna en cuadrillas y la producción sale de una orden de fabricación.')
    supply_method = fields.Selection(
        SUPPLY_METHODS, string='Abastecimiento', required=True, default='purchase')
    is_default = fields.Boolean(
        string='Por defecto del comportamiento',
        help='El que reciben las líneas creadas solo con el comportamiento (asistentes, '
             'importación). Uno por comportamiento.')
    note = fields.Text(string='Descripción')

    _code_unique = models.Constraint('UNIQUE(code)', 'Ya hay un tipo de recurso con ese código.')

    @api.model
    def _default_for(self, behavior):
        types = self.with_context(active_test=False).search([('behavior', '=', behavior)])
        return types.filtered('is_default')[:1] or types[:1]

    @api.constrains('is_default', 'behavior')
    def _check_default(self):
        for behavior in set(self.filtered('is_default').mapped('behavior')):
            if self.search_count([('behavior', '=', behavior), ('is_default', '=', True)]) > 1:
                raise UserError(self.env._(
                    'Solo un tipo de recurso por defecto por comportamiento.'))


class ConstructionResourceTypeMixin(models.AbstractModel):
    """Tipo de recurso del catálogo junto al comportamiento ``resource_type``.

    Elegir el tipo fija el comportamiento; las líneas que se crean solo con
    el comportamiento (asistentes, importación, adicionales) reciben el tipo
    por defecto de ese comportamiento."""
    _name = 'construction.resource.type.mixin'
    _description = 'Tipo de recurso del catálogo'

    resource_type_id = fields.Many2one(
        'construction.resource.type', string='Tipo de recurso', index=True,
        compute='_compute_resource_type_id', store=True, readonly=False,
        help='Del catálogo de tipos de recurso: fija el comportamiento de la línea.')

    @api.depends('resource_type')
    def _compute_resource_type_id(self):
        Type = self.env['construction.resource.type']
        defaults = {}
        for record in self:
            behavior = record.resource_type
            if not behavior or record.resource_type_id.behavior == behavior:
                continue
            if behavior not in defaults:
                defaults[behavior] = Type._default_for(behavior)
            record.resource_type_id = defaults[behavior]

    @api.onchange('resource_type_id')
    def _onchange_resource_type_id(self):
        if self.resource_type_id:
            self.resource_type = self.resource_type_id.behavior

    @api.model
    def _resource_type_behavior_vals(self, vals):
        if vals.get('resource_type_id') and 'resource_type' not in vals:
            vals['resource_type'] = self.env['construction.resource.type'].browse(
                vals['resource_type_id']).behavior
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._resource_type_behavior_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        return super().write(self._resource_type_behavior_vals(dict(vals)))
