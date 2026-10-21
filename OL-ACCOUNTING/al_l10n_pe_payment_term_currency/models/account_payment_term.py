from odoo import fields, models


class AccountPaymentTerm(models.Model):
    _inherit = 'account.payment.term'

    def _compute_terms(self, date_ref, currency, company, tax_amount, tax_amount_currency, sign,
                       untaxed_amount, untaxed_amount_currency, cash_rounding=None):
        """Las cuotas fijas marcadas «Importe en soles» valen ese importe en la moneda
        de la compañía; en la moneda de la factura, al tipo de cambio de la factura
        (el mismo que Odoo usa para las demás cuotas). La última cuota, que es el
        saldo, absorbe la diferencia."""
        res = super()._compute_terms(
            date_ref, currency, company, tax_amount, tax_amount_currency, sign,
            untaxed_amount, untaxed_amount_currency, cash_rounding=cash_rounding)
        company_currency = company.currency_id
        lines = self.line_ids
        flagged = [i for i, line in enumerate(lines[:-1])
                   if line.value == 'fixed' and line.l10n_pe_company_currency]
        if not flagged or currency == company_currency or len(res['line_ids']) != len(lines):
            return res
        total_amount = tax_amount + untaxed_amount
        total_amount_currency = tax_amount_currency + untaxed_amount_currency
        rate = abs(total_amount_currency / total_amount) if total_amount else 0.0
        for i in flagged:
            term_vals = res['line_ids'][i]
            term_vals['company_amount'] = sign * company_currency.round(lines[i].value_amount)
            term_vals['foreign_amount'] = sign * currency.round(lines[i].value_amount * rate)
            if cash_rounding:
                difference = cash_rounding.compute_difference(currency, term_vals['foreign_amount'])
                if not currency.is_zero(difference):
                    term_vals['foreign_amount'] += difference
                    term_vals['company_amount'] = company_currency.round(term_vals['foreign_amount'] / rate) \
                        if rate else 0.0
        balance = res['line_ids'][-1]
        others = res['line_ids'][:-1]
        balance['company_amount'] = total_amount - sum(vals['company_amount'] for vals in others)
        balance['foreign_amount'] = total_amount_currency - sum(vals['foreign_amount'] for vals in others)
        return res


class AccountPaymentTermLine(models.Model):
    _inherit = 'account.payment.term.line'

    l10n_pe_company_currency = fields.Boolean(
        string='Importe en soles',
        help='Cuota fija pactada en la moneda de la compañía: en una factura en dólares se convierte '
             'al tipo de cambio de la factura. Sin marcar, el importe está en la moneda de la factura.')
