# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # Glosa peruana por línea.
    l10n_pe_gloss = fields.Char(string='Glosa', copy=False)
