# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Glosa peruana (descripción del asiento para el PLE / libros).
    l10n_pe_gloss = fields.Char(string='Glosa', copy=False)

    def l10n_pe_is_pe(self):
        """Es un comprobante de una compañía peruana."""
        self.ensure_one()
        return self.country_code == 'PE'
