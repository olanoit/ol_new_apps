# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class L10nPeDetractionDepositWizard(models.TransientModel):
    """Registra el depósito de la detracción y su constancia.

    - Compras: la empresa deposita la detracción en la cuenta del Banco de
      la Nación del proveedor → pago parcial de la factura desde el diario
      elegido.
    - Ventas: el cliente depositó la detracción en nuestra cuenta del BN →
      cobro parcial de la factura en el diario que representa esa cuenta.

    En ambos casos se llena la constancia (número y fecha), que alimenta
    los campos 32-33 del PLE 8.1 (``l10n_pe_reports``)."""
    _name = 'l10n_pe.detraction.deposit.wizard'
    _description = 'Depósito de detracción SPOT'

    move_id = fields.Many2one(
        'account.move', string='Comprobante', required=True, readonly=True)
    company_currency_id = fields.Many2one(
        related='move_id.company_currency_id')
    amount = fields.Monetary(
        string='Monto del depósito', currency_field='company_currency_id',
        compute='_compute_amount', store=True, readonly=False)
    journal_id = fields.Many2one(
        'account.journal', string='Diario del depósito', required=True,
        check_company=True, domain="[('type', 'in', ('bank', 'cash'))]",
        help='Compras: diario del banco desde el que se depositó. Ventas: '
             'diario que representa la cuenta de detracciones del Banco de '
             'la Nación.')
    payment_date = fields.Date(
        string='Fecha de la constancia', required=True,
        default=fields.Date.context_today)
    constancy_number = fields.Char(
        string='Nº de constancia', required=True, size=24)

    @api.depends('move_id')
    def _compute_amount(self):
        for wizard in self:
            wizard.amount = wizard.move_id.l10n_pe_detraction_amount

    def action_confirm(self):
        self.ensure_one()
        move = self.move_id
        if move.state != 'posted':
            raise UserError(self.env._(
                'El comprobante debe estar publicado.'))
        if self.amount <= 0:
            raise UserError(self.env._(
                'El monto del depósito debe ser mayor a cero.'))
        register = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=move.ids,
        ).create({
            'amount': self.amount,
            'currency_id': move.company_currency_id.id,
            'journal_id': self.journal_id.id,
            'payment_date': self.payment_date,
            'communication': self.env._(
                'Detracción %(number)s - %(move)s',
                number=self.constancy_number, move=move.name),
        })
        register._create_payments()
        move.write({
            'l10n_pe_detraction_number': self.constancy_number,
            'l10n_pe_detraction_date': self.payment_date,
        })
        return True
