# -*- coding: utf-8 -*-
"""Tipología de mueble (rubro mobiliario, v1.7 M17-04): familia, módulos con
ancho y grupo ML, muebles, metros lineales y lista de materiales."""
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.al_construction_planner.models.common import (
    FURNITURE_GROUPS, ML_GROUPS, MODULE_TYPES, TYPOLOGY_FAMILIES,
)


class ConstructionTypology(models.Model):
    _inherit = 'construction.typology'
    _order = 'project_id, family, code'

    family = fields.Selection(
        TYPOLOGY_FAMILIES, string='Familia', required=True, default='kitchen', tracking=True)
    furniture_line_ids = fields.One2many(
        'construction.typology.furniture', 'typology_id', string='Muebles', copy=True,
        help='Muebles del ambiente (bajo, alto, torre de horno…) con sus metros lineales: con '
             'el nivel Mueble en la plantilla de la obra, la instalación, las puertas y la '
             'limpieza por ML cuelgan de cada mueble.')
    bom_id = fields.Many2one(
        'mrp.bom', string='Lista de materiales', check_company=True,
        domain="[('product_tmpl_id', '=', product_tmpl_id)]",
        help='Lista de materiales de un ambiente de esta tipología: de ella salen las '
             'líneas de material del plan y los componentes de la OF.')
    module_line_ids = fields.One2many(
        'construction.typology.module', 'typology_id', string='Módulos', copy=True)
    module_count = fields.Integer(
        string='Nº de módulos', compute='_compute_module_count', store=True)
    ml_low = fields.Float(
        string='ML bajo', digits=(16, 2), compute='_compute_module_stats', store=True,
        readonly=False,
        help='Metros lineales de mueble bajo. Se calculan del ancho de los módulos; '
             'sin anchos (p. ej. sin ETO) se escriben a mano.')
    ml_high = fields.Float(
        string='ML alto', digits=(16, 2), compute='_compute_module_stats', store=True,
        readonly=False, help='Metros lineales de mueble alto (ver «ML bajo»).')
    module_assembly_amount = fields.Monetary(
        string='Armado por módulo', compute='_compute_module_assembly_amount',
        currency_field='currency_id',
        help='Armado de los módulos a la tarifa vigente de la obra (referencia).')

    _code_unique = models.Constraint(
        'UNIQUE(project_id, family, code)',
        'El código de la tipología debe ser único por obra y familia.')

    @api.depends('module_line_ids')
    def _compute_module_count(self):
        for typology in self:
            typology.module_count = len(typology.module_line_ids)

    @api.depends('module_line_ids', 'module_line_ids.width_mm', 'module_line_ids.ml_group')
    def _compute_module_stats(self):
        for typology in self:
            modules = typology.module_line_ids
            if any(modules.mapped('width_mm')):
                typology.ml_low = sum(m.width_mm for m in modules if m.ml_group == 'low') / 1000.0
                typology.ml_high = sum(m.width_mm for m in modules if m.ml_group == 'high') / 1000.0
            else:
                # Sin anchos (p. ej. sin ETO) se conservan los escritos a mano.
                typology.ml_low = typology.ml_low
                typology.ml_high = typology.ml_high

    @api.depends('module_line_ids.assembly_activity_id')
    def _compute_module_assembly_amount(self):
        for typology in self:
            project = typology.project_id
            typology.module_assembly_amount = sum(
                line.assembly_activity_id._get_rate(project)[0]
                for line in typology.module_line_ids if line.assembly_activity_id)


class ConstructionTypologyModule(models.Model):
    """Módulo de la plantilla de una tipología (MB01, MA01, CAMPANA…)."""
    _name = 'construction.typology.module'
    _description = 'Módulo de la tipología'
    _order = 'typology_id, sequence, id'
    _check_company_auto = True

    typology_id = fields.Many2one(
        'construction.typology', string='Tipología', required=True, ondelete='cascade',
        index=True, check_company=True)
    company_id = fields.Many2one(
        related='typology_id.company_id', string='Compañía', store=True, index=True)
    sequence = fields.Integer(string='Orden', default=10)
    code = fields.Char(
        string='Código del módulo', required=True,
        help='Del ETO (MB01, MA01, CAMPANA). Sin ETO, generado por tipo («Tarugo 2»).')
    module_type = fields.Selection(MODULE_TYPES, string='Tipo', required=True, default='low')
    width_mm = fields.Integer(
        string='Ancho (mm)', help='Con ancho, las actividades por ML cuelgan del módulo.')
    ml_group = fields.Selection(ML_GROUPS, string='Grupo ML', default='none')
    furniture_id = fields.Many2one(
        'construction.typology.furniture', string='Mueble', check_company=True,
        domain="[('typology_id', '=', typology_id)]",
        help='Mueble del ambiente al que pertenece el módulo (con el nivel Mueble en la '
             'plantilla de la obra).')
    assembly_activity_id = fields.Many2one(
        'construction.labor.activity', string='Actividad de armado', required=True,
        check_company=True, domain=[('module_level', '=', True)])
    bom_id = fields.Many2one(
        'mrp.bom', string='BOM del módulo', check_company=True,
        help='Opcional. Si existe, los materiales del plan cuelgan del módulo.')

    @api.constrains('width_mm')
    def _check_width(self):
        if any(module.width_mm < 0 for module in self):
            raise ValidationError(self.env._('El ancho del módulo no puede ser negativo.'))


class ConstructionTypologyFurniture(models.Model):
    """Mueble de una tipología: bajo, alto, torre de horno… (v1.5, M15-03)."""
    _name = 'construction.typology.furniture'
    _description = 'Mueble de la tipología'
    _order = 'typology_id, sequence, id'
    _check_company_auto = True

    typology_id = fields.Many2one(
        'construction.typology', string='Tipología', required=True, ondelete='cascade',
        index=True, check_company=True)
    company_id = fields.Many2one(related='typology_id.company_id', store=True, index=True)
    sequence = fields.Integer(string='Orden', default=10)
    name = fields.Char(string='Mueble', required=True, help='Mueble bajo, mueble alto, torre de horno…')
    ml_group = fields.Selection(
        FURNITURE_GROUPS, string='Grupo', required=True, default='low',
        help='Bajo y alto reciben las actividades por ML de su grupo (instalación, limpieza).')
    ml = fields.Float(
        string='Metros lineales', digits=(16, 2), compute='_compute_ml', store=True,
        readonly=False,
        help='Suma del ancho de sus módulos; sin anchos, se escribe a mano.')
    module_ids = fields.One2many('construction.typology.module', 'furniture_id', string='Módulos')

    @api.depends('module_ids.width_mm')
    def _compute_ml(self):
        for furniture in self:
            widths = sum(furniture.module_ids.mapped('width_mm'))
            if widths:
                furniture.ml = round(widths / 1000.0, 2)
            elif not furniture.ml:
                furniture.ml = 0.0
