# -*- coding: utf-8 -*-
"""Diario del asiento de cierre.

Las cuentas de resultado por diferencia de cambio no se redefinen: se usan
las nativas ``income_currency_exchange_account_id`` (776) y
``expense_currency_exchange_account_id`` (676), que son las mismas que Odoo
emplea para la diferencia de cambio **realizada** al conciliar. Así ambas
diferencias, realizada y por cierre, caen en la misma cuenta de resultados.
"""
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_exchange_closing_journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Diario de cierre de T.C.',
        domain="[('type', '=', 'general'), ('company_id', '=', id)]",
        check_company=True,
        help='Diario donde se registran los asientos mensuales de ajuste por '
             'diferencia de cambio. Se recomienda uno dedicado (p. ej. CTC) '
             'para poder aislarlos en los reportes.')
