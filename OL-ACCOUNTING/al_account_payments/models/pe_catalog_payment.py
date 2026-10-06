# -*- coding: utf-8 -*-

from odoo import api, fields, models


class PeCatalogPayment(models.Model):
    """Catálogo de medios de pago de SUNAT (catálogo 1 — medios de pago).

    En v18 heredaba del modelo genérico ``pe.catalog`` de
    ``al_account_base``; ese modelo se eliminó en el refactor v19, por lo
    que aquí el catálogo es autónomo y define sus propios campos base.
    """
    _name = 'pe.catalog.payment'
    _description = 'PE: Catálogo de medios de pago'
    _order = 'code'
    _rec_names_search = ['name', 'code']

    active = fields.Boolean(string='Activo', default=True)
    code = fields.Char(string='Código', size=4, index=True, required=True)
    name = fields.Char(string='Descripción', size=128, index=True, required=True)
    pse_code = fields.Char(string='Código de facturador', size=5)
    is_detraction = fields.Boolean(
        string='Para detracción',
        help='Medio de pago usado para el depósito de detracción al proveedor.')

    @api.depends('code', 'name')
    def _compute_display_name(self):
        """Muestra el registro como «código - descripción»."""
        for catalog in self:
            if catalog.code and catalog.name:
                catalog.display_name = f'{catalog.code} - {catalog.name}'
            else:
                catalog.display_name = catalog.name
