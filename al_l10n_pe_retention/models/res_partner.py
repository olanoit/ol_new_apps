# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_pe_retention_agent = fields.Boolean(
        string='Agente de retención del IGV',
        help='El contacto fue designado agente de retención por SUNAT: '
             'las operaciones entre agentes están exceptuadas de la '
             'retención.')
    l10n_pe_good_contributor = fields.Boolean(
        string='Buen contribuyente',
        help='Proveedor con calidad de «buen contribuyente»: exceptuado '
             'de la retención del IGV.')
