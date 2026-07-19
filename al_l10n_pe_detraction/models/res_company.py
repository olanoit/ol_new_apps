# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_detraction_split = fields.Boolean(
        string='Separar la detracción en el asiento de la factura',
        help='Al publicar una factura sujeta a detracción, la línea por '
             'cobrar/pagar se reparte dentro del MISMO asiento: el neto '
             'queda en la cuenta normal del cliente/proveedor y la '
             'detracción en la cuenta configurada. Sin esta opción, el '
             'total completo queda en la cuenta del tercero (comportamiento '
             'estándar).')
    l10n_pe_detraction_receivable_account_id = fields.Many2one(
        'account.account', string='Cuenta detracciones por cobrar',
        check_company=True,
        domain=[('account_type', '=', 'asset_receivable')],
        help='Ventas: cuenta donde se registra la detracción que el '
             'cliente depositará en el Banco de la Nación '
             '(p. ej. 121001 Detracciones por cobrar).')
    l10n_pe_detraction_payable_account_id = fields.Many2one(
        'account.account', string='Cuenta detracciones por pagar',
        check_company=True,
        domain=[('account_type', '=', 'liability_payable')],
        help='Compras: cuenta donde se registra la detracción a depositar '
             'a nombre del proveedor (p. ej. 424001 Detracciones por '
             'pagar).')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_detraction_split = fields.Boolean(
        related='company_id.l10n_pe_detraction_split', readonly=False)
    l10n_pe_detraction_receivable_account_id = fields.Many2one(
        related='company_id.l10n_pe_detraction_receivable_account_id',
        readonly=False)
    l10n_pe_detraction_payable_account_id = fields.Many2one(
        related='company_id.l10n_pe_detraction_payable_account_id',
        readonly=False)
