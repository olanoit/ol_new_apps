# -*- coding: utf-8 -*-
"""Tipo de cambio compra/venta en las facturas en moneda extranjera.

Dos cosas:

* **Elección del tipo de cambio.** SUNAT publica compra y venta, y cuál se
  aplica depende de la operación y del criterio de la empresa. Cada
  comprobante lleva su elección, propuesta desde la configuración de la
  compañía, y esa elección **cambia el importe en soles**: se engancha en
  ``_get_expected_currency_rate_at``, de donde cuelga
  ``invoice_currency_rate``.
* **Visualización.** Odoo expresa la tasa como "moneda compañía → moneda del
  documento"; aquí se muestra al derecho para Perú (S/ 3.75 por US$ 1), con la
  fecha del tipo de cambio realmente aplicado y si fue compra o venta.
"""
from odoo import api, fields, models
from odoo.tools import format_date

from .res_company import EXCHANGE_RATE_TYPES


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_exchange_rate = fields.Float(
        string='Tipo de cambio', digits='Dual_Currency_TRM',
        compute='_compute_l10n_pe_exchange_rate',
        help='Moneda de la compañía por 1 unidad de la moneda del documento, '
             'según la tasa aplicada a esta factura.')
    l10n_pe_exchange_rate_date = fields.Date(
        string='Fecha del T.C.', compute='_compute_l10n_pe_exchange_rate',
        help='Fecha del tipo de cambio efectivamente aplicado.')
    l10n_pe_exchange_rate_info = fields.Char(
        string='T.C. aplicado', compute='_compute_l10n_pe_exchange_rate',
        help='Tipo de cambio aplicado y su fecha, para mostrar junto a la '
             'moneda en facturas en moneda extranjera.')

    l10n_pe_exchange_rate_type = fields.Selection(
        EXCHANGE_RATE_TYPES,
        string='Tipo de T.C.',
        compute='_compute_l10n_pe_exchange_rate_type',
        store=True, readonly=False,
        help='Cuál de los dos tipos de cambio de SUNAT se aplica a este '
             'comprobante. Se propone según el criterio configurado para '
             'compras y ventas, y puede cambiarse mientras esté en borrador.')

    @api.depends('move_type', 'company_id')
    def _compute_l10n_pe_exchange_rate_type(self):
        """Propone el criterio configurado en la compañía para cada sentido."""
        for move in self:
            company = move.company_id or self.env.company
            if move.move_type in ('out_invoice', 'out_refund', 'out_receipt'):
                move.l10n_pe_exchange_rate_type = \
                    company.l10n_pe_exchange_rate_type_out or 'sale'
            elif move.move_type in ('in_invoice', 'in_refund', 'in_receipt'):
                move.l10n_pe_exchange_rate_type = \
                    company.l10n_pe_exchange_rate_type_in or 'sale'
            else:
                move.l10n_pe_exchange_rate_type = False

    # ------------------------------------------------------------------
    # Conversión
    # ------------------------------------------------------------------
    def _get_expected_currency_rate_at(self, date):
        """Aplica el tipo de cambio compra o venta según el comprobante.

        Odoo trabaja con una única tasa por día; en Perú hay dos y la elección
        cambia el importe en soles del comprobante. Se sobreescribe aquí, que
        es de donde cuelgan ``expected_currency_rate`` e
        ``invoice_currency_rate``, para que la elección se propague sola.

        Cuando no hay tasa peruana registrada para esa fecha —o la compañía no
        es peruana— se mantiene el comportamiento nativo.
        """
        self.ensure_one()
        rate = self._l10n_pe_rate_record(date)
        value = rate.rate_purchase if self.l10n_pe_exchange_rate_type == 'purchase' \
            else rate.rate_sale
        if rate and value:
            # La tasa nativa va de la moneda de la compañía a la del
            # documento, es decir la inversa de «soles por dólar».
            return 1.0 / value
        return super()._get_expected_currency_rate_at(date)

    def _l10n_pe_rate_record(self, date):
        """Tipo de cambio peruano vigente en esa fecha, si lo hay."""
        self.ensure_one()
        if not self.currency_id or self.currency_id == self.company_currency_id:
            return self.env['res.currency.rate']
        if not self.l10n_pe_exchange_rate_type:
            return self.env['res.currency.rate']
        return self.env['res.currency.rate'].search([
            ('currency_id', '=', self.currency_id.id),
            ('company_id', '=', self.company_id.root_id.id),
            ('name', '<=', date or fields.Date.context_today(self)),
        ], order='name desc', limit=1)

    # Los dos computes nativos se reexponen con una dependencia más: al
    # cambiar de compra a venta hay que rehacer la conversión. El segundo es
    # imprescindible porque ``_compute_invoice_currency_rate`` **no** depende
    # de ``expected_currency_rate``, sino de la misma lista de campos que
    # este, de modo que sin esto la tasa almacenada se quedaría como estaba.
    @api.depends('currency_id', 'company_currency_id', 'company_id',
                 'invoice_date', 'taxable_supply_date',
                 'l10n_pe_exchange_rate_type')
    def _compute_expected_currency_rate(self):
        return super()._compute_expected_currency_rate()

    @api.depends('currency_id', 'company_currency_id', 'company_id',
                 'invoice_date', 'taxable_supply_date',
                 'l10n_pe_exchange_rate_type')
    def _compute_invoice_currency_rate(self):
        return super()._compute_invoice_currency_rate()

    @api.depends('currency_id', 'company_currency_id', 'company_id',
                 'invoice_date', 'date', 'invoice_currency_rate',
                 'l10n_pe_exchange_rate_type')
    def _compute_l10n_pe_exchange_rate(self):
        labels = dict(EXCHANGE_RATE_TYPES)
        for move in self:
            foreign = bool(move.currency_id) and move.currency_id != move.company_currency_id
            if not foreign:
                move.l10n_pe_exchange_rate = 0.0
                move.l10n_pe_exchange_rate_date = False
                move.l10n_pe_exchange_rate_info = False
                continue
            # Tasa aplicada (moneda compañía por 1 unidad de la moneda del doc).
            # invoice_currency_rate = moneda_compañía → moneda_doc, así que su
            # inversa es lo que el usuario espera ver (p. ej. 3.75).
            rate = (1.0 / move.invoice_currency_rate) if move.invoice_currency_rate else 0.0
            move.l10n_pe_exchange_rate = rate
            # Fecha del registro de tipo de cambio realmente usado.
            rate_date = move._get_invoice_currency_rate_date()
            rate_record = move._l10n_pe_rate_record(rate_date)
            applied_date = rate_record.name if rate_record else rate_date
            move.l10n_pe_exchange_rate_date = applied_date
            kind = labels.get(move.l10n_pe_exchange_rate_type, '')
            move.l10n_pe_exchange_rate_info = move.env._(
                'T.C. %(kind)s %(rate)s · %(date)s',
                kind=kind,
                rate='%.3f' % rate,
                date=format_date(move.env, applied_date) if applied_date else '')
