# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class L10nPeHrUit(models.Model):
    """UIT (Unidad Impositiva Tributaria) por año.

    En v18 la UIT colgaba de ``account.fiscal.year``, modelo que ya no
    existe en v19 — pasa a catálogo propio. Es un valor nacional (D.S.
    del MEF), por eso no lleva compañía.
    """
    _name = 'l10n_pe.hr.uit'
    _description = 'UIT por año'
    _order = 'year desc'
    _rec_name = 'year'

    year = fields.Integer(string='Año', required=True)
    amount = fields.Float(string='Valor UIT', required=True)

    _year_uniq = models.Constraint(
        'UNIQUE(year)', 'Ya existe la UIT de ese año.')

    @api.model
    def get_uit(self, year):
        """Valor de la UIT del año; error claro si no está cargada (la
        renta de 5ta no puede calcular con una UIT ausente)."""
        uit = self.search([('year', '=', year)], limit=1)
        if not uit:
            raise UserError(self.env._(
                'No está registrada la UIT del año %(year)s '
                '(Nómina → Configuración → Perú → UIT).', year=year))
        return uit.amount
