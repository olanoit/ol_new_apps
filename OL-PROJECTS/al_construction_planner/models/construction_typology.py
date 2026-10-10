# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .common import ML_GROUPS, MODULE_TYPES, TYPOLOGY_FAMILIES


class ConstructionTypology(models.Model):
    """Tipología de ambiente de una obra (p. ej. «Cocina tipo 01»): plantilla
    de sus módulos, actividades por ambiente y lista de materiales."""
    _name = 'construction.typology'
    _description = 'Tipología de la obra'
    _inherit = ['mail.thread']
    _order = 'project_id, family, code'
    _check_company_auto = True

    project_id = fields.Many2one(
        'project.project', string='Obra', required=True, index=True, check_company=True,
        domain=[('is_construction_site', '=', True)], tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True, store=True,
        compute='_compute_company_id', precompute=True, readonly=False,
        default=lambda self: self.env.company,
        help='La de la obra; si la obra es compartida entre compañías, la activa al crearlo.')
    code = fields.Char(string='Código', required=True, tracking=True)
    name = fields.Char(string='Nombre', required=True, tracking=True)
    family = fields.Selection(
        TYPOLOGY_FAMILIES, string='Familia', required=True, default='kitchen', tracking=True)
    active = fields.Boolean(string='Activo', default=True)
    product_tmpl_id = fields.Many2one(
        'product.template', string='Producto', check_company=True,
        help='Mueble terminado de la tipología: lo que fabrica la OF.')
    bom_id = fields.Many2one(
        'mrp.bom', string='Lista de materiales', check_company=True,
        domain="[('product_tmpl_id', '=', product_tmpl_id)]",
        help='Lista de materiales de un ambiente de esta tipología: de ella salen las '
             'líneas de material del plan y los componentes de la OF.')
    module_line_ids = fields.One2many(
        'construction.typology.module', 'typology_id', string='Módulos', copy=True)
    activity_line_ids = fields.One2many(
        'construction.typology.activity', 'typology_id', string='Actividades por ambiente',
        copy=True)
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
        string='Armado por módulo', compute='_compute_reference_amounts',
        currency_field='currency_id',
        help='Armado de los módulos a la tarifa vigente de la obra (referencia).')
    space_contract_amount = fields.Monetary(
        string='Contratas por ambiente', compute='_compute_reference_amounts',
        currency_field='currency_id',
        help='Actividades por ambiente a la tarifa vigente de la obra (referencia).')
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    space_task_count = fields.Integer(
        string='Ambientes', compute='_compute_space_task_count')

    _code_unique = models.Constraint(
        'UNIQUE(project_id, family, code)',
        'El código de la tipología debe ser único por obra y familia.')

    @api.depends('project_id')
    def _compute_company_id(self):
        for record in self:
            record.company_id = (record.project_id.company_id or record.company_id
                                 or self.env.company)

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

    @api.depends('module_line_ids.assembly_activity_id', 'activity_line_ids.qty',
                 'activity_line_ids.activity_id')
    def _compute_reference_amounts(self):
        for typology in self:
            project = typology.project_id
            typology.module_assembly_amount = sum(
                line.assembly_activity_id._get_rate(project)[0]
                for line in typology.module_line_ids if line.assembly_activity_id)
            typology.space_contract_amount = sum(
                line.qty * line.activity_id._get_rate(project)[0]
                for line in typology.activity_line_ids)

    def _compute_space_task_count(self):
        counts = dict(self.env['project.task']._read_group(
            [('construction_typology_id', 'in', self.ids)],
            groupby=['construction_typology_id'], aggregates=['__count']))
        for typology in self:
            typology.space_task_count = counts.get(typology, 0)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for typology in self:
            typology.display_name = typology.name or typology.code

    def action_view_space_tasks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Ambientes de %s', self.display_name),
            'res_model': 'project.task',
            'view_mode': 'list,form',
            'domain': [('construction_typology_id', '=', self.id)],
        }


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


class ConstructionTypologyActivity(models.Model):
    """Actividad que no se mide por módulo, con su cantidad por ambiente."""
    _name = 'construction.typology.activity'
    _description = 'Actividad por ambiente de la tipología'
    _order = 'typology_id, sequence, id'
    _check_company_auto = True

    typology_id = fields.Many2one(
        'construction.typology', string='Tipología', required=True, ondelete='cascade',
        index=True, check_company=True)
    company_id = fields.Many2one(
        related='typology_id.company_id', string='Compañía', store=True, index=True)
    sequence = fields.Integer(string='Orden', default=10)
    activity_id = fields.Many2one(
        'construction.labor.activity', string='Actividad', required=True, check_company=True)
    stage = fields.Selection(related='activity_id.stage', string='Etapa')
    uom_id = fields.Many2one(related='activity_id.uom_id', string='Unidad')
    qty = fields.Float(
        string='Cantidad por ambiente', digits=(16, 4), required=True,
        help='Unidades de driver de un ambiente de esta tipología '
             '(p. ej. instalación de mueble bajo: 2.12 ML).')
