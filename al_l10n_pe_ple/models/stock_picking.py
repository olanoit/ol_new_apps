# -*- coding: utf-8 -*-
from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    l10n_pe_consignment = fields.Selection(
        [('out_delivery', '9.1 Entrega en consignación (consignador)'),
         ('out_return', '9.1 Devolución del consignatario'),
         ('out_sale', '9.1 Venta de bienes consignados'),
         ('in_receipt', '9.2 Recepción en consignación (consignatario)'),
         ('in_return', '9.2 Devolución al consignador'),
         ('in_sale', '9.2 Venta de bienes recibidos en consignación')],
        string='Consignación PLE (Libro 9)', copy=False,
        help='Marca la operación para incluirla en el Registro de '
             'Consignaciones PLE 9.1 (rol consignador) o 9.2 (rol '
             'consignatario). El contacto del albarán es la contraparte.')
