# -*- coding: utf-8 -*-
"""Cumplimiento del 30 % de genéricos (Ley 32033; DS 014-2011-SA, art.
32-A): de los ítems del listado que el local ofrece en versión de marca,
en cuántos tiene disponible el genérico en DCI. Se mide por ítem."""
from odoo import api, fields, models

MINIMUM_RATIO = 30.0


class PharmacyGenericCompliance(models.TransientModel):
    _name = 'pharmacy.generic.compliance'
    _description = 'Cumplimiento de genéricos (Ley 32033)'
    _check_company_auto = True

    warehouse_id = fields.Many2one('stock.warehouse', string='Local', required=True,
                                   check_company=True,
                                   default=lambda self: self.env['stock.warehouse'].search(
                                       [('company_id', '=', self.env.company.id)], limit=1))
    company_id = fields.Many2one('res.company', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    line_ids = fields.One2many('pharmacy.generic.compliance.line', 'report_id', string='Ítems')
    items_with_brand = fields.Integer(string='Ítems ofrecidos de marca', readonly=True)
    items_with_generic = fields.Integer(string='Con genérico disponible', readonly=True)
    ratio = fields.Float(string='Cumplimiento (%)', readonly=True, digits=(5, 1))
    compliant = fields.Boolean(string='Cumple', readonly=True)
    exempt = fields.Boolean(related='company_id.pharmacy_microenterprise', string='Exceptuada')

    def action_compute(self):
        self.ensure_one()
        self.line_ids.unlink()
        Product = self.env['product.template'].with_context(warehouse_id=self.warehouse_id.id)
        lines = []
        for item in self.env['pharmacy.essential.medicine'].search([]):
            products = Product.browse(item._matching_products(self.company_id).ids)
            in_stock = products.filtered(lambda p: p.qty_available > 0)
            brand = in_stock.filtered(lambda p: p.pharmacy_product_type != 'generic_dci')
            generic = in_stock.filtered(lambda p: p.pharmacy_product_type == 'generic_dci')
            if not brand:
                continue
            lines.append({'item_id': item.id, 'brand_product_ids': [(6, 0, brand.ids)],
                          'generic_product_ids': [(6, 0, generic.ids)],
                          'compliant': bool(generic)})
        self.line_ids = [(0, 0, values) for values in lines]
        with_generic = sum(1 for values in lines if values['compliant'])
        ratio = 100.0 * with_generic / len(lines) if lines else 100.0
        self.write({'items_with_brand': len(lines), 'items_with_generic': with_generic,
                    'ratio': ratio, 'compliant': ratio >= MINIMUM_RATIO})
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'target': 'new'}


class PharmacyGenericComplianceLine(models.TransientModel):
    _name = 'pharmacy.generic.compliance.line'
    _description = 'Ítem del cumplimiento de genéricos'

    report_id = fields.Many2one('pharmacy.generic.compliance', required=True, ondelete='cascade')
    item_id = fields.Many2one('pharmacy.essential.medicine', string='Ítem del listado')
    brand_product_ids = fields.Many2many('product.template', 'pharmacy_compliance_brand_rel',
                                         string='De marca en stock')
    generic_product_ids = fields.Many2many('product.template', 'pharmacy_compliance_generic_rel',
                                           string='Genéricos en DCI en stock')
    compliant = fields.Boolean(string='Con genérico')
