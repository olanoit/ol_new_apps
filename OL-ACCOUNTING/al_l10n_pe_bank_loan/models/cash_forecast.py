# -*- coding: utf-8 -*-
from odoo import fields, models


class L10nPeCashForecast(models.Model):
    _inherit = 'l10n_pe.cash.forecast'

    def _l10n_pe_source_values(self, journals):
        # Cuotas pendientes de los préstamos vigentes (sin las de gracia total,
        # que no mueven dinero).
        values = super()._l10n_pe_source_values(journals)
        company = self.company_id
        lines = self.env['l10n_pe.bank.loan.line'].search([
            ('company_id', 'child_of', company.root_id.id), ('loan_state', '=', 'running'),
            ('state', '=', 'pending'), ('amount_total', '>', 0)])
        for line in lines:
            values.append({
                'category': 'loan',
                'partner_id': line.partner_id.commercial_partner_id.id,
                'name': self.env._('Cuota %(seq)s %(loan)s', seq=line.sequence, loan=line.loan_id.name),
                'date_due': line.date_due,
                'amount': -line.currency_id._convert(line.amount_total, self.currency_id, company, self.date_from),
                'source_ref': 'l10n_pe.bank.loan.line,%s' % line.id,
            })
        return values


class L10nPeCashForecastLine(models.Model):
    _inherit = 'l10n_pe.cash.forecast.line'

    category = fields.Selection(selection_add=[('loan', 'Cuota de préstamo')], ondelete={'loan': 'cascade'})
