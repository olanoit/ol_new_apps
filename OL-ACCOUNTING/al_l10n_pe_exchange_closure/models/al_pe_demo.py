# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import Command, api, fields, models


class AlPeDemo(models.AbstractModel):
    _inherit = 'al.pe.demo'

    @api.model
    def _load_demo_exchange_closure(self):
        """Movimientos en dólares de hace dos meses (venta y compra a crédito
        y un depósito en la cuenta corriente en M.E.), el cierre de ese mes
        contabilizado y el del mes siguiente calculado, con T.C. de cierre
        registrados (sin descargarlos de internet)."""
        company = self._demo_company()
        if not company or self._demo_ref('al_l10n_pe_exchange_closure.demo_closure_2'):
            return
        env = self._demo_env(company)
        usd = env.ref('base.USD')
        usd.active = True
        Account = env['account.account']

        def account(code):
            return Account.search([*Account._check_company_domain(company), ('code', '=', code)], limit=1)

        receivable, payable = account('1212000'), account('4212000')
        # Cuenta propia en dólares: una del plan ya puede tener apuntes en otra moneda.
        bank = self._demo_account(env, 'al_l10n_pe_exchange_closure.demo_account_bank_usd', '1041901',
                                  'Cuenta corriente en dólares (demostración)', 'asset_current',
                                  currency_id=usd.id)
        income = Account.search([*Account._check_company_domain(company), ('account_type', '=', 'income')], limit=1)
        expense = Account.search([*Account._check_company_domain(company), ('account_type', '=', 'expense')], limit=1)
        if not (bank and receivable and payable and income and expense):
            return
        journal = self._demo_journal(env, 'al_l10n_pe_exchange_closure.demo_journal', 'Cierre de tipo de cambio',
                                     'DCTC', 'general')
        company.l10n_pe_exchange_closing_journal_id = journal
        bank.write({'currency_id': usd.id, 'l10n_pe_exchange_closing': 'summary'})
        (receivable | payable).write({'l10n_pe_exchange_closing': 'detail'})
        customer = self._demo_partner(env, 'al_l10n_pe_exchange_closure.demo_customer', 'Importadora Pacífico S.A.C.',
                                      self._demo_ruc('2060555666'))
        supplier = self._demo_partner(env, 'al_l10n_pe_exchange_closure.demo_supplier', 'Exportadora Andina S.A.C.',
                                      self._demo_ruc('2060555777'))
        first = fields.Date.context_today(self).replace(day=1) - relativedelta(months=2)
        # T.C. de cierre: el del último día del mes se registra con la fecha
        # del día siguiente, como lo publica SUNAT.
        usd._l10n_pe_upsert_rate(first + relativedelta(months=1), 3.410, 3.418, 'manual')
        usd._l10n_pe_upsert_rate(first + relativedelta(months=2), 3.395, 3.404, 'manual')

        def entry(key, day, lines):
            """Asiento en dólares: (cuenta, US$, T.C., socio)."""
            move = self._demo_record('al_l10n_pe_exchange_closure.demo_move_%s' % key, env['account.move'], {
                'move_type': 'entry', 'journal_id': journal.id, 'date': first.replace(day=day),
                'ref': 'Saldo en dólares %s' % key,
                'line_ids': [Command.create({
                    'account_id': acc.id, 'partner_id': partner.id, 'currency_id': usd.id, 'amount_currency': amount,
                    'balance': round(amount * rate, 2), 'name': 'Saldo en dólares %s' % key,
                }) for acc, amount, rate, partner in lines]})
            if move.state == 'draft':
                move.action_post()

        no_partner = env['res.partner']
        entry('venta', 15, [(receivable, 10000.0, 3.389, customer), (income, -10000.0, 3.389, no_partner)])
        entry('compra', 18, [(expense, 6000.0, 3.384, no_partner), (payable, -6000.0, 3.384, supplier)])
        entry('banco', 22, [(bank, 5000.0, 3.386, no_partner), (income, -5000.0, 3.386, no_partner)])
        Closure = env['l10n_pe.exchange.closure']
        for key, period in (('1', first), ('2', first + relativedelta(months=1))):
            closure = self._demo_record('al_l10n_pe_exchange_closure.demo_closure_%s' % key, Closure, {
                'company_id': company.id, 'currency_id': usd.id, 'month': '%02d' % period.month,
                'year': period.year, 'journal_id': journal.id})
            closure.action_fetch_rate()
            closure.action_compute()
            if key == '1':
                closure.action_post()
