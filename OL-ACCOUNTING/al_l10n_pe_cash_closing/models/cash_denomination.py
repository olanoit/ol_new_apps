from odoo import api, fields, models


class L10nPeCashDenomination(models.Model):
    """Billete o moneda que se cuenta en el arqueo."""
    _name = 'l10n_pe.cash.denomination'
    _description = 'Denominación de billete o moneda'
    _order = 'currency_id, sequence, value desc'

    currency_id = fields.Many2one('res.currency', string='Moneda', required=True)
    value = fields.Float(string='Valor', required=True, digits=(12, 2))
    kind = fields.Selection([('bill', 'Billete'), ('coin', 'Moneda')], string='Tipo', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _value_uniq = models.Constraint(
        'unique(currency_id, value, kind)', 'La denominación ya existe para esa moneda.')

    @api.depends('value', 'kind', 'currency_id')
    def _compute_display_name(self):
        kinds = dict(self._fields['kind']._description_selection(self.env))
        for denomination in self:
            amount = denomination.currency_id.format(denomination.value) if denomination.currency_id \
                else denomination.value
            denomination.display_name = '%s de %s' % (kinds.get(denomination.kind, ''), amount)
