# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # El padrón de l10n_pe_vat_sunat trae agentes de retención y buenos
    # contribuyentes, no agentes de percepción: se marca a mano.
    l10n_pe_is_perception_agent = fields.Boolean(
        string='Agente de percepción',
        help='Designado agente de percepción por SUNAT (padrón de agentes de '
             'percepción). No se le retiene el IGV: art. 5 h) de la R.S. '
             '037-2002/SUNAT.')
