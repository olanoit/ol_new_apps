# -*- coding: utf-8 -*-
"""Tipo de cambio compra/venta en cobros y pagos.

Un cobro en dólares no tiene por qué convertirse con el mismo tipo de cambio
que la factura que cancela: la factura se valora a la fecha de emisión y el
cobro a la de su propia fecha, y el criterio puede diferir. Por eso el pago
lleva su propia elección.

La conversión no se reimplementa: se indica el tipo de cambio en el contexto y
lo aplica ``res.currency._get_conversion_rate``.
"""
from odoo import api, fields, models

from .res_company import EXCHANGE_RATE_TYPES


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    l10n_pe_exchange_rate_type = fields.Selection(
        EXCHANGE_RATE_TYPES,
        string='Tipo de T.C.',
        compute='_compute_l10n_pe_exchange_rate_type',
        store=True, readonly=False,
        help='Cuál de los dos tipos de cambio de SUNAT se aplica a este '
             'cobro o pago. Se propone según el criterio configurado para '
             'compras y ventas.')

    @api.depends('payment_type', 'company_id')
    def _compute_l10n_pe_exchange_rate_type(self):
        """Un cobro sigue el criterio de ventas; un pago, el de compras."""
        for payment in self:
            company = payment.company_id or self.env.company
            if payment.payment_type == 'outbound':
                payment.l10n_pe_exchange_rate_type = \
                    company.l10n_pe_exchange_rate_type_in or 'sale'
            else:
                payment.l10n_pe_exchange_rate_type = \
                    company.l10n_pe_exchange_rate_type_out or 'sale'

    def _prepare_move_lines_per_type(self, *args, **kwargs):
        # El importe en soles del asiento sale de aquí; basta con anunciar qué
        # tipo de cambio toca para que la conversión lo respete.
        self.ensure_one()
        return super(
            AccountPayment,
            self.with_context(
                l10n_pe_exchange_rate_type=self.l10n_pe_exchange_rate_type),
        )._prepare_move_lines_per_type(*args, **kwargs)


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    # Almacenado aunque sea un asistente: sin ``store`` el compute se vuelve a
    # ejecutar en cada lectura y se perdería lo que elija el usuario.
    l10n_pe_exchange_rate_type = fields.Selection(
        EXCHANGE_RATE_TYPES,
        string='Tipo de T.C.',
        compute='_compute_l10n_pe_exchange_rate_type',
        store=True, readonly=False,
        help='Tipo de cambio que se aplicará al pago que se va a registrar.')

    @api.depends('partner_type', 'company_id')
    def _compute_l10n_pe_exchange_rate_type(self):
        for wizard in self:
            company = wizard.company_id or self.env.company
            if wizard.partner_type == 'supplier':
                wizard.l10n_pe_exchange_rate_type = \
                    company.l10n_pe_exchange_rate_type_in or 'sale'
            else:
                wizard.l10n_pe_exchange_rate_type = \
                    company.l10n_pe_exchange_rate_type_out or 'sale'

    def _create_payment_vals_from_wizard(self, batch_result):
        values = super()._create_payment_vals_from_wizard(batch_result)
        values['l10n_pe_exchange_rate_type'] = self.l10n_pe_exchange_rate_type
        return values

    def _create_payment_vals_from_batch(self, batch_result):
        values = super()._create_payment_vals_from_batch(batch_result)
        values['l10n_pe_exchange_rate_type'] = self.l10n_pe_exchange_rate_type
        return values
