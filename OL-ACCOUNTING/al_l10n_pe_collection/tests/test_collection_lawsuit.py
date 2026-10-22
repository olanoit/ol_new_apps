from datetime import timedelta

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import CollectionCommon


@tagged('post_install', '-at_install')
class TestCollectionLawsuit(CollectionCommon):
    """Cobranza judicial: etapas, seguimiento, provisión, castigo y acceso."""

    def _lawsuit(self, invoices, **vals):
        values = {'partner_id': self.customer.id, 'user_id': self.collector.id, 'court': '3.er Juzgado Civil de Lima',
                  'file_number': '01234-2026-0-1801-JR-CI-03',
                  'line_ids': [Command.set(invoices.line_ids.filtered(
                      lambda l: l.account_id.account_type == 'asset_receivable').ids)]}
        values.update(vals)
        return self.env['l10n_pe.collection.lawsuit'].create(values)

    def _journal(self):
        return self.env['account.journal'].create({'name': 'Provisiones (judicial)', 'code': 'TPJU', 'type': 'general'})

    def test_stages_and_followup(self):
        invoice = self._invoice(5000, -60)
        receivable = self._receivable(invoice)
        lawsuit = self._lawsuit(invoice)
        self.assertFalse(receivable.no_followup, 'En preparación sigue en el seguimiento.')
        lawsuit.action_conciliation()
        self.assertEqual(lawsuit.date_conciliation, self.today)
        lawsuit.action_file()
        self.assertEqual((lawsuit.state, lawsuit.date_filed, lawsuit.amount_claimed), ('filed', self.today, 5000.0))
        self.assertTrue(receivable.no_followup and receivable.l10n_pe_collection_in_lawsuit)
        with self.assertRaises(UserError):
            lawsuit.unlink()
        with self.assertRaises(UserError):
            lawsuit.action_enforce()
        lawsuit.action_admit()
        lawsuit.action_enforce()
        self._pay(invoice, amount=2000)
        self.assertEqual(lawsuit.amount_recovered, 2000.0)
        self.env['l10n_pe.collection.lawsuit.close'].create({'lawsuit_id': lawsuit.id, 'result': 'settled'}).action_close()
        self.assertEqual((lawsuit.state, lawsuit.result), ('closed', 'settled'))
        self.assertFalse(receivable.no_followup, 'Concluido, el saldo vuelve al seguimiento.')
        with self.assertRaises(UserError):
            lawsuit.with_user(self.collector).action_reopen()

    def test_filing_needs_court_and_own_documents(self):
        invoice = self._invoice(800, -30)
        with self.assertRaises(ValidationError):
            self._lawsuit(invoice, partner_id=self.other_customer.id)
        lawsuit = self._lawsuit(invoice, court=False)
        with self.assertRaises(UserError):
            lawsuit.action_file()

    def test_deadline_schedules_activity(self):
        lawsuit = self._lawsuit(self._invoice(800, -30))
        event = self.env['l10n_pe.collection.lawsuit.event'].create({
            'lawsuit_id': lawsuit.id, 'event_type': 'notification', 'name': 'Contestar la contradicción',
            'date_deadline': self.today + timedelta(days=5)})
        self.assertEqual(event.activity_id.user_id, self.collector)
        self.assertEqual(lawsuit.next_deadline, self.today + timedelta(days=5))
        event.done = True
        self.assertFalse(lawsuit.next_deadline)
        self.assertFalse(lawsuit.activity_ids)

    def test_lawsuit_supports_provision_before_twelve_months(self):
        """Art. 21 f): la cobranza judicial acredita la morosidad sin esperar 12 meses."""
        invoice = self._invoice(3000, -90)
        provision = self.env['l10n_pe.collection.provision'].create({'journal_id': self._journal().id})
        provision.action_load()
        self.assertNotIn(invoice, provision.line_ids.move_id)
        lawsuit = self._lawsuit(invoice)
        lawsuit.action_file()
        provision.action_load()
        line = provision.line_ids.filtered(lambda l: l.move_id == invoice)
        self.assertTrue(line.judicial and line.selected and line.supported)
        self.assertFalse(line.judicial_exhausted)

    def test_uncollectible_allows_write_off_over_three_uit(self):
        self.company.l10n_pe_collection_uit = 100.0
        invoice = self._invoice(1000, -60)
        lawsuit = self._lawsuit(invoice)
        lawsuit.action_file()
        provision = self.env['l10n_pe.collection.provision'].create({'journal_id': self._journal().id})
        provision.action_load()
        provision.line_ids.filtered(lambda l: l.move_id != invoice).selected = False
        provision.action_post()
        line = provision.line_ids.filtered(lambda l: l.move_id == invoice)
        self.assertFalse(line.write_off_allowed, '1000 > 3 UIT de 100 sin acciones agotadas.')
        wizard = self.env['l10n_pe.collection.lawsuit.close'].create({'lawsuit_id': lawsuit.id,
                                                                     'result': 'uncollectible'})
        with self.assertRaises(UserError):
            wizard.action_close()
        wizard.note = 'Embargo sin resultado: el deudor no tiene bienes registrados (SUNARP).'
        wizard.action_close()
        self.assertTrue(line.judicial_exhausted and line.write_off_allowed)
        line.action_write_off()
        self.assertTrue(self._receivable(invoice).reconciled)

    def test_file_report_includes_lawsuit(self):
        lawsuit = self._lawsuit(self._invoice(800, -30))
        lawsuit.action_file()
        self.env['l10n_pe.collection.lawsuit.event'].create({
            'lawsuit_id': lawsuit.id, 'event_type': 'resolution', 'name': 'Mandato ejecutivo'})
        html = self.env['ir.actions.report']._render_qweb_html(
            'al_l10n_pe_collection.report_collection_file', self.customer.ids)[0].decode()
        self.assertIn('Cobranza judicial', html)
        self.assertIn('Mandato ejecutivo', html)
        self.assertEqual(self.customer.l10n_pe_collection_lawsuit_count, 1)

    def test_access_collector_and_agency(self):
        own = self._lawsuit(self._invoice(800, -30))
        other = self._lawsuit(self._invoice(900, -30, partner=self.other_customer),
                              partner_id=self.other_customer.id, user_id=self.other_collector.id)
        Lawsuit = self.env['l10n_pe.collection.lawsuit'].with_user(self.collector)
        self.assertEqual(Lawsuit.search([('id', 'in', (own | other).ids)]), own)
        agency_user = self.env['res.users'].create({
            'name': 'Abogada Externa', 'login': 'abogada_externa', 'email': 'abogada@example.com',
            'group_ids': [Command.set([self.env.ref('base.group_user').id])],
            'company_id': self.company.id, 'company_ids': [Command.set(self.company.ids)]})
        agency = self.env['l10n_pe.collection.agency'].create({
            'name': 'Estudio Legal', 'user_ids': [Command.set(agency_user.ids)],
            'partner_id': self.env['res.partner'].create({'name': 'Estudio Legal SAC'}).id})
        with self.assertRaises(ValidationError):
            own.agency_id = agency
        self.env['l10n_pe.collection.agency.assignment'].create({'agency_id': agency.id, 'partner_id': self.customer.id})
        own.agency_id = agency
        as_agency = own.with_user(agency_user)
        as_agency.read(['name', 'line_ids', 'amount_residual'])
        as_agency.event_ids = [Command.create({'event_type': 'filing', 'name': 'Demanda ejecutiva'})]
        as_agency.action_file()
        self.assertEqual(own.state, 'filed')
        with self.assertRaises(AccessError):
            other.with_user(agency_user).read(['name'])
