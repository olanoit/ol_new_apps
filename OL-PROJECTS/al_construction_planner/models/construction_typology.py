# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .common import TYPOLOGY_ALIAS_SOURCES, UNIT_OVERRIDE_KINDS


class ConstructionTypology(models.Model):
    """Tipología de unidad o ambiente de una obra (p. ej. «Cocina tipo 01»):
    sus otros nombres, variantes, producto y actividades por ambiente. Los
    módulos, metros lineales, muebles y la lista de materiales los agrega el
    rubro mobiliario (v1.7, M17-04)."""
    _name = 'construction.typology'
    _description = 'Tipología de la obra'
    _inherit = ['mail.thread']
    _order = 'project_id, code'
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
    active = fields.Boolean(string='Activo', default=True)
    variant_of_id = fields.Many2one(
        'construction.typology', string='Variante de', index=True, check_company=True,
        domain="[('project_id', '=', project_id), ('id', '!=', id)]",
        help='Tipología base de una variante con sufijo (03A, 01.1): se agrupan juntas en '
             'los reportes.')
    variant_ids = fields.One2many('construction.typology', 'variant_of_id', string='Variantes')
    alias_ids = fields.One2many(
        'construction.typology.alias', 'typology_id', string='Otros nombres', copy=True,
        help='Cómo se llama la tipología en la cotización, la orden del cliente, el itemizado '
             'o el ETO: el importador la reconoce por cualquiera de ellos.')
    product_tmpl_id = fields.Many2one(
        'product.template', string='Producto', check_company=True,
        help='Lo que se fabrica o se entrega de la tipología (el mueble terminado).')
    activity_line_ids = fields.One2many(
        'construction.typology.activity', 'typology_id', string='Actividades por ambiente',
        copy=True)
    space_contract_amount = fields.Monetary(
        string='Contratas por ambiente', compute='_compute_space_contract_amount',
        currency_field='currency_id',
        help='Actividades por ambiente a la tarifa vigente de la obra (referencia).')
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    space_task_count = fields.Integer(
        string='Ambientes', compute='_compute_space_task_count')

    @api.depends('project_id')
    def _compute_company_id(self):
        for record in self:
            record.company_id = (record.project_id.company_id or record.company_id
                                 or self.env.company)

    @api.depends('activity_line_ids.qty', 'activity_line_ids.activity_id')
    def _compute_space_contract_amount(self):
        for typology in self:
            project = typology.project_id
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

    @api.constrains('variant_of_id')
    def _check_variant_of(self):
        for typology in self.filtered('variant_of_id'):
            if typology.variant_of_id.project_id != typology.project_id:
                raise ValidationError(self.env._(
                    'La tipología %s solo puede ser variante de otra de la misma obra.',
                    typology.display_name))
            if typology.variant_of_id.variant_of_id:
                raise ValidationError(self.env._(
                    'La tipología base de %s no puede ser a su vez una variante.',
                    typology.display_name))

    @api.model
    def _find_by_name(self, project, text, typologies=None):
        """Tipología de la obra por su código, su nombre o cualquiera de sus
        otros nombres (sin distinguir mayúsculas, espacios ni guiones):
        «VK-01», «V-K-01» y «COCINA 05» pueden ser la misma."""
        key = self._name_key(text)
        if not key:
            return self.browse()
        typologies = typologies if typologies is not None else self.search(
            [('project_id', '=', project.id)])
        for typology in typologies:
            names = [typology.code, typology.name] + typology.alias_ids.mapped('name')
            if key in {self._name_key(name) for name in names}:
                return typology
        return self.browse()

    @staticmethod
    def _name_key(text):
        return ''.join(ch for ch in (text or '').upper() if ch.isalnum())

    def action_view_space_tasks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Ambientes de %s', self.display_name),
            'res_model': 'project.task',
            'view_mode': 'list,form',
            'domain': [('construction_typology_id', '=', self.id)],
        }


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


class ConstructionTypologyAlias(models.Model):
    """Otro nombre de una tipología en un documento (v1.5, M15-04)."""
    _name = 'construction.typology.alias'
    _description = 'Otro nombre de la tipología'
    _order = 'typology_id, source, name'

    typology_id = fields.Many2one(
        'construction.typology', string='Tipología', required=True, ondelete='cascade',
        index=True)
    company_id = fields.Many2one(related='typology_id.company_id', store=True, index=True)
    name = fields.Char(string='Nombre', required=True)
    source = fields.Selection(
        TYPOLOGY_ALIAS_SOURCES, string='Documento', required=True, default='quote')


class ConstructionUnitOverride(models.Model):
    """Variante de una unidad o un ambiente frente a su tipología (v1.5,
    M15-04): otro color de un material, un componente excluido o un metrado
    distinto. El generador del plan la aplica a los materiales del ambiente
    (y de todos los ambientes de la unidad)."""
    _name = 'construction.unit.override'
    _description = 'Variante de la unidad'
    _order = 'task_id, id'
    _check_company_auto = True

    task_id = fields.Many2one(
        'project.task', string='Unidad o ambiente', required=True, ondelete='cascade',
        index=True, check_company=True,
        domain="[('construction_level', 'in', ('apartment', 'space'))]")
    project_id = fields.Many2one(related='task_id.project_id', store=True, index=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', compute='_compute_company_id', store=True, index=True,
        precompute=True)
    kind = fields.Selection(UNIT_OVERRIDE_KINDS, string='Tipo', required=True, default='color')
    product_id = fields.Many2one(
        'product.product', string='Producto', required=True, check_company=True,
        help='El material de la tipología al que se aplica la variante.')
    new_product_id = fields.Many2one(
        'product.product', string='Reemplazar por', check_company=True,
        help='Solo para «Color o acabado»: el material que se usa en su lugar.')
    qty = fields.Float(
        string='Cantidad por ambiente', digits='Product Unit',
        help='Solo para «Metrado distinto»: la cantidad que reemplaza a la de la tipología.')
    note = fields.Text(string='Nota')

    @api.depends('task_id.company_id', 'task_id.project_id.company_id')
    def _compute_company_id(self):
        # En Odoo 19 la obra puede no tener compañía: la de la tarea, la de la
        # obra o la activa (como la tipología).
        for override in self:
            override.company_id = override.task_id.company_id \
                or override.task_id.project_id.company_id or self.env.company

    @api.constrains('kind', 'new_product_id', 'qty')
    def _check_values(self):
        for override in self:
            if override.kind == 'color' and not override.new_product_id:
                raise ValidationError(self.env._(
                    'La variante de color de %s necesita el material que reemplaza.',
                    override.task_id.display_name))
            if override.kind == 'qty' and override.qty < 0:
                raise ValidationError(self.env._('La cantidad de la variante no puede ser negativa.'))

    def _apply_to_material(self, product, qty):
        """(producto, cantidad) de una línea de material tras las variantes;
        ``None`` si se excluye."""
        for override in self.filtered(lambda o: o.product_id == product):
            if override.kind == 'exclude':
                return None
            if override.kind == 'qty':
                qty = override.qty
            elif override.kind == 'color':
                product = override.new_product_id
        return product, qty

