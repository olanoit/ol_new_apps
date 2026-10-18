# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import Command, api, fields, models


class AlPeDemo(models.AbstractModel):
    _inherit = 'al.pe.demo'

    @api.model
    def _load_demo_factoring(self):
        """Un factor, un cliente y tres operaciones: sin recurso con dos
        facturas (cedida y desembolsada), con recurso (desembolsada y con
        intereses devengados) y una en borrador."""
        company = self._demo_company()
        if not company or self._demo_ref('al_l10n_pe_factoring.demo_operation_3'):
            return
        env = self._demo_env(company)
        Journal = env['account.journal']
        misc = Journal.search([*Journal._check_company_domain(company), ('type', '=', 'general')], limit=1)
        bank = self._demo_bank_journal(env)
        if not misc or not bank:
            return
        factor = self._demo_partner(env, 'al_l10n_pe_factoring.demo_factor', 'Factor Capital S.A.',
                                    self._demo_ruc('2060123456'))
        customer = self._demo_partner(env, 'al_l10n_pe_factoring.demo_customer',
                                      'Inmobiliaria del Sur S.A.C.', self._demo_ruc('2060987654'))
        sale = self._demo_journal(env, 'al_l10n_pe_factoring.demo_journal_sale', 'Ventas con factoring', 'DFAC', 'sale')
        today = fields.Date.context_today(self)

        def invoice(key, amount, days_ago):
            move = self._demo_record('al_l10n_pe_factoring.demo_invoice_%s' % key, env['account.move'], {
                'move_type': 'out_invoice', 'partner_id': customer.id, 'journal_id': sale.id,
                'invoice_date': today - timedelta(days=days_ago),
                'invoice_date_due': today + timedelta(days=60 - days_ago),
                'invoice_line_ids': [Command.create({'name': 'Avance de obra', 'quantity': 1, 'price_unit': amount,
                                                     'tax_ids': [Command.clear()]})]})
            if move.state == 'draft':
                move.action_post()
            return move

        def operation(key, invoices, modality, percent, contract):
            return self._demo_record('al_l10n_pe_factoring.demo_operation_%s' % key, env['l10n_pe.factoring'], {
                'factor_id': factor.id, 'modality': modality, 'journal_id': misc.id,
                'currency_id': company.currency_id.id, 'default_advance_percent': percent,
                'contract_ref': contract,
                'line_ids': [Command.create({
                    'move_id': inv.id, 'advance_percent': percent, 'cavali_number': 'CAV-%s' % inv.id,
                    'cavali_date': today, 'conformity_state': 'presumed',
                    'conformity_date': inv.invoice_date + timedelta(days=8)}) for inv in invoices]})

        def wizard(op, kind, **vals):
            env['l10n_pe.factoring.wizard'].create(dict({
                'factoring_id': op.id, 'operation': kind, 'date': today, 'bank_journal_id': bank.id},
                **vals)).action_apply()

        year = today.year
        op1 = operation('1', invoice('1', 12000.0, 10) | invoice('2', 8500.0, 5), 'without_recourse', 90.0,
                        'CT-%s-015' % year)
        op1.action_assign()
        wizard(op1, 'disburse', interest_amount=245.0, fee_amount=120.0, expense_amount=35.0)
        op2 = operation('2', invoice('3', 15000.0, 3), 'with_recourse', 85.0, 'CT-%s-016' % year)
        op2.action_assign()
        wizard(op2, 'disburse', interest_amount=310.0, fee_amount=90.0)
        wizard(op2, 'accrue', amount=155.0)
        operation('3', invoice('4', 6400.0, 1), 'without_recourse', 90.0, 'CT-%s-017' % year)
