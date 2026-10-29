# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models


class AlPeDemo(models.AbstractModel):
    _inherit = 'al.pe.demo'

    @api.model
    def _load_demo_batch_payment(self):
        """Un diario BCP en soles con el pago masivo y un lote validado de
        tres pagos a proveedores de tres bancos (BCP, BBVA e Interbank)."""
        company = self._demo_company()
        if not company or self._demo_ref('al_l10n_pe_batch_payment.demo_batch'):
            return
        env = self._demo_env(company)
        pen = env.ref('base.PEN')
        Bank = env['l10n_pe.bank']
        bcp = self._demo_record('al_l10n_pe_batch_payment.demo_bank_bcp', Bank,
                                {'name': 'Banco de Crédito del Perú', 'l10n_pe_batch_format': 'bcp'})
        bbva = self._demo_record('al_l10n_pe_batch_payment.demo_bank_bbva', Bank,
                                 {'name': 'BBVA Perú', 'l10n_pe_batch_format': 'bbva'})
        ibk = self._demo_record('al_l10n_pe_batch_payment.demo_bank_interbank', Bank,
                                {'name': 'Interbank', 'l10n_pe_batch_format': 'interbank'})
        company_account = self._demo_record(
            'al_l10n_pe_batch_payment.demo_company_bank_account', env['res.partner.bank'], {
                'partner_id': company.partner_id.id, 'l10n_pe_bank_id': bcp.id, 'account_number': '191-2233445-0-66',
                'currency_id': pen.id})
        journal = self._demo_journal(env, 'al_l10n_pe_batch_payment.demo_journal_bcp', 'BCP soles', 'DBCP',
                                     'bank', currency_id=pen.id, bank_account_id=company_account.id,
                                     l10n_pe_batch_service_code='P')
        method_line = journal.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'pe_bank_txt')
        trusted_banks = env['res.partner.bank'].with_user(env.ref('base.user_admin')).sudo()
        payments = env['account.payment']
        day = fields.Date.context_today(self) - timedelta(days=2)
        for key, name, vat, bank, number, cci, amount in (
                ('1', 'Maderas del Sur S.A.C.', '2060555501', bcp, '193-7654321-0-22', False, 4820.0),
                ('2', 'Herrajes Lima S.A.C.', '2060555502', bbva, '0011-0456-0200098765',
                 '01145600020009876512', 1350.75),
                ('3', 'Transportes Andinos S.A.C.', '2060555503', ibk, '200-3001234567',
                 '00320000300123456713', 690.0)):
            partner = self._demo_partner(env, 'al_l10n_pe_batch_payment.demo_supplier_%s' % key, name,
                                         self._demo_ruc(vat))
            # Confiar en la cuenta (la exige el pago masivo) lo puede hacer un
            # administrador, no OdooBot: se crea como el administrador (sudo,
            # la carga de datos ya es de superusuario).
            bank_account = self._demo_record(
                'al_l10n_pe_batch_payment.demo_supplier_account_%s' % key, trusted_banks, {
                    'partner_id': partner.id, 'l10n_pe_bank_id': bank.id, 'account_number': number, 'l10n_pe_cci': cci,
                    'allow_out_payment': True})
            payments |= env['account.payment'].create({
                'payment_type': 'outbound', 'partner_type': 'supplier', 'partner_id': partner.id,
                'partner_bank_id': bank_account.id, 'amount': amount, 'journal_id': journal.id,
                'payment_method_line_id': method_line.id, 'date': day,
                'memo': 'F001-0000%s' % key})
        payments.action_post()
        batch = self._demo_record('al_l10n_pe_batch_payment.demo_batch', env['account.batch.payment'], {
            'journal_id': journal.id, 'batch_type': 'outbound', 'date': day,
            'payment_method_id': env.ref('al_l10n_pe_batch_payment.account_payment_method_pe_bank_txt').id,
            'payment_ids': [(6, 0, payments.ids)]})
        batch.validate_batch()
