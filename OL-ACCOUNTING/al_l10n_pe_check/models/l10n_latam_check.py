# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError

# Ley 27287 (Títulos Valores), arts. 199 y 207: el cheque se presenta al cobro
# dentro de los 30 días de su fecha; el de pago diferido, desde la fecha de
# pago indicada y dentro de los 30 días siguientes.
PRESENTATION_DAYS = 30


class L10nLatamCheck(models.Model):
    _inherit = 'l10n_latam.check'

    l10n_pe_presentation_deadline = fields.Date(
        string='Presentar hasta', compute='_compute_l10n_pe_presentation_deadline', store=True,
        help='Último día para presentar el cheque al cobro: 30 días desde su fecha o, si es '
             'de pago diferido, desde la fecha de pago (Ley 27287, arts. 199 y 207).')

    @api.depends('payment_date', 'company_id.account_fiscal_country_id')
    def _compute_l10n_pe_presentation_deadline(self):
        for check in self:
            peru = check.company_id.account_fiscal_country_id.code == 'PE'
            check.l10n_pe_presentation_deadline = peru and check.payment_date \
                and check.payment_date + timedelta(days=PRESENTATION_DAYS)

    def _l10n_pe_presentation_warnings(self, date):
        """Avisos al presentar los cheques al cobro en ``date``."""
        messages = []
        for check in self.filtered('l10n_pe_presentation_deadline'):
            if date < check.payment_date:
                messages.append(self.env._(
                    'El cheque %(check)s es de pago diferido: el banco no lo paga antes del %(date)s.',
                    check=check.display_name, date=check.payment_date.strftime('%d/%m/%Y')))
            elif date > check.l10n_pe_presentation_deadline:
                messages.append(self.env._(
                    'El cheque %(check)s venció su plazo de presentación el %(date)s (30 días): '
                    'el banco puede rechazarlo.',
                    check=check.display_name,
                    date=check.l10n_pe_presentation_deadline.strftime('%d/%m/%Y')))
        return messages

    @api.constrains('issuer_vat')
    def _check_issuer_vat(self):
        # Perú: el emisor puede ser una persona con DNI o carné de extranjería;
        # el nativo exige un RUC.
        peru = self.filtered(lambda c: c.company_id.account_fiscal_country_id.code == 'PE')
        super(L10nLatamCheck, self - peru)._check_issuer_vat()
        Partner = self.env['res.partner']
        for check in peru.filtered('issuer_vat'):
            vat = check.issuer_vat.strip()
            if len(vat) == 11 and vat.isdigit():
                valid = Partner.check_vat_pe(vat)
            else:
                valid = (len(vat) == 8 and vat.isdigit()) or (vat.isalnum() and 8 < len(vat) <= 12)
            if not valid:
                raise ValidationError(self.env._(
                    'El documento del emisor del cheque %(check)s no es válido: RUC de 11 dígitos, '
                    'DNI de 8 o carné de extranjería.', check=check.display_name))
