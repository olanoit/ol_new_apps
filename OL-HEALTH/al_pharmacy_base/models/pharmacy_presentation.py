# -*- coding: utf-8 -*-
"""Presentaciones de venta de un producto (caja, blíster, frasco…).

El stock se lleva siempre en la unidad del producto (p. ej. tableta). Cada
presentación agrupa un número fijo de unidades y tiene su propio precio, que
no tiene por qué ser proporcional al de la unidad (Ley 29459, art. 27.5:
venta por unidad, blíster o caja). La unidad de medida de la presentación
(«Caja x 100») se crea sola, relativa a la del producto, y se agrega a sus
empaques (``uom_ids``): así la factura o boleta la usa y el código de barras
del empaque funciona en el TPV.
"""
from odoo import Command, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare, float_is_zero


class PharmacyPresentation(models.Model):
    _name = 'pharmacy.presentation'
    _description = 'Presentación de venta'
    _order = 'product_tmpl_id, sequence, factor, id'
    _check_company_auto = True

    product_tmpl_id = fields.Many2one(
        'product.template', string='Producto', required=True, index=True, ondelete='cascade',
        check_company=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Presentación', required=True,
                       help='Por ejemplo Caja, Blíster o Frasco.')
    factor = fields.Float(
        string='Unidades', required=True, digits='Product Unit',
        help='Cuántas unidades del producto (en su unidad de medida) trae la presentación.')
    price = fields.Monetary(string='Precio', currency_field='currency_id',
                            help='Precio de venta de la presentación completa, con la '
                                 'misma base (con o sin impuestos) que el precio del producto.')
    unit_price = fields.Float(
        string='Precio por unidad', compute='_compute_unit_price', digits=(16, 6),
        help='Precio de la presentación dividido entre sus unidades: es el que lleva la '
             'línea del TPV, sin redondear.')
    uom_id = fields.Many2one('uom.uom', string='Unidad de la presentación', readonly=True,
                             ondelete='restrict')
    currency_id = fields.Many2one(related='product_tmpl_id.currency_id')
    company_id = fields.Many2one(related='product_tmpl_id.company_id', store=True, index=True)
    active = fields.Boolean(default=True)

    _factor_positive = models.Constraint('CHECK(factor > 0)',
                                         'Las unidades de la presentación deben ser mayores que cero.')
    _factor_unique = models.Constraint('UNIQUE(product_tmpl_id, factor)',
                                       'El producto ya tiene una presentación con esas unidades.')

    @api.depends('name', 'factor')
    def _compute_display_name(self):
        for presentation in self:
            presentation.display_name = '%s x %s' % (presentation.name or '',
                                                     self._format_factor(presentation.factor))

    @api.depends('price', 'factor')
    def _compute_unit_price(self):
        for presentation in self:
            presentation.unit_price = (presentation.price / presentation.factor
                                       if presentation.factor else 0.0)

    @api.model
    def _format_factor(self, factor):
        return ('%f' % factor).rstrip('0').rstrip('.') if factor else '0'

    @api.constrains('factor', 'product_tmpl_id')
    def _check_factor(self):
        for presentation in self:
            if float_compare(presentation.factor, 1.0, precision_digits=6) <= 0:
                raise ValidationError(self.env._(
                    'Una presentación agrupa más de una unidad: la unidad suelta se vende al '
                    'precio del producto.'))

    # ------------------------------------------------------------------
    # Unidad de medida de la presentación
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        presentations = super().create(vals_list)
        presentations._sync_uom()
        return presentations

    def write(self, vals):
        result = super().write(vals)
        if {'name', 'factor', 'product_tmpl_id'} & set(vals):
            self._sync_uom()
        return result

    def _sync_uom(self):
        """Busca o crea la unidad «<nombre> x <unidades>» relativa a la del
        producto y la agrega a sus empaques."""
        # Los usuarios de inventario no crean unidades de medida (solo
        # Ajustes): la de la presentación es un dato técnico que se deriva de
        # ella, así que se busca y se crea como superusuario.
        uom_sudo = self.env['uom.uom'].sudo()
        for presentation in self:
            base_uom = presentation.product_tmpl_id.uom_id
            name = presentation.display_name
            uom = uom_sudo.search([
                ('relative_uom_id', '=', base_uom.id), ('name', '=', name)], limit=1)
            if not uom or float_compare(uom.relative_factor, presentation.factor,
                                        precision_digits=6):
                uom = uom_sudo.create(presentation._prepare_uom_values(base_uom))
            if presentation.uom_id != uom:
                super(PharmacyPresentation, presentation).write({'uom_id': uom.id})
            if uom not in presentation.product_tmpl_id.uom_ids:
                presentation.product_tmpl_id.uom_ids = [Command.link(uom.id)]

    def _prepare_uom_values(self, base_uom):
        """Valores de la unidad de la presentación. Las localizaciones
        agregan aquí sus códigos (p. ej. la unidad SUNAT del comprobante)."""
        self.ensure_one()
        return {
            'name': self.display_name,
            'relative_factor': self.factor,
            'relative_uom_id': base_uom.id,
        }

    def _get_quantity_in_presentations(self, quantity):
        """Número de presentaciones que suman ``quantity`` unidades, o
        ``None`` si no es un número entero de presentaciones."""
        self.ensure_one()
        count = quantity / self.factor
        if float_is_zero(count - round(count), precision_digits=6):
            return round(count)
        return None
