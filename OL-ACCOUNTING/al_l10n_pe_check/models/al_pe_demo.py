# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import Command, api, fields, models


class AlPeDemo(models.AbstractModel):
    _inherit = 'al.pe.demo'

    @api.model
    def _load_demo_check(self):
        """Cartera de cheques de terceros: uno al día ya depositado, uno en
        cartera, uno de pago diferido y otro con el plazo de presentación
        vencido; y un cheque propio girado a un proveedor."""
        company = self._demo_company()
        if not company or self._demo_ref('al_l10n_pe_check.demo_payment_4'):
            return
        env = self._demo_env(company)
        company._l10n_pe_check_setup()
        portfolio = env['account.chart.template'].ref('l10n_pe_third_party_check', raise_if_not_found=False)
        bank_journal = self._demo_bank_journal(env)
        if not portfolio or not bank_journal:
            return
        bank = self._demo_record('al_l10n_pe_check.demo_bank', env['res.bank'],
                                 {'name': 'Banco de Crédito', 'bic': 'BCPLPEPL'})
        customer = self._demo_partner(env, 'al_l10n_pe_check.demo_customer', 'Ferretería Los Andes S.A.C.',
                                      self._demo_ruc('2061223334'))
        person = self._demo_partner(env, 'al_l10n_pe_check.demo_person', 'Rosa Quispe Mamani', '41234567')
        supplier = self._demo_partner(env, 'al_l10n_pe_check.demo_supplier', 'Maderas Selva Central S.A.C.',
                                      self._demo_ruc('2061556667'))
        today = fields.Date.context_today(self)
        new_line = portfolio.inbound_payment_method_line_ids.filtered(lambda l: l.code == 'new_third_party_checks')

        def receive(key, partner, number, amount, date):
            payment = self._demo_record('al_l10n_pe_check.demo_payment_%s' % key, env['account.payment'], {
                'payment_type': 'inbound', 'partner_type': 'customer', 'partner_id': partner.id,
                'journal_id': portfolio.id, 'payment_method_line_id': new_line.id,
                'date': min(date, today),
                'l10n_latam_new_check_ids': [Command.create({
                    'name': number, 'bank_id': bank.id, 'payment_date': date, 'amount': amount})],
            })
            payment.action_post()
            return payment.l10n_latam_new_check_ids

        deposited = receive('1', customer, '00045871', 3540.0, today - timedelta(days=6))
        receive('2', customer, '00045902', 1180.0, today - timedelta(days=2))
        receive('3', person, '00731125', 850.0, today + timedelta(days=15))
        receive('4', person, '00730988', 420.0, today - timedelta(days=45))
        env['l10n_latam.payment.mass.transfer'].with_context(
            active_model='l10n_latam.check', active_ids=deposited.ids).create({
                'destination_journal_id': bank_journal.id, 'payment_date': today - timedelta(days=5),
                'communication': 'Depósito de cheques'})._create_payments()
        own_line = bank_journal.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'own_checks')[:1]
        if own_line.payment_account_id:
            own = self._demo_record('al_l10n_pe_check.demo_payment_5', env['account.payment'], {
                'payment_type': 'outbound', 'partner_type': 'supplier', 'partner_id': supplier.id,
                'journal_id': bank_journal.id, 'payment_method_line_id': own_line.id, 'date': today,
                'l10n_latam_new_check_ids': [Command.create({
                    'name': '00001021', 'payment_date': today + timedelta(days=10), 'amount': 2360.0})],
            })
            own.action_post()
