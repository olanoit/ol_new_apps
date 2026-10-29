# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import Command, api, fields, models


class AlPeDemo(models.AbstractModel):
    _inherit = 'al.pe.demo'

    @api.model
    def _load_demo_account_letter(self):
        """Cuentas de letras del PCGE, diarios de letras por cobrar y por
        pagar, el canje de una factura de cliente de S/ 1 180 en tres letras
        (con su redondeo de 0,01), una de ellas enviada a cobranza libre, y el
        canje de una factura de proveedor de S/ 2 360 en dos letras."""
        company = self._demo_company()
        if not company or self._demo_ref('al_l10n_pe_account_letter.demo_letter_supplier'):
            return
        env = self._demo_env(company)
        pen = env.ref('base.PEN')
        Account = env['account.account']
        tax_s, tax_p = self._demo_tax(env, 'sale'), self._demo_tax(env, 'purchase')

        def account(code):
            return Account.search([*Account._check_company_domain(company), ('code', '=', code)], limit=1)

        accounts = {('asset_receivable', 'portfolio'): account('1232000'),
                    ('asset_receivable', 'billing'): account('1233000'),
                    ('asset_receivable', 'discount'): account('1234000')}
        payable = account('4230000')
        if not (all(accounts.values()) and payable and tax_s and tax_p):
            return
        for letter_type in ('portfolio', 'billing', 'discount'):
            accounts[('liability_payable', letter_type)] = payable
        Config = env['l10n_pe.letter.account.config']
        for (account_type, letter_type), letter_account in accounts.items():
            if not Config.search_count([('company_id', '=', company.id), ('account_type', '=', account_type),
                                        ('letter_type', '=', letter_type), ('currency_id', '=', pen.id)]):
                Config.create({'account_type': account_type, 'letter_type': letter_type, 'currency_id': pen.id,
                               'account_id': letter_account.id, 'company_id': company.id})
        company.write({
            'l10n_pe_letter_rounding_loss_account_id': company.l10n_pe_letter_rounding_loss_account_id.id
            or self._demo_account(env, 'al_l10n_pe_account_letter.demo_account_rounding_loss', '659901',
                                  'Redondeo', 'expense').id,
            'l10n_pe_letter_rounding_gain_account_id': company.l10n_pe_letter_rounding_gain_account_id.id
            or self._demo_account(env, 'al_l10n_pe_account_letter.demo_account_rounding_gain', '759901',
                                  'Redondeo', 'income_other').id,
        })
        receivable_journal = self._demo_journal(env, 'al_l10n_pe_account_letter.demo_journal_receivable',
                                                'Letras por cobrar', 'DLEC', 'general', currency_id=pen.id,
                                                l10n_pe_letter_type='receivable')
        payable_journal = self._demo_journal(env, 'al_l10n_pe_account_letter.demo_journal_payable',
                                             'Letras por pagar', 'DLEP', 'general', currency_id=pen.id,
                                             l10n_pe_letter_type='payable')
        sale = self._demo_journal(env, 'al_l10n_pe_account_letter.demo_journal_sale', 'Ventas con letras', 'DLTV',
                                  'sale')
        purchase = self._demo_journal(env, 'al_l10n_pe_account_letter.demo_journal_purchase', 'Compras con letras',
                                      'DLTC', 'purchase')
        customer = self._demo_partner(env, 'al_l10n_pe_account_letter.demo_customer', 'Comercial Los Olivos S.A.C.',
                                      self._demo_ruc('2060555888'))
        supplier = self._demo_partner(env, 'al_l10n_pe_account_letter.demo_supplier', 'Suministros del Norte S.A.C.',
                                      self._demo_ruc('2060555999'))
        bank = self._demo_record('al_l10n_pe_account_letter.demo_bank', env['l10n_pe.bank'], {'name': 'Banco Comercial Andino'})
        today = fields.Date.context_today(self)
        start = today - timedelta(days=20)

        def invoice(key, move_type, partner, journal, tax, amount, ref=False):
            move = self._demo_record('al_l10n_pe_account_letter.demo_%s' % key, env['account.move'], {
                'move_type': move_type, 'partner_id': partner.id, 'journal_id': journal.id,
                'invoice_date': start, 'ref': ref,
                'invoice_line_ids': [Command.create({'name': 'Mercadería', 'quantity': 1, 'price_unit': amount,
                                                     'tax_ids': [Command.set(tax.ids)]})]})
            if move.state == 'draft':
                move.action_post()
            return move

        def exchange(key, partner, move_type, journal, move, number, prefix):
            letter = self._demo_record('al_l10n_pe_account_letter.demo_letter_%s' % key, env['l10n_pe.letter'], {
                'partner_id': partner.id, 'type': move_type, 'journal_id': journal.id,
                'payment_reference': 'LT-%s' % key.upper()})
            line = move.line_ids.filtered(lambda l: l.display_type == 'payment_term')
            letter.write({
                'invoice_date': start + timedelta(days=5),
                'invoice_line_ids': [Command.create({
                    'document_type_id': env.ref('l10n_pe.document_type01').id, 'move_line_id': line.id,
                    'account_id': line.account_id.id, 'imp_div': abs(line.amount_residual_currency)})]})
            letter.action_checked()
            letter.write({'number_letter': number, 'letter_end_date': start + timedelta(days=35), 'range_date': 30})
            letter.action_create_letters()
            for index, letter_line in enumerate(letter.letter_line_ids, start=1):
                letter_line.nro_letter = '%s-%03d' % (prefix, index)
            letter.action_redeemed()
            return letter

        customer_letter = exchange('customer', customer, 'out_invoice', receivable_journal,
                                   invoice('invoice', 'out_invoice', customer, sale, tax_s, 1000.0), 3, 'LET-CLI')
        sent = customer_letter.letter_line_ids.filtered(lambda l: l.payment_state == 'pending')[:1]
        customer_letter.action_canje_create('billing', start + timedelta(days=10), sent)
        sent.write({'bank_id': bank.id, 'code': 'CANJE-CLI-001', 'letter_type': 'billing'})
        exchange('supplier', supplier, 'in_invoice', payable_journal,
                 invoice('bill', 'in_invoice', supplier, purchase, tax_p, 2000.0, ref='F001-00004433'), 2, 'LET-PROV')
