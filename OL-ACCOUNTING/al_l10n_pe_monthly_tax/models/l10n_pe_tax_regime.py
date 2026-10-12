# -*- coding: utf-8 -*-
from odoo import fields, models

TAX_REGIMES = [
    ('general', 'Régimen General'),
    ('mype', 'Régimen MYPE Tributario'),
    ('special', 'Régimen Especial (RER)'),
]


class L10nPeTaxRegime(models.Model):
    """Régimen tributario de la compañía (del RUC) desde una fecha."""
    _name = 'l10n_pe.tax.regime'
    _description = 'Régimen tributario'
    _order = 'company_id, date_from desc'
    _check_company_auto = True

    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company.root_id)
    regime = fields.Selection(TAX_REGIMES, string='Régimen', required=True, default='general')
    date_from = fields.Date(
        string='Desde', required=True,
        help='Primer día del periodo en que rige (el acogimiento o el cambio de régimen).')
    note = fields.Char(string='Nota')

    _regime_unique = models.Constraint(
        'UNIQUE(company_id, date_from)', 'Ya hay un régimen registrado desde esa fecha.')
