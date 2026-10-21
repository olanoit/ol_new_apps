# -*- coding: utf-8 -*-
"""Tipo de cambio compra/venta en cobros y pagos.

Un cobro en dólares no tiene por qué convertirse con el mismo tipo de cambio
que la factura que cancela: la factura se valora a la fecha de emisión y el
cobro a la de su propia fecha, y el criterio puede diferir. Por eso el pago
lleva su propia elección.

La conversión no se reimplementa: se indica el tipo de cambio en el contexto y
lo aplica ``res.currency._get_conversion_rate``.
"""
from odoo import _, api, fields, models

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

    l10n_pe_agreed_rate = fields.Float(
        string='T.C. pactado', digits=(12, 4), copy=False,
        help='Tipo de cambio acordado con el banco o con el cliente para esta operación (soles '
             'por unidad de la moneda extranjera). Reemplaza al de SUNAT en el pago; la '
             'diferencia con el de la factura se registra como diferencia de cambio.')

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
                l10n_pe_exchange_rate_type=self.l10n_pe_exchange_rate_type,
                l10n_pe_agreed_rate=self.l10n_pe_agreed_rate),
        )._prepare_move_lines_per_type(*args, **kwargs)

    @api.model
    def _get_trigger_fields_to_synchronize(self):
        # Cambiar compra/venta en un pago en borrador debe rehacer su asiento,
        # igual que cambiar la fecha o el importe.
        return super()._get_trigger_fields_to_synchronize() + (
            'l10n_pe_exchange_rate_type', 'l10n_pe_agreed_rate')


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

    writeoff_account_id = fields.Many2one(compute='_compute_writeoff_account_id', store=True, readonly=False)
    l10n_pe_agreed_rate = fields.Float(
        string='T.C. pactado', digits=(12, 4),
        help='Tipo de cambio acordado para este cobro o pago (soles por unidad de la moneda '
             'extranjera). El importe se calcula con él y la diferencia con el de la factura '
             'queda como diferencia de cambio.')

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

    def _l10n_pe_with_rate_type(self):
        """El asistente con el tipo de cambio elegido en el contexto: el
        núcleo convierte aquí la diferencia de pago (write-off), el importe
        forzado y el descuento por pronto pago, y deben ir al mismo tipo de
        cambio que la línea de liquidez del pago."""
        return self.with_context(
            l10n_pe_exchange_rate_type=self.l10n_pe_exchange_rate_type,
            l10n_pe_agreed_rate=self.l10n_pe_agreed_rate)

    def _l10n_pe_agreed_in_company_currency(self):
        """Pago en soles de documentos en otra moneda con T.C. pactado."""
        self.ensure_one()
        return bool(self.l10n_pe_agreed_rate and self.currency_id == self.company_currency_id
                    and self.source_currency_id and self.source_currency_id != self.company_currency_id)

    def _get_total_amounts_to_pay(self, batch_results):
        """Base de todos los importes del asistente (importe propuesto,
        diferencia, cuotas). Con T.C. pactado:

        * pago en la moneda extranjera: los importes no cambian; el pactado
          valora el pago en soles (asiento) y Odoo registra la diferencia de
          cambio al conciliar;
        * pago en soles: el importe sale del pactado, pero la diferencia se
          mide al cambio del día, que es como Odoo concilia; esa diferencia se
          salda contra la cuenta de diferencia de cambio
          (``_compute_writeoff_account_id``).
        """
        if len(self) != 1 or not self.l10n_pe_agreed_rate:
            return super()._get_total_amounts_to_pay(batch_results)
        agreed = super(AccountPaymentRegister, self._l10n_pe_with_rate_type()) \
            ._get_total_amounts_to_pay(batch_results)
        if not self._l10n_pe_agreed_in_company_currency():
            return agreed
        native = super()._get_total_amounts_to_pay(batch_results)
        return {**native, 'amount_by_default': agreed['amount_by_default'],
                'full_amount': agreed['full_amount']}

    @api.depends('early_payment_discount_mode', 'l10n_pe_agreed_rate', 'currency_id')
    def _compute_payment_difference_handling(self):
        super()._compute_payment_difference_handling()
        for wizard in self.filtered(lambda w: w.can_edit_wizard and w._l10n_pe_agreed_in_company_currency()):
            wizard.payment_difference_handling = 'reconcile'

    @api.depends('l10n_pe_agreed_rate', 'currency_id', 'payment_difference', 'payment_type')
    def _compute_writeoff_account_id(self):
        for wizard in self:
            if not (wizard.can_edit_wizard and wizard._l10n_pe_agreed_in_company_currency()
                    and not wizard.currency_id.is_zero(wizard.payment_difference)):
                wizard.writeoff_account_id = wizard.writeoff_account_id
                continue
            # Se cobra menos (o se paga más) de lo que vale al cambio del día: pérdida.
            loss = (wizard.payment_difference > 0) == (wizard.payment_type == 'inbound')
            company = wizard.company_id
            wizard.writeoff_account_id = company.expense_currency_exchange_account_id if loss \
                else company.income_currency_exchange_account_id
            wizard.writeoff_label = _('Diferencia de cambio (T.C. pactado %s)', wizard.l10n_pe_agreed_rate)

    @api.depends('can_edit_wizard', 'source_amount', 'source_amount_currency', 'source_currency_id',
                 'company_id', 'currency_id', 'payment_date', 'installments_mode', 'l10n_pe_agreed_rate')
    def _compute_amount(self):
        return super()._compute_amount()

    def _create_payment_vals_from_wizard(self, batch_result):
        values = super(
            AccountPaymentRegister, self._l10n_pe_with_rate_type(),
        )._create_payment_vals_from_wizard(batch_result)
        values['l10n_pe_exchange_rate_type'] = self.l10n_pe_exchange_rate_type
        values['l10n_pe_agreed_rate'] = self.l10n_pe_agreed_rate
        return values

    def _create_payment_vals_from_batch(self, batch_result):
        values = super(
            AccountPaymentRegister, self._l10n_pe_with_rate_type(),
        )._create_payment_vals_from_batch(batch_result)
        values['l10n_pe_exchange_rate_type'] = self.l10n_pe_exchange_rate_type
        values['l10n_pe_agreed_rate'] = self.l10n_pe_agreed_rate
        return values
