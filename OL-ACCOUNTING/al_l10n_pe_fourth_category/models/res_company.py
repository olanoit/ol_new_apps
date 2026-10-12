# -*- coding: utf-8 -*-
from odoo import Command, api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_fourth_category_agent = fields.Boolean(
        string='Agente de retención de 4.ª categoría', default=True,
        help='Las personas, empresas y entidades obligadas a llevar contabilidad que pagan '
             'o acreditan rentas de cuarta categoría retienen el impuesto a la renta del '
             'prestador (art. 71 de la Ley del Impuesto a la Renta).')
    l10n_pe_fourth_category_rate = fields.Float(
        string='Tasa de retención de 4.ª (%)', default=8.0, digits=(5, 2),
        help='Porcentaje del importe total del recibo por honorarios (8 % vigente).')
    l10n_pe_fourth_category_threshold = fields.Monetary(
        string='Tope sin retención de 4.ª', default=1500.0,
        currency_field='currency_id',
        help='No se retiene cuando el recibo no excede este importe (S/ 1 500 vigente).')
    l10n_pe_fourth_category_account_id = fields.Many2one(
        'account.account', string='Cuenta de retenciones de 4.ª', check_company=True,
        domain=[('account_type', 'in', ('liability_current', 'liability_payable'))],
        help='Pasivo con el fisco por las retenciones practicadas (40172 del PCGE). Sin '
             'ella se usa la 40172 del plan contable peruano.')
    l10n_pe_fourth_category_tax_id = fields.Many2one(
        'account.tax', string='Impuesto de retención de 4.ª', check_company=True,
        domain=[('l10n_pe_fourth_category', '=', True)], readonly=True, copy=False)

    def _l10n_pe_fourth_category_account(self):
        """Cuenta de las retenciones: la configurada o la 40172 del plan
        peruano por su identificador (no por código)."""
        self.ensure_one()
        if self.l10n_pe_fourth_category_account_id:
            return self.l10n_pe_fourth_category_account_id
        return self.env['account.chart.template'].with_company(self).ref(
            'chart40172', raise_if_not_found=False) or self.env['account.account']

    def _l10n_pe_fourth_category_tax(self):
        """Impuesto de retención de 4.ª de la compañía (se crea la primera vez
        y se ajusta a la tasa y la cuenta configuradas)."""
        self.ensure_one()
        account = self._l10n_pe_fourth_category_account()
        tax = self.l10n_pe_fourth_category_tax_id
        rate = -abs(self.l10n_pe_fourth_category_rate)
        name = self.env._('Retención 4.ª categoría %s %%', '%g' % abs(rate))
        if tax:
            vals = {}
            if tax.amount != rate:
                vals.update(amount=rate, name=name)
            tax_line = tax.invoice_repartition_line_ids.filtered(
                lambda line: line.repartition_type == 'tax')
            if account and tax_line.account_id != account:
                (tax.invoice_repartition_line_ids | tax.refund_repartition_line_ids).filtered(
                    lambda line: line.repartition_type == 'tax').account_id = account
            if vals:
                tax.write(vals)
            return tax
        group = self.env['account.tax.group'].search([
            ('company_id', '=', self.id), ('name', '=', self.env._('Retención 4.ª categoría'))],
            limit=1) or self.env['account.tax.group'].create({
                'name': self.env._('Retención 4.ª categoría'), 'company_id': self.id,
                'country_id': self.account_fiscal_country_id.id or self.country_id.id})

        def repartition():
            return [
                Command.create({'repartition_type': 'base'}),
                Command.create({'repartition_type': 'tax',
                                'account_id': account.id or False}),
            ]

        tax = self.env['account.tax'].create({
            'name': name,
            'description': self.env._('Ret. 4.ª'),
            'invoice_label': self.env._('Retención 4.ª categoría'),
            'amount_type': 'percent',
            'amount': rate,
            'type_tax_use': 'purchase',
            'company_id': self.id,
            'country_id': self.account_fiscal_country_id.id or self.country_id.id,
            'tax_group_id': group.id,
            'l10n_pe_fourth_category': True,
            'invoice_repartition_line_ids': repartition(),
            'refund_repartition_line_ids': repartition(),
        })
        self.l10n_pe_fourth_category_tax_id = tax
        return tax


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_fourth_category_agent = fields.Boolean(
        related='company_id.l10n_pe_fourth_category_agent', readonly=False)
    l10n_pe_fourth_category_rate = fields.Float(
        related='company_id.l10n_pe_fourth_category_rate', readonly=False)
    l10n_pe_fourth_category_threshold = fields.Monetary(
        related='company_id.l10n_pe_fourth_category_threshold', readonly=False,
        currency_field='company_currency_id')
    l10n_pe_fourth_category_account_id = fields.Many2one(
        related='company_id.l10n_pe_fourth_category_account_id', readonly=False)

    def set_values(self):
        super().set_values()
        if self.company_id.l10n_pe_fourth_category_tax_id:
            # Tasa o cuenta cambiadas: el impuesto existente se ajusta.
            self.company_id._l10n_pe_fourth_category_tax()
