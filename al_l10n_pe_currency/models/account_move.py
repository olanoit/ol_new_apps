# -*- coding: utf-8 -*-
"""Muestra el tipo de cambio aplicado y su fecha en facturas en moneda
extranjera (distinta a la de la compañía).

Odoo 19 ya calcula la tasa aplicada en ``invoice_currency_rate`` (dirección
"moneda compañía → moneda del documento"). Aquí se expone de forma amigable
para Perú: el tipo de cambio como **moneda de compañía por 1 unidad de la
moneda del documento** (p. ej. S/ 3.75 por US$ 1) y la **fecha del tipo de
cambio** efectivamente utilizado.
"""
from odoo import api, fields, models
from odoo.tools import format_date


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

    @api.depends('currency_id', 'company_currency_id', 'company_id',
                 'invoice_date', 'date', 'invoice_currency_rate')
    def _compute_l10n_pe_exchange_rate(self):
        Rate = self.env['res.currency.rate']
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
            rate_rec = Rate.search([
                ('currency_id', '=', move.currency_id.id),
                ('company_id', '=', move.company_id.root_id.id),
                ('name', '<=', rate_date),
            ], order='name desc', limit=1)
            applied_date = rate_rec.name if rate_rec else rate_date
            move.l10n_pe_exchange_rate_date = applied_date
            move.l10n_pe_exchange_rate_info = move.env._(
                'T.C. %(rate)s · %(date)s',
                rate='%.3f' % rate,
                date=format_date(move.env, applied_date) if applied_date else '')
