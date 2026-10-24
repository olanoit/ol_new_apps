# -*- coding: utf-8 -*-
"""Plantilla de ejecución: la receta de un nivel por unidad (v1.7, M17-04).

Es el APU de una partida (muro drywall RF por m²: placas, perfiles, masilla,
horas de operario y de oficial, andamio) o la receta de un spool: líneas de
recurso con su cantidad por unidad del nivel, rendimiento, cuadrilla y etapa.
«Generar plan desde la receta» multiplica cada línea por el metrado
planificado de la tarea. La tipología de mueble es la receta del rubro
mobiliario y sigue con su propio asistente.

La receta se escribe aquí, se importa desde Excel o se copia desde los Work
Items del paquete Construction de Odoo (copia en un solo sentido, que se
puede repetir).
"""
from odoo import api, fields, models

from .common import RESOURCE_TYPES, stage_selection

RECIPE_SOURCES = [
    ('manual', 'Escrita en el planificador'),
    ('excel', 'Importada desde Excel'),
    ('work_item', 'Copiada de un Work Item'),
]


class ConstructionExecutionTemplate(models.Model):
    _name = 'construction.execution.template'
    _description = 'Plantilla de ejecución (receta del nivel)'
    _inherit = ['mail.thread']
    _order = 'code, name, id'
    _check_company_auto = True
    _rec_names_search = ['code', 'name']

    code = fields.Char(string='Código', required=True, tracking=True,
                       help='El de la partida (ARQ-03.02.01) o del spool.')
    name = fields.Char(string='Nombre', required=True, translate=True, tracking=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    project_id = fields.Many2one(
        'project.project', string='Obra', index=True, check_company=True,
        domain="[('is_construction_site', '=', True)]",
        help='Vacía: la receta sirve para cualquier obra de la compañía.')
    uom_id = fields.Many2one(
        'uom.uom', string='Unidad del nivel', required=True,
        default=lambda self: self.env.ref('uom.product_uom_unit'),
        help='Driver de la tarea (m², und, ml, kg): las cantidades de la receta '
             'son por una de estas unidades.')
    product_id = fields.Many2one(
        'product.product', string='Producto de la partida', check_company=True, index=True,
        help='El que se vende al cliente (línea de la orden de venta o Work Item).')
    source = fields.Selection(RECIPE_SOURCES, string='Origen', default='manual', required=True)
    source_ref = fields.Char(string='Referencia del origen', readonly=True, copy=False,
                             help='Work Item o archivo del que se copió.')
    line_ids = fields.One2many(
        'construction.execution.template.line', 'template_id', string='Recursos', copy=True)
    amount_unit = fields.Monetary(
        string='Costo por unidad', compute='_compute_amount_unit', currency_field='currency_id',
        help='Suma de las líneas a su costo, por una unidad del nivel.')
    note = fields.Html(string='Notas')

    _code_company_unique = models.UniqueIndex(
        '(code, company_id, COALESCE(project_id, 0))',
        'Ya hay una receta con ese código en la compañía (y la obra).')

    @api.depends('line_ids.amount_unit')
    def _compute_amount_unit(self):
        for template in self:
            template.amount_unit = sum(template.line_ids.mapped('amount_unit'))

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for template in self:
            template.display_name = ' '.join(filter(None, [template.code, template.name]))


class ConstructionExecutionTemplateLine(models.Model):
    _name = 'construction.execution.template.line'
    _description = 'Recurso de la plantilla de ejecución'
    _inherit = ['construction.resource.type.mixin']
    _order = 'template_id, sequence, id'
    _check_company_auto = True

    template_id = fields.Many2one(
        'construction.execution.template', string='Receta', required=True, ondelete='cascade',
        index=True)
    company_id = fields.Many2one(related='template_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='template_id.currency_id', string='Moneda')
    sequence = fields.Integer(default=10)
    resource_type = fields.Selection(
        RESOURCE_TYPES, string='Comportamiento', required=True, default='material')
    stage = fields.Selection(stage_selection, string='Etapa')
    product_id = fields.Many2one('product.product', string='Producto', check_company=True)
    activity_id = fields.Many2one(
        'construction.labor.activity', string='Actividad (driver)', check_company=True,
        help='Contrata y personal propio: lo que se reporta y se paga.')
    # Seis decimales: el APU trae rendimientos como 0.042105 h por m².
    qty = fields.Float(string='Cantidad por unidad', digits=(16, 6), required=True,
                       default=1.0)
    product_uom_id = fields.Many2one('uom.uom', string='Unidad', required=True,
                                     default=lambda self: self.env.ref('uom.product_uom_unit'))
    # Con la precisión de «Precio del producto»: el APU trae costos como
    # 0.9661 por ladrillo (CREVAL v1.0, CR-03).
    price_unit = fields.Float(
        string='Costo unitario', digits='Product Price',
        help='Vacío: el costo del producto o la tarifa de la actividad al generar.')
    productivity = fields.Float(
        string='Rendimiento', digits=(16, 4),
        help='Unidades del nivel por jornada de la cuadrilla (p. ej. 19 m² por día).')
    crew_size = fields.Float(
        string='Personas', default=1.0,
        help='Cuántos de este rol tiene la cuadrilla (1 operario, 1 oficial, 0.5 peón).')
    # Sin redondear a la moneda: la receta redondea una sola vez la suma (CR-03).
    amount_unit = fields.Float(
        string='Costo por unidad', compute='_compute_amount_unit', digits='Product Price')
    note = fields.Char(string='Nota')

    @api.depends('qty', 'price_unit', 'product_id.standard_price')
    def _compute_amount_unit(self):
        for line in self:
            price = line.price_unit or line.product_id.standard_price
            line.amount_unit = line.qty * price

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom_id = self.product_id.uom_id

    @api.onchange('activity_id')
    def _onchange_activity_id(self):
        if self.activity_id:
            self.product_uom_id = self.activity_id.uom_id
            self.stage = self.stage or self.activity_id.stage

    @api.constrains('stage')
    def _check_stage_code(self):
        self.env['construction.stage']._check_codes(self)
