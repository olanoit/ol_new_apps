# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    # Etiquetas en español del marco nativo de retenciones
    withholding_line_ids = fields.One2many(string='Retenciones')
    withholding_net_amount = fields.Monetary(string='Neto a pagar')
    withholding_outstanding_account_id = fields.Many2one(
        string='Cuenta transitoria de pagos',
        help='Cuenta puente del pago cuando el método no tiene cuenta '
             'propia. Se propone desde Ajustes ▸ Perú ▸ «Cuenta '
             'transitoria (retenciones)».')

    @api.depends('can_edit_wizard', 'display_withholding')
    def _compute_withholding_line_ids(self):
        """Monto mínimo del régimen (art. 12 de la R.S. 037-2002/SUNAT):
        no se retiene si los comprobantes pagados juntos (y por tanto el
        pago) suman S/ 700 o menos; si superan el mínimo, se retiene aunque
        cada factura sea menor. En moneda extranjera se convierte al T.C.
        venta oficial de la fecha del pago."""
        super()._compute_withholding_line_ids()
        for wizard in self:
            tax = wizard.company_id.l10n_pe_retention_tax_id
            lines = wizard.withholding_line_ids.filtered(lambda l: l.tax_id == tax)
            if not (tax and lines and wizard.batches):
                continue
            bills = wizard._get_batches()[0]['lines'].move_id.filtered('l10n_pe_retention_eligible')
            total = sum(bill._l10n_pe_retention_base(wizard.payment_date) for bill in bills)
            if total <= wizard.company_id.l10n_pe_retention_min_amount:
                wizard.withholding_line_ids = wizard.withholding_line_ids - lines
                continue
            wizard._l10n_pe_retention_deduct_credit_notes(lines[:1])

    def _l10n_pe_retention_deduct_credit_notes(self, line):
        """Art. 2 de la R.S. 037-2002/SUNAT: la retención de las notas de
        crédito del proveedor sobre facturas ya retenidas se descuenta de
        esta retención (opción de la compañía). Al emitir el pago, la
        diferencia queda imputada a cada nota."""
        self.ensure_one()
        company = self.company_id
        if not company.l10n_pe_retention_deduct_credit_notes:
            return
        partner = self._get_batches()[0]['lines'].move_id.commercial_partner_id[:1]
        company_currency = company.currency_id
        available = self.currency_id._convert(
            line.amount, company_currency, company, self.payment_date)
        plan = self.env['account.move']._l10n_pe_retention_plan_deductions(
            company, partner, available)
        deducted = sum(amount for _note, amount in plan)
        if deducted:
            line.amount = self.currency_id.round(line.amount - company_currency._convert(
                deducted, self.currency_id, company, self.payment_date))

    @api.depends('withholding_payment_account_id', 'withhold')
    def _compute_withholding_outstanding_account_id(self):
        """El nativo solo propone la cuenta copiándola del último pago
        similar: en una base nueva queda vacía y el campo es obligatorio.
        Fallback: la cuenta configurada en la compañía."""
        super()._compute_withholding_outstanding_account_id()
        for wizard in self:
            if (wizard.withhold != 'payment'
                    and not wizard.withholding_payment_account_id
                    and not wizard.withholding_outstanding_account_id):
                wizard.withholding_outstanding_account_id = (
                    wizard.company_id
                    .l10n_pe_retention_outstanding_account_id)
