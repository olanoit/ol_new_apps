# -*- coding: utf-8 -*-
"""Observatorio Peruano de Productos Farmacéuticos (DS 014-2011-SA, art. 30;
Ley 29459, art. 28-A): el establecimiento informa el precio de su oferta y lo
actualiza cuando cambia o entra un producto nuevo. Cada cambio de precio de
un producto con código DIGEMID queda «pendiente de informar» hasta que se
exporta."""
from odoo import api, fields, models


class PharmacyObservatoryPrice(models.Model):
    _name = 'pharmacy.observatory.price'
    _description = 'Precio para el Observatorio de productos farmacéuticos'
    _order = 'date desc, id desc'
    _check_company_auto = True

    product_tmpl_id = fields.Many2one('product.template', string='Producto', required=True,
                                      ondelete='cascade', index=True, check_company=True)
    digemid_code = fields.Char(string='Código DIGEMID', required=True)
    date = fields.Datetime(string='Fecha', required=True, default=fields.Datetime.now)
    unit_price = fields.Monetary(string='Precio unitario', currency_field='currency_id')
    package_price = fields.Monetary(string='Precio por empaque', currency_field='currency_id',
                                    help='Precio de la presentación más grande (caja).')
    state = fields.Selection([('pending', 'Pendiente de informar'), ('reported', 'Informado')],
                             string='Estado', default='pending', required=True, index=True)
    reported_date = fields.Datetime(string='Informado el', readonly=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)

    @api.model
    def _pharmacy_register_prices(self, templates):
        """Un pendiente por producto: si ya hay uno, se actualiza el precio."""
        company = self.env.company
        for template in templates:
            box = template.pharmacy_presentation_ids.sorted('factor')[-1:]
            values = {
                'digemid_code': template.pharmacy_digemid_code,
                'unit_price': template.list_price,
                'package_price': box.price if box else template.list_price,
                'date': fields.Datetime.now(),
            }
            pending = self.search([('product_tmpl_id', '=', template.id), ('state', '=', 'pending'),
                                   ('company_id', '=', company.id)], limit=1)
            if pending:
                pending.write(values)
            else:
                self.create({**values, 'product_tmpl_id': template.id, 'company_id': company.id})


class PharmacyPresentation(models.Model):
    _inherit = 'pharmacy.presentation'

    def write(self, vals):
        result = super().write(vals)
        if 'price' in vals:
            self.product_tmpl_id.filtered(lambda t: t.pharmacy_ok and t.pharmacy_digemid_code) \
                ._pharmacy_observatory_register()
        return result
