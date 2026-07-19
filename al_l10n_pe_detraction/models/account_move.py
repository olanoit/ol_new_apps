# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.tools import float_round

DETRACTION_OPERATION_TYPES = ('1001', '1002', '1003', '1004')
DEFAULT_MIN_AMOUNT = 700.0


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_detraction_applies = fields.Boolean(
        string='Sujeta a detracción',
        compute='_compute_l10n_pe_detraction', store=True)
    l10n_pe_detraction_type_id = fields.Many2one(
        'l10n_pe.detraction.type', string='Tipo de detracción',
        compute='_compute_l10n_pe_detraction', store=True, readonly=False,
        help='Código dominante (mayor porcentaje) entre los productos de '
             'la factura; puede corregirse manualmente en borrador.')
    l10n_pe_detraction_percent = fields.Float(
        string='% detracción', digits=(5, 2),
        compute='_compute_l10n_pe_detraction', store=True, readonly=False)
    l10n_pe_detraction_amount = fields.Monetary(
        string='Monto de detracción',
        currency_field='company_currency_id',
        compute='_compute_l10n_pe_detraction_amount', store=True,
        help='Detracción en soles, redondeada a enteros (regla SUNAT), '
             'sobre el importe total con IGV convertido a soles.')
    l10n_pe_detraction_net = fields.Monetary(
        string='Neto tras detracción',
        currency_field='company_currency_id',
        compute='_compute_l10n_pe_detraction_amount',
        help='Importe total en soles menos la detracción: lo que se '
             'cobra/paga a la contraparte fuera del Banco de la Nación.')

    @api.depends('invoice_line_ids.product_id', 'amount_total_signed',
                 'move_type', 'company_id')
    def _compute_l10n_pe_detraction(self):
        for move in self:
            best_type = self.env['l10n_pe.detraction.type']
            best_percent = 0.0
            min_amount = DEFAULT_MIN_AMOUNT
            if (move.move_type in ('out_invoice', 'in_invoice')
                    and move.country_code == 'PE'):
                for product in move.invoice_line_ids.product_id:
                    dtype = product.l10n_pe_detraction_type_id
                    percent = (dtype.percentage if dtype
                               else product.l10n_pe_withhold_percentage)
                    if percent > best_percent:
                        best_percent = percent
                        best_type = dtype
                        min_amount = (dtype.min_amount if dtype
                                      else DEFAULT_MIN_AMOUNT)
            base = abs(move.amount_total_signed)
            applies = bool(best_percent) and base > min_amount
            move.l10n_pe_detraction_applies = applies
            move.l10n_pe_detraction_type_id = best_type if applies else False
            move.l10n_pe_detraction_percent = best_percent if applies else 0.0

    @api.depends('l10n_pe_detraction_applies', 'l10n_pe_detraction_percent',
                 'amount_total_signed')
    def _compute_l10n_pe_detraction_amount(self):
        for move in self:
            base = abs(move.amount_total_signed)
            amount = 0.0
            if move.l10n_pe_detraction_applies:
                # depósito sin decimales, igual criterio que el XML nativo
                amount = float_round(
                    base * move.l10n_pe_detraction_percent / 100.0,
                    precision_rounding=1.0)
            move.l10n_pe_detraction_amount = amount
            move.l10n_pe_detraction_net = base - amount

    def _post(self, soft=True):
        # el XML UBL nativo solo emite el bloque «Detraccion» con un tipo
        # de operación 100x: se fija automáticamente si el usuario no lo hizo
        for move in self:
            if (move.l10n_pe_detraction_applies
                    and move.move_type == 'out_invoice'
                    and move.l10n_pe_edi_operation_type
                    not in DETRACTION_OPERATION_TYPES):
                move.l10n_pe_edi_operation_type = '1001'
        return super()._post(soft=soft)

    def action_open_detraction_deposit(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Registrar depósito de detracción'),
            'res_model': 'l10n_pe.detraction.deposit.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_move_id': self.id},
        }
