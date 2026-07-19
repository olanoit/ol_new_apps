# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class L10nPeDetractionType(models.Model):
    """Catálogo 54 de SUNAT: bienes y servicios sujetos a detracción, con
    el porcentaje y el monto mínimo vigentes (R.S. 183-2004/SUNAT y
    modificatorias). Es la fuente de verdad del módulo: los productos se
    sincronizan con los campos nativos que usa el XML UBL."""
    _name = 'l10n_pe.detraction.type'
    _description = 'Tipo de detracción SPOT (catálogo 54 SUNAT)'
    _order = 'code'

    code = fields.Char(string='Código', size=3, required=True)
    name = fields.Char(string='Descripción', required=True, translate=False)
    percentage = fields.Float(
        string='Porcentaje (%)', digits=(5, 2), required=True,
        help='Porcentaje de detracción vigente (p. ej. 12 para 12 %).')
    min_amount = fields.Float(
        string='Monto mínimo (S/)', digits=(12, 2), default=700.0,
        help='Importe total (IGV incluido) a partir del cual aplica la '
             'detracción. 0 = aplica a cualquier monto.')
    comment = fields.Text(string='Notas')
    active = fields.Boolean(default=True)
    product_count = fields.Integer(compute='_compute_product_count')

    _code_uniq = models.Constraint(
        'unique (code)', 'El código del catálogo 54 debe ser único.')

    @api.depends('code')
    def _compute_display_name(self):
        for record in self:
            record.display_name = '[%s] %s' % (record.code, record.name)

    def _compute_product_count(self):
        groups = self.env['product.template']._read_group(
            [('l10n_pe_detraction_type_id', 'in', self.ids)],
            ['l10n_pe_detraction_type_id'], ['__count'])
        counts = {dtype.id: count for dtype, count in groups}
        for record in self:
            record.product_count = counts.get(record.id, 0)

    @api.constrains('percentage')
    def _check_percentage(self):
        for record in self:
            if not 0 < record.percentage <= 100:
                raise ValidationError(self.env._(
                    'El porcentaje de detracción debe estar entre 0 y 100.'))

    def action_sync_products(self):
        """Reaplica el % vigente del catálogo a los productos vinculados
        (campos nativos que usa el XML UBL)."""
        for record in self:
            products = self.env['product.template'].search(
                [('l10n_pe_detraction_type_id', '=', record.id)])
            products.write({
                'l10n_pe_withhold_code': record.code,
                'l10n_pe_withhold_percentage': record.percentage,
            })
        return True

    def action_view_products(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.display_name,
            'res_model': 'product.template',
            'view_mode': 'list,form',
            'domain': [('l10n_pe_detraction_type_id', '=', self.id)],
        }
