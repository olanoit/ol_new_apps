"""Preparación común de las pruebas de la app Cobranza."""
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import TransactionCase

from odoo.addons.al_account_base.tests.common import use_pe_company


class CollectionCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        # Hora de Lima, como la cartera: si no, cerca de medianoche «hoy» difiere.
        cls.env = cls.env(context=dict(cls.env.context, tz='America/Lima'))
        cls.company = cls.env.company
        if not cls.company.external_report_layout_id:
            cls.company.external_report_layout_id = cls.env.ref('web.external_layout_standard')
        cls.today = fields.Date.context_today(cls.env['res.partner'])
        group_user = cls.env.ref('al_l10n_pe_collection.group_collection_user')
        cls.collector = cls.env['res.users'].create({
            'name': 'Gestora Cobranza', 'login': 'gestora_cobranza', 'email': 'gestora@example.com',
            'group_ids': [Command.set([group_user.id])],
            'company_id': cls.company.id, 'company_ids': [Command.set(cls.company.ids)],
        })
        cls.other_collector = cls.env['res.users'].create({
            'name': 'Otro Gestor', 'login': 'otro_gestor', 'email': 'otro@example.com',
            'group_ids': [Command.set([group_user.id])],
            'company_id': cls.company.id, 'company_ids': [Command.set(cls.company.ids)],
        })
        cls.zone = cls.env['l10n_pe.collection.zone'].create({'name': 'Lima Norte', 'user_id': cls.collector.id})
        cls.customer, cls.other_customer = cls.env['res.partner'].create([
            # Empresas: el art. 62 (horario de contacto) solo protege a consumidores.
            # Odoo 20: es empresa quien tiene RUC (is_company se calcula del vat).
            {'name': 'CLIENTE COBRANZA SAC', 'email': 'cliente@example.com',
             'vat': '20100070970', 'country_id': cls.env.ref('base.pe').id},
            {'name': 'OTRO CLIENTE SAC', 'email': 'otro.cliente@example.com',
             'vat': '20131312955', 'country_id': cls.env.ref('base.pe').id},
        ])
        cls.customer.with_company(cls.company).write({
            'followup_responsible_id': cls.collector.id, 'l10n_pe_collection_zone_id': cls.zone.id})
        cls.other_customer.with_company(cls.company).followup_responsible_id = cls.other_collector
        cls.sale_journal = cls.env['account.journal'].create({
            'name': 'Ventas cobranza', 'code': 'VTCO', 'type': 'sale', 'l10n_latam_use_documents': False})
        outstanding = cls.env['account.account'].create({
            'name': 'Pendientes (prueba cobranza)', 'code': '104188', 'account_type': 'asset_current',
            'reconcile': True})
        cls.bank = cls.env['account.journal'].create({
            'name': 'Banco cobranza', 'code': 'BKCO', 'type': 'bank', 'company_id': cls.company.id})
        (cls.bank.inbound_payment_method_line_ids | cls.bank.outbound_payment_method_line_ids) \
            .payment_account_id = outstanding
        cls.result_promise = cls.env.ref('al_l10n_pe_collection.result_promise')
        cls.result_no_answer = cls.env.ref('al_l10n_pe_collection.result_no_answer')

    # ------------------------------------------------------------------ ayuda
    def _invoice(self, amount, due_in, partner=None, invoice_date=None):
        due = self.today + timedelta(days=due_in)
        move = self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': (partner or self.customer).id,
            'journal_id': self.sale_journal.id,
            'invoice_date': invoice_date or min(due, self.today) - timedelta(days=1),
            'invoice_date_due': due,
            'invoice_line_ids': [Command.create({'name': 'Venta', 'price_unit': amount,
                                                 'tax_ids': [Command.clear()]})],
        })
        move.action_post()
        return move

    def _pay(self, invoice, amount=None, day=None):
        vals = {'journal_id': self.bank.id, 'payment_date': day or self.today}
        if amount is not None:
            vals['amount'] = amount
        return self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids).create(vals)._create_payments()

    @staticmethod
    def _receivable(move):
        return move.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')

    def _promise(self, amount, date, lines=None, partner=None):
        return self.env['l10n_pe.collection.promise'].create({
            'partner_id': (partner or self.customer).id, 'user_id': self.collector.id, 'date': date,
            'amount': amount, 'line_ids': [Command.set(lines.ids)] if lines else [],
        })
