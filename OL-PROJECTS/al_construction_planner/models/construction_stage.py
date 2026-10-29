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

Sub etapas (v1.8, M18-02): una etapa puede tener etapa padre («1 Producción ›
1.1 Producción de piezas»). Las líneas, las recetas, los avances y las
etapas del cronograma se asignan siempre a una etapa sin sub etapas (hoja);
la etapa padre suma lo de sus hijas en cada vista y no está en la lista de
los campos ``stage``.
"""
from odoo import api, fields, models, tools
from odoo.exceptions import UserError, ValidationError

from .common import RESOURCE_TYPES, norm

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
    number = fields.Char(
        string='Número', help='Numeración visible del árbol de etapas («1», «1.1»): va delante '
                              'del nombre en todas las vistas y reportes.')
    parent_id = fields.Many2one(
        'construction.stage', string='Etapa padre', index=True, ondelete='restrict',
        help='La etapa que la agrupa. Una etapa con sub etapas solo suma: los recursos se '
             'asignan a sus sub etapas.')
    child_ids = fields.One2many('construction.stage', 'parent_id', string='Sub etapas')
    is_group = fields.Boolean(
        string='Con sub etapas', compute='_compute_is_group', store=True,
        help='Agrupa sub etapas: no lleva recursos propios.')
    alias_names = fields.Char(
        string='Otros nombres',
        help='Separados por comas: los nombres con que la etapa llega en hojas de cálculo e '
             'importaciones («Producción», «Acabado y entrega»).')
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

    @api.depends('child_ids')
    def _compute_is_group(self):
        for stage in self:
            stage.is_group = bool(stage.child_ids)

    @api.depends('number', 'name')
    def _compute_display_name(self):
        for stage in self:
            stage.display_name = stage._label()

    def _label(self):
        self.ensure_one()
        return ' '.join(filter(None, [self.number, self.name]))

    def _tree_key(self):
        """Clave de orden en el árbol: el orden de cada ancestro, de arriba abajo."""
        self.ensure_one()
        key, node, seen = [], self, set()
        while node and node.id not in seen:
            seen.add(node.id)
            key.insert(0, (node.sequence, node.id))
            node = node.parent_id
        return key

    @api.model
    def _tree_sorted(self, stages=None):
        """Etapas (todas, con las archivadas, si no se pasan) en el orden del
        árbol: cada etapa padre seguida de sus sub etapas."""
        if stages is None:
            stages = self.with_context(active_test=False).search([])
        return stages.sorted(lambda stage: stage._tree_key())

    @api.model
    @api.ormcache('self.env.lang')
    def _get_selection(self):
        # Con las archivadas: lo ya registrado con ellas se sigue leyendo. Las
        # etapas padre no llevan recursos: no están en la lista.
        stages = self._tree_sorted().filtered(lambda stage: not stage.is_group)
        return [(stage.code, stage._label()) for stage in stages]

    @api.model
    @api.ormcache('self.env.lang')
    def _get_group_selection(self):
        stages = self._tree_sorted().filtered(lambda stage: not stage.parent_id)
        return [(stage.code, stage._label()) for stage in stages]

    def _root(self):
        """Etapa de primer nivel de la que cuelga (ella misma si no tiene padre)."""
        self.ensure_one()
        node, seen = self, set()
        while node.parent_id and node.id not in seen:
            seen.add(node.id)
            node = node.parent_id
        return node

    @api.model
    def _get_tree(self, active_only=True):
        """Árbol de etapas para filtros y reportes, en su orden: lista de
        ``{code, label, number, name, parent, depth, leaf, leaves}`` donde
        ``leaves`` son los códigos de las hojas que cubre la etapa."""
        stages = self._tree_sorted(self.search([]) if active_only else None)
        result = []
        for stage in stages:
            depth = len(stage._tree_key()) - 1
            result.append({
                'code': stage.code, 'label': stage._label(), 'number': stage.number or '',
                'name': stage.name, 'parent': stage.parent_id.code or False, 'depth': depth,
                'leaf': not stage.is_group,
                'leaves': stage._leaf_stages().mapped('code'),
            })
        return result

    def _leaf_stages(self):
        """Hojas que cubren estas etapas (ellas mismas si no tienen sub etapas)."""
        leaves = self.browse()
        for stage in self:
            leaves |= stage._leaf_stages_of(stage)
        return leaves

    @api.model
    def _leaf_stages_of(self, stage):
        children = stage.with_context(active_test=False).child_ids
        if not children:
            return stage
        leaves = self.browse()
        for child in children:
            leaves |= self._leaf_stages_of(child)
        return leaves

    @api.model
    def _leaf_codes(self, codes):
        """Códigos hoja de una lista de códigos que puede traer etapas padre
        (filtros del árbol y del cronograma)."""
        codes = [code for code in (codes or []) if code]
        if not codes:
            return []
        stages = self._by_code(codes)
        groups = stages.filtered('is_group')
        leaves = set(codes) - set(groups.mapped('code'))
        leaves |= set(groups._leaf_stages().mapped('code'))
        order = self._codes()
        return sorted(leaves, key=lambda code: order.index(code) if code in order else len(order))

    @api.model
    def _find_by_text(self, text):
        """Código de la etapa hoja que nombra ``text`` en una importación: su
        código, su nombre, su número y nombre, su número o uno de sus otros
        nombres. Los otros nombres pesan más que el nombre de una etapa padre
        («Producción» es la producción de piezas en las hojas de mobiliario).
        Devuelve ``None`` si no hay ninguna."""
        key = norm(text)
        if not key:
            return None
        stages = self._tree_sorted()
        leaves = stages.filtered(lambda stage: not stage.is_group)
        for stage in leaves:
            if key in (norm(stage.code), norm(stage.name), norm(stage._label()),
                       norm(stage.number) if stage.number else None):
                return stage.code
        for stage in leaves:
            if key in {norm(alias) for alias in (stage.alias_names or '').split(',') if alias.strip()}:
                return stage.code
        for stage in stages.filtered('is_group'):
            if key in (norm(stage.code), norm(stage.name), norm(stage._label())):
                leaves = stage._leaf_stages()
                return leaves[:1].code if len(leaves) == 1 else None
        return None

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
            ('is_group', '=', False),
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
        stages = self._tree_sorted(self.search(domain + [('is_group', '=', False)]))
        return stages[:1].code or False

    @api.model
    def _field_codes(self):
        """Etapas que se asignan a una contrata o a una cuadrilla."""
        return tuple(self._tree_sorted(self.search(
            [('kind', '=', 'field'), ('is_group', '=', False)])).mapped('code'))

    @api.model
    def _check_codes(self, records, fname='stage'):
        """La lista de los campos de etapa es dinámica y Odoo no la valida:
        lo hace esta restricción en los modelos que la escriben."""
        codes = set(self._codes())
        wrong = {code for code in records.mapped(fname) if code and code not in codes}
        groups = self._by_code(wrong).filtered('is_group')
        if groups:
            raise ValidationError(self.env._(
                'La etapa %s tiene sub etapas: los recursos se asignan a una de ellas.',
                ', '.join(groups.mapped(lambda stage: stage._label()))))
        if wrong:
            raise ValidationError(self.env._(
                'Etapa desconocida: %s. Las etapas salen del catálogo de etapas.',
                ', '.join(sorted(wrong))))

    @api.constrains('parent_id')
    def _check_parent(self):
        if self._has_cycle():
            raise ValidationError(self.env._('Una etapa no puede ser sub etapa de sí misma.'))
        parents = self.parent_id
        used = parents.filtered(lambda stage: stage._is_used())
        if used:
            raise ValidationError(self.env._(
                'La etapa %s ya tiene recursos, actividades o etapas del cronograma: no puede '
                'tener sub etapas. Cree una etapa padre nueva y ponga esta debajo.',
                ', '.join(used.mapped(lambda stage: stage._label()))))

    @api.model_create_multi
    def create(self, vals_list):
        self.env.transaction.invalidate_ormcache()
        return super().create(vals_list)

    def write(self, vals):
        if 'code' in vals and any(stage.code != vals['code'] for stage in self) \
                and self._is_used():
            raise UserError(self.env._(
                'El código de la etapa ya está en uso: cree otra etapa y archive esta.'))
        if {'code', 'name', 'active', 'sequence', 'number', 'parent_id'} & set(vals):
            self.env.transaction.invalidate_ormcache()
        res = super().write(vals)
        if 'parent_id' in vals:
            self._recompute_stage_parent()
        return res

    def _recompute_stage_parent(self):
        """La etapa padre guardada en las líneas del plan sigue al catálogo."""
        Line = self.env['construction.resource.plan.line'].sudo()
        lines = Line.search([('stage', 'in', self._leaf_stages().mapped('code'))])
        if lines:
            self.env.add_to_compute(Line._fields['stage_parent'], lines)
            lines.flush_recordset(['stage_parent'])

    @api.ondelete(at_uninstall=False)
    def _unlink_if_unused(self):
        if self._is_used():
            raise UserError(self.env._(
                'La etapa ya se usa en planes o actividades: archívela en lugar de borrarla.'))

    def unlink(self):
        self.env.transaction.invalidate_ormcache()
        return super().unlink()

    def _is_used(self):
        codes = self.mapped('code')
        for model in ('construction.resource.plan.line', 'construction.labor.activity',
                      'construction.space.stage', 'construction.execution.template.line'):
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
