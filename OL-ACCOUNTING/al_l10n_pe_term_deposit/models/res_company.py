# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_term_deposit_notice_days = fields.Integer(
        string='Aviso de vencimiento (días)', default=7,
        help='Días antes del vencimiento de un depósito o garantía en que se crea la '
             'actividad de aviso para su responsable.')
