# -*- coding: utf-8 -*-
from odoo import api, fields, models

SALE_CONDITIONS = [
    ('otc', 'Venta libre'),
    ('prescription', 'Con receta médica'),
    ('controlled', 'Receta especial (controlado)'),
]

PRODUCT_TYPES = [
    ('generic_dci', 'Genérico en DCI'),
    ('generic_brand', 'Genérico de marca'),
    ('innovator', 'Innovador o de marca'),
]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    pharmacy_ok = fields.Boolean(
        string='Producto farmacéutico',
        help='Medicamentos, dispositivos médicos y productos sanitarios: llevan los datos del '
             'registro sanitario y las reglas de dispensación.')

    # Presentaciones de venta (prototipo E0).
    pharmacy_presentation_ids = fields.One2many(
        'pharmacy.presentation', 'product_tmpl_id', string='Presentaciones',
        help='Cajas, blísteres u otras presentaciones con precio propio. La unidad suelta se '
             'vende al precio del producto.')
    pharmacy_presentation_count = fields.Integer(compute='_compute_pharmacy_presentation_count')

    # Composición y forma
    pharmacy_ingredient_line_ids = fields.One2many(
        'pharmacy.product.ingredient', 'product_tmpl_id', string='Composición', copy=True)
    pharmacy_composition = fields.Char(
        string='Principio activo y concentración', compute='_compute_pharmacy_composition',
        store=True, index='trigram',
        help='Por ejemplo «Paracetamol 500 mg» o, en combinaciones, «Paracetamol 500 mg + '
             'Cafeína 65 mg».')
    pharmacy_dosage_form_id = fields.Many2one('pharmacy.dosage.form', string='Forma farmacéutica')
    pharmacy_route_id = fields.Many2one('pharmacy.route', string='Vía de administración')
    pharmacy_equivalence_key = fields.Char(
        compute='_compute_pharmacy_equivalence_key', store=True, index=True, copy=False,
        help='Mismo principio activo, concentración y forma farmacéutica: productos '
             'intercambiables para ofrecer alternativas.')
    pharmacy_equivalent_ids = fields.Many2many(
        'product.template', string='Equivalentes', compute='_compute_pharmacy_equivalent_ids')

    # Registro sanitario y condición de venta (Ley 29459)
    pharmacy_sale_condition = fields.Selection(
        SALE_CONDITIONS, string='Condición de venta',
        help='La que figura en el registro sanitario.')
    pharmacy_sanitary_registry = fields.Char(
        string='Registro sanitario', help='Número del registro sanitario (p. ej. EN-01234).')
    pharmacy_registry_holder_id = fields.Many2one(
        'res.partner', string='Titular del registro')
    pharmacy_registry_expiry = fields.Date(
        string='Vencimiento del registro',
        help='Con el registro vencido no se puede recibir el producto.')
    pharmacy_laboratory_id = fields.Many2one('res.partner', string='Laboratorio fabricante')
    pharmacy_product_type = fields.Selection(
        PRODUCT_TYPES, string='Tipo de producto',
        help='Los genéricos en DCI se ofrecen primero como alternativa (Ley 32033).')
    pharmacy_linked_company = fields.Boolean(
        string='Empresa vinculada',
        help='Producto de una empresa vinculada al establecimiento: debe informarse al '
             'cliente (Ley 32033, art. 4).')

    # Conservación y ficha
    pharmacy_cold_chain = fields.Boolean(string='Cadena de frío',
                                         help='Se conserva entre 2 °C y 8 °C.')
    pharmacy_storage_conditions = fields.Char(string='Condiciones de almacenamiento')
    pharmacy_shelf = fields.Char(string='Ubicación en estante',
                                 help='Anaquel o casillero donde se exhibe o guarda.')
    pharmacy_indications = fields.Text(string='Indicaciones')
    pharmacy_contraindications = fields.Text(string='Contraindicaciones')
    pharmacy_adverse_effects = fields.Text(string='Efectos adversos')

    @api.depends('pharmacy_presentation_ids')
    def _compute_pharmacy_presentation_count(self):
        for template in self:
            template.pharmacy_presentation_count = len(template.pharmacy_presentation_ids)

    @api.depends('pharmacy_ingredient_line_ids.ingredient_id.name',
                 'pharmacy_ingredient_line_ids.strength',
                 'pharmacy_ingredient_line_ids.strength_unit')
    def _compute_pharmacy_composition(self):
        for template in self:
            template.pharmacy_composition = ' + '.join(
                line._label() for line in template.pharmacy_ingredient_line_ids) or False

    @api.depends('pharmacy_ingredient_line_ids.ingredient_id',
                 'pharmacy_ingredient_line_ids.strength',
                 'pharmacy_ingredient_line_ids.strength_unit', 'pharmacy_dosage_form_id')
    def _compute_pharmacy_equivalence_key(self):
        for template in self:
            lines = template.pharmacy_ingredient_line_ids.filtered('ingredient_id')
            if not lines:
                template.pharmacy_equivalence_key = False
                continue
            template.pharmacy_equivalence_key = '%s|%s' % (
                ','.join(sorted(line._key() for line in lines)),
                template.pharmacy_dosage_form_id.id or '')

    @api.depends('pharmacy_equivalence_key')
    def _compute_pharmacy_equivalent_ids(self):
        keys = [key for key in set(self.mapped('pharmacy_equivalence_key')) if key]
        candidates = self.search([('pharmacy_equivalence_key', 'in', keys)]) if keys else self.browse()
        for template in self:
            if not template.pharmacy_equivalence_key:
                template.pharmacy_equivalent_ids = False
                continue
            template.pharmacy_equivalent_ids = candidates.filtered(
                lambda t: t.pharmacy_equivalence_key == template.pharmacy_equivalence_key
                and t.id != template._origin.id)

    def _pharmacy_sorted_alternatives(self):
        """Equivalentes para ofrecer: primero los genéricos en DCI y, entre
        ellos, del más barato al más caro (Ley 32033, art. 32)."""
        self.ensure_one()
        return self.pharmacy_equivalent_ids.sorted(
            lambda t: (t.pharmacy_product_type != 'generic_dci', t.list_price, t.name))

    def _pharmacy_needs_prescription(self):
        self.ensure_one()
        return self.pharmacy_sale_condition in ('prescription', 'controlled')
