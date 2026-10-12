# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    l10n_pe_cci = fields.Char(
        string='CCI',
        help='Código de Cuenta Interbancario de 20 dígitos: lo usa el pago masivo cuando la '
             'cuenta del proveedor es de otro banco que el de la empresa.')
    l10n_pe_account_kind = fields.Selection(
        [('checking', 'Corriente'), ('savings', 'Ahorros')], string='Tipo de cuenta',
        default='checking',
        help='Tipo de la cuenta en su banco; algunos formatos de pago masivo lo informan.')

    @api.constrains('l10n_pe_cci')
    def _check_l10n_pe_cci(self):
        for account in self.filtered('l10n_pe_cci'):
            cci = account.l10n_pe_cci.replace('-', '').replace(' ', '')
            if not (cci.isdigit() and len(cci) == 20):
                raise ValidationError(self.env._(
                    'El CCI de la cuenta %(account)s debe tener 20 dígitos.',
                    account=account.display_name))

    def _l10n_pe_preferred(self, current, journal, currency):
        """Cuenta del proveedor con la que conviene pagar desde ``journal``,
        entre las de ``self`` (las disponibles para el pago): si ``current``
        es de otro banco que el del diario y el proveedor tiene una cuenta
        habilitada para pagos en ese mismo banco, en la moneda del pago o sin
        moneda, se abona ahí (directo, sin pasar por la CCI), la corriente
        antes que la de ahorros. Solo con bancos que tienen formato de pago
        masivo."""
        bank = journal.bank_id
        if not bank.l10n_pe_batch_format or current.bank_id == bank:
            return current
        candidates = self.filtered(lambda acc: acc.bank_id == bank and acc.allow_out_payment
                                   and acc.currency_id in (currency, self.env['res.currency']))
        best = candidates.sorted(lambda acc: (acc.l10n_pe_account_kind != 'checking',
                                              not acc.currency_id))[:1]
        return best or current
