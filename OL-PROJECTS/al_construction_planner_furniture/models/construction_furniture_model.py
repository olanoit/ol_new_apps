# -*- coding: utf-8 -*-
"""Modelo del mueble de mobiliario (v1.8, M18-17 a M18-20).

* M18-17: el mueble es su tipo (bajo, alto, torre, isla o el mueble completo
  de closets, baños y lavanderías) y el módulo es estándar o especial
  (microondas, campana, alacena con puertas, torre de horno…).
* M18-18: el método de unión del módulo (tornillo, tarugo, mixto, minifix o
  sin unión) se propone con reglas configurables sobre los insumos de armado
  del despiece (los tornillos de instalación no cuentan) y se puede cambiar.
* M18-19: catálogo de actividades de contrata con su clase, unidad, sub etapa
  y tarifa por lista: una lista por familia (cocina y baño; closet y cajones)
  que se versiona por obra. El módulo estándar toma la actividad de armado de
  su método; el especial, la de su tipo.
* M18-20: las líneas de contrata de cada módulo salen de su receta: el
  armado, la colocación de puertas por el ancho de las piezas PUERTA, los
  cajones, tapas y correderas por las piezas FRENTE y TAPA, y la instalación
  por los ML de mueble bajo y alto.
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain

from odoo.addons.al_construction_planner.models.common import norm, stage_selection

FURNITURE_KINDS = [
    ('low', 'Mueble bajo'),
    ('high', 'Mueble alto'),
    ('tower', 'Torre'),
    ('island', 'Isla'),
    ('block', 'Mueble completo'),
]
MODULE_CLASSES = [
    ('standard', 'Estándar'),
    ('special', 'Especial'),
]
SPECIAL_KINDS = [
    ('microwave', 'Microondas'),
    ('hood', 'Campana'),
    ('cupboard', 'Alacena con puertas'),
    ('shelf', 'Repisero'),
    ('oven_tower', 'Torre de horno'),
    ('fridge', 'Refrigeradora'),
    ('corner', 'Esquinero'),
    ('drawer', 'Cajonera'),
    ('spice', 'Condimentero'),
    ('bottle', 'Botellero'),
    ('plinth', 'Zócalo'),
]
#: Palabras del nombre del módulo que delatan su tipo especial.
SPECIAL_KEYWORDS = [
    ('microwave', ('MICROONDAS', 'MICRO ONDAS')),
    ('hood', ('CAMPANA',)),
    ('oven_tower', ('TORRE DE HORNO', 'TORRE HORNO', 'HORNO')),
    ('fridge', ('REFRIGERADORA', 'REFRI')),
    ('corner', ('ESQUINERO', 'ESQUINA')),
    ('drawer', ('CAJONERA',)),
    ('spice', ('CONDIMENTERO',)),
    ('bottle', ('BOTELLERO',)),
    ('plinth', ('ZOCALO',)),
    ('shelf', ('REPISERO',)),
    ('cupboard', ('ALACENA',)),
]
JOIN_METHODS = [
    ('screw', 'Tornillo'),
    ('dowel', 'Tarugo'),
    ('mixed', 'Mixto'),
    ('minifix', 'Minifix'),
    ('none', 'Sin unión'),
]
ACTIVITY_CLASSES = [
    ('assembly_method', 'Armado del casco según el método'),
    ('onsite_assembly', 'Armado en obra'),
    ('assembly_special', 'Armado de módulo especial'),
    ('complementary', 'Complementaria'),
    ('installation', 'Instalación'),
    ('other', 'Otra'),
]
PIECE_MEASURES = [
    ('count', 'Una por pieza'),
    ('width_ml', 'Ancho de las piezas en ML'),
    ('length_ml', 'Largo de las piezas en ML'),
]
RATE_FAMILIES = [
    ('kitchen_bath', 'Cocina y baño'),
    ('closet_drawer', 'Closet y cajones'),
]


def special_kind_from_name(name):
    """Tipo especial que delata el nombre del módulo (o False)."""
    key = norm(name).upper()
    for kind, words in SPECIAL_KEYWORDS:
        if any(norm(word).upper() in key for word in words):
            return kind
    return False


def rate_family_for(typology_family):
    """Lista de tarifas de una familia de tipología: closet y cajones aparte."""
    return 'closet_drawer' if typology_family in ('closet',) else 'kitchen_bath'


class ConstructionTypologyFurniture(models.Model):
    _inherit = 'construction.typology.furniture'

    furniture_kind = fields.Selection(
        FURNITURE_KINDS, string='Tipo de mueble', compute='_compute_furniture_kind', store=True,
        readonly=False,
        help='Bajo, alto, torre o isla en cocinas; en closet, baño, lavandería, ducto y '
             'estacionamiento el bloque del despiece es el mueble completo.')

    @api.depends('ml_group', 'typology_id.family')
    def _compute_furniture_kind(self):
        for furniture in self:
            if furniture.furniture_kind:
                continue
            if furniture.typology_id.family not in ('kitchen', False):
                furniture.furniture_kind = 'block'
            else:
                furniture.furniture_kind = {'low': 'low', 'high': 'high'}.get(
                    furniture.ml_group, 'low')


class ConstructionTypologyModule(models.Model):
    _inherit = 'construction.typology.module'

    name = fields.Char(
        string='Nombre del módulo',
        help='Su función y su ancho en mm (MOD LAVADERO 900, MOD ALTO CAMPANA 610).')
    module_class = fields.Selection(
        MODULE_CLASSES, string='Tipo de módulo', compute='_compute_module_class', store=True,
        readonly=False, help='Estándar o especial (microondas, campana, torre de horno…).')
    special_kind = fields.Selection(
        SPECIAL_KINDS, string='Módulo especial', compute='_compute_module_class', store=True,
        readonly=False)
    join_method = fields.Selection(
        JOIN_METHODS, string='Método de unión', compute='_compute_join_method', store=True,
        readonly=False,
        help='Propuesto por las reglas sobre los insumos de armado; se puede cambiar.')
    join_warning = fields.Char(string='Aviso del método', compute='_compute_join_method',
                               store=True)
    join_method_manual = fields.Boolean(
        string='Método escrito a mano', copy=False,
        help='El método se escribió (a mano o en la hoja): las reglas ya no lo cambian.')
    piece_ids = fields.One2many('construction.typology.piece', 'module_id', string='Piezas',
                                copy=True)
    material_ids = fields.One2many('construction.typology.module.material', 'module_id',
                                   string='Materiales', copy=True)
    # La actividad de armado ya no es obligatoria: sin ella sale del catálogo
    # por el método o el tipo especial (M18-19).
    assembly_activity_id = fields.Many2one(required=False)
    effective_assembly_activity_id = fields.Many2one(
        'construction.labor.activity', string='Actividad de armado del catálogo',
        compute='_compute_effective_assembly_activity_id',
        help='La escrita o, sin ella, la del catálogo según el método o el tipo especial.')

    @api.depends('name', 'code')
    def _compute_module_class(self):
        for module in self:
            if module.module_class:
                continue
            kind = special_kind_from_name(module.name or module.code)
            module.special_kind = kind
            module.module_class = 'special' if kind else 'standard'

    @api.depends('material_ids.product_id', 'material_ids.qty', 'material_ids.stage',
                 'special_kind')
    def _compute_join_method(self):
        Rule = self.env['construction.join.rule']
        for module in self:
            if module.join_method_manual:
                module.join_method = module.join_method
                module.join_warning = False
                continue
            if not module.material_ids and not module.special_kind:
                # Sin receta no hay qué contar: se conserva el escrito.
                module.join_method = module.join_method
                module.join_warning = False
                continue
            method, warning = Rule._propose(module._join_counts(), module.special_kind,
                                            module.company_id or self.env.company)
            module.join_method = method or module.join_method
            module.join_warning = warning or False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('join_method'):
                vals.setdefault('join_method_manual', True)
        return super().create(vals_list)

    def write(self, vals):
        if 'join_method' in vals and 'join_method_manual' not in vals:
            vals = dict(vals, join_method_manual=bool(vals['join_method']))
        return super().write(vals)

    def _join_counts(self):
        """(tornillos, tarugos) de armado del módulo: los de las etapas de
        armado (no los de instalación)."""
        self.ensure_one()
        company = self.company_id or self.env.company
        screws = company.construction_join_screw_product_ids
        dowels = company.construction_join_dowel_product_ids
        installation = set(self.env['construction.stage'].search([
            ('kind', '=', 'field'), ('production_consumption', '=', False)]).mapped('code'))
        n_screws = n_dowels = 0.0
        for material in self.material_ids:
            if material.stage in installation:
                continue
            if material.product_id in screws:
                n_screws += material.qty
            elif material.product_id in dowels:
                n_dowels += material.qty
        return n_screws, n_dowels

    @api.depends('assembly_activity_id', 'join_method', 'special_kind', 'module_class')
    def _compute_effective_assembly_activity_id(self):
        for module in self:
            module.effective_assembly_activity_id = module.assembly_activity_id \
                or module._catalog_assembly_activity()

    def _catalog_assembly_activity(self):
        """Actividad de armado del catálogo de la compañía (o compartida)."""
        self.ensure_one()
        Activity = self.env['construction.labor.activity']
        company = self.company_id or self.env.company
        base = [('company_id', 'in', (company.id, False))]
        if self.module_class == 'special' and self.special_kind:
            domain = base + [('activity_class', '=', 'assembly_special'),
                             ('special_kind', '=', self.special_kind)]
        elif self.join_method and self.join_method != 'none':
            domain = base + [('activity_class', 'in', ('assembly_method', 'onsite_assembly')),
                             ('join_method', '=', self.join_method)]
        else:
            return Activity
        return Activity.search(domain, order='company_id, sequence, id', limit=1)

    def _piece_quantity(self, activity):
        """Cantidad de una actividad complementaria desde las piezas del
        módulo (M18-20)."""
        self.ensure_one()
        types = [norm(t).upper() for t in (activity.piece_types or '').split(',') if t.strip()]
        qty = 0.0
        for piece in self.piece_ids:
            if norm(piece.piece_type).upper() not in types:
                continue
            if activity.piece_measure == 'width_ml':
                qty += piece.qty * (piece.width_mm or 0) / 1000.0
            elif activity.piece_measure == 'length_ml':
                qty += piece.qty * (piece.length_mm or 0) / 1000.0
            else:
                qty += piece.qty
        return round(qty, 4)


class ConstructionTypologyPiece(models.Model):
    """Pieza del despiece de un módulo (hoja PIEZAS)."""
    _name = 'construction.typology.piece'
    _description = 'Pieza del módulo'
    _order = 'module_id, sequence, id'

    module_id = fields.Many2one('construction.typology.module', string='Módulo', required=True,
                                ondelete='cascade', index=True)
    company_id = fields.Many2one(related='module_id.company_id', store=True, index=True)
    sequence = fields.Integer(default=10)
    qty = fields.Float(string='Cantidad', digits=(16, 2), default=1.0)
    length_mm = fields.Float(string='Largo (mm)', digits=(16, 1))
    width_mm = fields.Float(string='Ancho (mm)', digits=(16, 1))
    piece_type = fields.Char(string='Tipo de pieza', help='COSTADO, BASE, PUERTA, FRENTE, TAPA…')
    color = fields.Char(string='Color o descripción')
    product_id = fields.Many2one('product.product', string='Tablero')
    edges = fields.Char(string='Cantos')
    area_m2 = fields.Float(string='m²', compute='_compute_area_m2', digits=(16, 4))

    @api.depends('qty', 'length_mm', 'width_mm')
    def _compute_area_m2(self):
        for piece in self:
            piece.area_m2 = piece.qty * (piece.length_mm or 0) * (piece.width_mm or 0) / 1e6


class ConstructionTypologyModuleMaterial(models.Model):
    """Material de la receta del módulo con su sub etapa de consumo."""
    _name = 'construction.typology.module.material'
    _description = 'Material del módulo'
    _order = 'module_id, sequence, id'

    module_id = fields.Many2one('construction.typology.module', string='Módulo', required=True,
                                ondelete='cascade', index=True)
    company_id = fields.Many2one(related='module_id.company_id', store=True, index=True)
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    qty = fields.Float(string='Cantidad', digits=(16, 6), required=True)
    uom_id = fields.Many2one('uom.uom', string='Unidad', compute='_compute_uom_id', store=True,
                             readonly=False)
    stage = fields.Selection(stage_selection, string='Sub etapa')
    source_code = fields.Char(string='Código en la hoja')

    @api.depends('product_id')
    def _compute_uom_id(self):
        for material in self:
            material.uom_id = material.uom_id or material.product_id.uom_id

    @api.constrains('stage')
    def _check_stage_code(self):
        self.env['construction.stage']._check_codes(self)


class ConstructionJoinRule(models.Model):
    """Regla para proponer el método de unión de un módulo (M18-18): rangos
    de tornillos y tarugos de armado, o un tipo de módulo especial."""
    _name = 'construction.join.rule'
    _description = 'Regla del método de unión'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Regla', required=True)
    active = fields.Boolean(default=True)
    method = fields.Selection(JOIN_METHODS, string='Método', required=True)
    special_kind = fields.Selection(
        SPECIAL_KINDS, string='Módulo especial',
        help='Si se indica, la regla vale para ese tipo de módulo sin mirar los insumos '
             '(el zócalo va sin unión).')
    screws_min = fields.Float(string='Tornillos desde')
    screws_max = fields.Float(string='Tornillos hasta')
    dowels_min = fields.Float(string='Tarugos desde')
    dowels_max = fields.Float(string='Tarugos hasta')

    @api.model
    def _propose(self, counts, special_kind=False, company=None):
        """(método, aviso) para (tornillos, tarugos) de armado."""
        screws, dowels = counts
        for rule in self.search([]):
            if rule.special_kind:
                if rule.special_kind == special_kind:
                    return rule.method, False
                continue
            if rule.screws_min <= screws <= rule.screws_max \
                    and rule.dowels_min <= dowels <= rule.dowels_max:
                return rule.method, False
        return False, self.env._(
            'La receta (%(screws)s tornillos y %(dowels)s tarugos de armado) no calza en ninguna '
            'regla del método de unión.', screws=round(screws, 2), dowels=round(dowels, 2))


class ConstructionLaborActivity(models.Model):
    _inherit = 'construction.labor.activity'

    activity_class = fields.Selection(ACTIVITY_CLASSES, string='Clase de actividad')
    join_method = fields.Selection(JOIN_METHODS, string='Método de unión',
                                   help='Armado del casco: el método que paga.')
    special_kind = fields.Selection(SPECIAL_KINDS, string='Módulo especial',
                                    help='Armado de módulo especial: el tipo que paga.')
    piece_types = fields.Char(
        string='Piezas que la generan',
        help='Tipos de pieza separados por comas (PUERTA; FRENTE; TAPA): la cantidad de la '
             'actividad sale de las piezas del módulo.')
    piece_measure = fields.Selection(PIECE_MEASURES, string='Medida de las piezas',
                                     default='count')
    rate_line_ids = fields.One2many('construction.rate.list.line', 'activity_id',
                                    string='Tarifas por lista')

    def _get_rate(self, project=None, partner=None, date=None):
        price, retention, rate = super()._get_rate(project, partner, date)
        if rate:
            return price, retention, rate
        family = self.env.context.get('construction_rate_family')
        line = self.env['construction.rate.list']._line_for(self, project, family, date)
        if line:
            return line.price, line.retention_pct, rate
        return price, retention, rate


class ConstructionRateList(models.Model):
    """Lista de tarifas de contrata por familia (M18-19): cocina y baño;
    closet y cajones. Una lista general y, como se pactan por obra, versiones
    por obra con vigencia."""
    _name = 'construction.rate.list'
    _description = 'Lista de tarifas de contrata'
    _order = 'project_id, family, date_from desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Lista', required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Compañía', index=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', compute='_compute_currency_id')
    family = fields.Selection(RATE_FAMILIES, string='Familia', required=True,
                              default='kitchen_bath')
    project_id = fields.Many2one('project.project', string='Obra', index=True,
                                 check_company=True, help='Vacía: la lista general.')
    date_from = fields.Date(string='Vigente desde')
    date_to = fields.Date(string='Vigente hasta')
    line_ids = fields.One2many('construction.rate.list.line', 'list_id', string='Tarifas',
                               copy=True)
    note = fields.Text(string='Notas')

    @api.depends('company_id')
    def _compute_currency_id(self):
        for rate_list in self:
            rate_list.currency_id = (rate_list.company_id or self.env.company).currency_id

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rate_list in self:
            if rate_list.date_from and rate_list.date_to \
                    and rate_list.date_from > rate_list.date_to:
                raise ValidationError(self.env._('La lista %s termina antes de empezar.',
                                                 rate_list.name))

    @api.model
    def _line_for(self, activity, project=None, family=None, date=None):
        """Tarifa de la actividad: la lista de la obra vigente a la fecha y,
        si no, la general de su familia."""
        date = date or fields.Date.context_today(self)
        company = (project and project.company_id) or self.env.company
        domain = Domain.AND([
            [('list_id.active', '=', True), ('activity_id', '=', activity.id)],
            [('list_id.company_id', 'in', (company.id, False))],
            ['|', ('list_id.date_from', '=', False), ('list_id.date_from', '<=', date)],
            ['|', ('list_id.date_to', '=', False), ('list_id.date_to', '>=', date)],
        ])
        if family:
            domain = Domain.AND([domain, [('list_id.family', '=', family)]])
        lines = self.env['construction.rate.list.line'].search(domain)
        for match in (lambda l: project and l.list_id.project_id == project,
                      lambda l: not l.list_id.project_id):
            found = lines.filtered(match).sorted(
                lambda l: l.list_id.date_from or fields.Date.to_date('1900-01-01'),
                reverse=True)[:1]
            if found:
                return found
        return self.env['construction.rate.list.line']

    def action_copy_for_project(self):
        """Versión de la lista para una obra (se pacta por obra)."""
        self.ensure_one()
        project_id = self.env.context.get('construction_project_id')
        copy = self.copy({'name': '%s (copia)' % self.name, 'project_id': project_id or False,
                          'date_from': fields.Date.context_today(self)})
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': copy.id,
                'view_mode': 'form'}


class ConstructionRateListLine(models.Model):
    _name = 'construction.rate.list.line'
    _description = 'Tarifa de la lista'
    _order = 'list_id, activity_id'

    list_id = fields.Many2one('construction.rate.list', string='Lista', required=True,
                              ondelete='cascade', index=True)
    company_id = fields.Many2one(related='list_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='list_id.currency_id', string='Moneda')
    activity_id = fields.Many2one('construction.labor.activity', string='Actividad',
                                  required=True, index=True)
    uom_id = fields.Many2one(related='activity_id.uom_id', string='Unidad')
    price = fields.Monetary(string='Tarifa', currency_field='currency_id')
    retention_pct = fields.Float(string='Retención (%)', digits=(5, 2))

    _activity_unique = models.Constraint('UNIQUE(list_id, activity_id)',
                                         'La actividad va una sola vez en la lista.')


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_join_screw_product_ids = fields.Many2many(
        'product.product', 'res_company_construction_join_screw_rel', 'company_id', 'product_id',
        string='Tornillos de armado',
        help='Los que cuentan para el método de unión (4x50 de armado; no los 5x60 de '
             'instalación).')
    construction_join_dowel_product_ids = fields.Many2many(
        'product.product', 'res_company_construction_join_dowel_rel', 'company_id', 'product_id',
        string='Tarugos')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_join_screw_product_ids = fields.Many2many(
        related='company_id.construction_join_screw_product_ids', readonly=False)
    construction_join_dowel_product_ids = fields.Many2many(
        related='company_id.construction_join_dowel_product_ids', readonly=False)


class ProjectTask(models.Model):
    _inherit = 'project.task'

    construction_furniture_kind = fields.Selection(FURNITURE_KINDS, string='Tipo de mueble')
    construction_module_class = fields.Selection(MODULE_CLASSES, string='Clase de módulo')
    construction_special_kind = fields.Selection(SPECIAL_KINDS, string='Módulo especial')
    construction_join_method = fields.Selection(JOIN_METHODS, string='Método de unión')
