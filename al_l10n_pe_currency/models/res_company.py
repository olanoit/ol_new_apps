# -*- coding: utf-8 -*-
"""Criterio por defecto de tipo de cambio para compras y ventas.

SUNAT publica dos tipos de cambio y la norma no usa siempre el mismo:

* Para el **IGV**, el Reglamento de la Ley del IGV (artículo 5, numeral 17)
  manda convertir al tipo de cambio **promedio ponderado venta** de la fecha
  en que nace la obligación tributaria. Es el criterio mayoritario y el que
  se toma por defecto en ambos sentidos.
* Para la **Renta**, el Reglamento de la Ley del Impuesto a la Renta
  (artículo 34) usa el tipo de cambio **compra** para los activos y **venta**
  para los pasivos, criterio que ya aplica el cierre de tipo de cambio.

Como el criterio depende de la lectura de cada empresa, se deja configurable
por separado para ventas y para compras, y ajustable factura a factura.
"""
from odoo import fields, models

EXCHANGE_RATE_TYPES = [
    ('sale', 'Venta'),
    ('purchase', 'Compra'),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_exchange_rate_type_out = fields.Selection(
        EXCHANGE_RATE_TYPES,
        string='T.C. en ventas', default='sale',
        help='Tipo de cambio que se aplica por defecto a las facturas y notas '
             'emitidas en moneda extranjera.')
    l10n_pe_exchange_rate_type_in = fields.Selection(
        EXCHANGE_RATE_TYPES,
        string='T.C. en compras', default='sale',
        help='Tipo de cambio que se aplica por defecto a las facturas y notas '
             'de proveedor en moneda extranjera.')
