# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Fuentes que pueden generar un tipo de cambio.
RATE_ORIGINS = [
    ('sunat', 'SUNAT'),
    ('bcrp', 'BCRP'),
    ('decolecta', 'Decolecta'),
    ('apis_net', 'apis.net.pe'),
    ('manual', 'Manual'),
]


class ResCurrencyRate(models.Model):
    _inherit = 'res.currency.rate'

    # Tipo de cambio peruano (SUNAT publica compra y venta). Odoo nativo solo
    # maneja una tasa única (`rate`); estos campos son el valor agregado local.
    rate_purchase = fields.Float(
        string='Compra', digits='Dual_Currency_TRM',
        help='Tipo de cambio compra publicado por SUNAT. Se usa para valorar '
             'los activos en moneda extranjera (artículo 61 de la Ley del '
             'Impuesto a la Renta).')
    rate_sale = fields.Float(
        string='Venta', digits='Dual_Currency_TRM',
        help='Tipo de cambio venta publicado por SUNAT. Es el que rige la '
             'conversión contable, de ahí que la tasa nativa sea 1 / venta.')
    ref_origin = fields.Selection(
        RATE_ORIGINS,
        string='Origen', default='manual', required=True,
        help='Fuente que generó este tipo de cambio.')

    # Nota: se usa la constraint nativa de v19 unique(name, currency_id,
    # company_id) — un tipo de cambio por día/moneda/compañía. `ref_origin` es
    # solo informativo (no forma parte de la unicidad).

    # ------------------------------------------------------------------
    # Coherencia entre la tasa nativa y compra/venta
    # ------------------------------------------------------------------
    @api.model
    def _l10n_pe_sync_values(self, vals, record=None):
        """Mantiene ``rate`` y ``rate_sale`` diciendo lo mismo.

        La tasa nativa de Odoo es «unidades de moneda extranjera por una de la
        compañía», mientras que en Perú se habla de soles por dólar: una es la
        inversa de la otra. Si se registran a mano compra y venta, hay que
        recalcular ``rate``; y si solo se toca ``rate``, hay que reflejarlo en
        la venta, o la ficha quedaría diciendo dos cosas distintas.
        """
        touched_sale = 'rate_sale' in vals
        touched_rate = 'rate' in vals

        sale = vals.get('rate_sale', record.rate_sale if record else 0.0)
        if touched_sale and sale:
            vals['rate'] = 1.0 / sale
        elif touched_rate and not touched_sale and vals.get('rate'):
            vals['rate_sale'] = 1.0 / vals['rate']

        # Sin compra informada se asume la venta: es preferible a dejar un
        # cero que luego se interpretaría como «no hay tipo de cambio».
        purchase = vals.get('rate_purchase',
                            record.rate_purchase if record else 0.0)
        if not purchase and vals.get('rate_sale'):
            vals['rate_purchase'] = vals['rate_sale']
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._l10n_pe_sync_values(vals)
        return super().create(vals_list)

    def write(self, vals):
        if not {'rate', 'rate_sale', 'rate_purchase'} & set(vals):
            return super().write(vals)
        for record in self:
            super(ResCurrencyRate, record).write(
                record._l10n_pe_sync_values(dict(vals), record=record))
        return True

    # ------------------------------------------------------------------
    # Validaciones
    # ------------------------------------------------------------------
    @api.constrains('rate_purchase', 'rate_sale')
    def _check_l10n_pe_rates(self):
        for record in self:
            if record.rate_purchase < 0 or record.rate_sale < 0:
                raise ValidationError(_(
                    'El tipo de cambio no puede ser negativo.'))

    @api.onchange('rate_sale')
    def _onchange_l10n_pe_rate_sale(self):
        """Avisa si la compra supera a la venta, sin bloquear el registro.

        Lo normal es compra < venta, pero no es una regla absoluta y hay días
        en que SUNAT publica valores iguales; por eso es un aviso y no un
        error.
        """
        if self.rate_purchase and self.rate_sale \
                and self.rate_purchase > self.rate_sale:
            return {'warning': {
                'title': _('Tipo de cambio'),
                'message': _('La compra (%(purchase)s) es mayor que la venta '
                             '(%(sale)s). Compruebe los valores.',
                             purchase=self.rate_purchase,
                             sale=self.rate_sale),
            }}
