# -*- coding: utf-8 -*-
from odoo import fields, models

# Sentido de la dinámica de destinos (PCGE peruano).
L10N_PE_DEST_TYPE_SELECTION = [
    ('6a9', 'Destino de cuenta clase 6 a 9'),
    ('9a6', 'Destino de cuenta clase 9 a 6'),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_dest_type = fields.Selection(
        selection=L10N_PE_DEST_TYPE_SELECTION,
        string='Tipo de destino', required=True, default='9a6',
        help='Sentido del asiento de destino: de gasto por naturaleza (6) a '
             'función (9), o viceversa.')
