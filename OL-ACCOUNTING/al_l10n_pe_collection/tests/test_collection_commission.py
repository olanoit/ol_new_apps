from datetime import timedelta

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import CollectionCommon


@tagged('post_install', '-at_install')
class TestCollectionCommission(CollectionCommon):
    """Comisiones de gestores y agencias externas de cobranza."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.plan = cls.env['l10n_pe.collection.commission.plan'].create({
            'name': 'Plan prueba', 'line_ids': [
                Command.create({'days_from': 1, 'days_to': 30, 'rate': 1.0}),
                Command.create({'days_from': 31, 'days_to': 90, 'rate': 3.0}),
                Command.create({'days_from': 91, 'days_to': 0, 'rate': 10.0}),
            ]})
        cls.company.l10n_pe_collection_commission_plan_id = cls.plan
        cls.agency_user = cls.env['res.users'].create({
            'name': 'Agente Externo', 'login': 'agente_externo', 'email': 'agente@example.com',
            'group_ids': [Command.set([cls.env.ref('base.group_user').id])],
            'company_id': cls.company.id, 'company_ids': [Command.set(cls.company.ids)],
        })
        cls.agency_partner = cls.env['res.partner'].create({'name': 'Estudio Recupera SAC', 'is_company': True})
        cls.agency = cls.env['l10n_pe.collection.agency'].create({
            'name': 'Estudio Recupera', 'partner_id': cls.agency_partner.id, 'plan_id': cls.plan.id,
            'user_ids': [Command.set(cls.agency_user.ids)],
        })

    def _assign(self, partner, days_ago=10, date_to=None):
        return self.env['l10n_pe.collection.agency.assignment'].create({
            'agency_id': self.agency.id, 'partner_id': partner.id,
            'date_from': self.today - timedelta(days=days_ago), 'date_to': date_to})

    def _commission(self, **vals):
        values = {'beneficiary': 'user', 'user_id': self.collector.id,
                  'date_from': self.today - timedelta(days=5), 'date_to': self.today}
        values.update(vals)
        commission = self.env['l10n_pe.collection.commission'].create(values)
        commission.action_compute()
        return commission

    # ------------------------------------------------------------------ plan
    def test_plan_scale_and_overlap(self):
        self.assertEqual(self.plan._rate_for_days(0), 0.0, 'Lo cobrado antes de vencer no comisiona.')
        self.assertEqual(self.plan._rate_for_days(30), 1.0)
        self.assertEqual(self.plan._rate_for_days(45), 3.0)
        self.assertEqual(self.plan._rate_for_days(800), 10.0)
        with self.assertRaises(ValidationError):
            self.plan.line_ids = [Command.create({'days_from': 60, 'days_to': 120, 'rate': 5.0})]
        default = self.env.ref('al_l10n_pe_collection.commission_plan_default')
        self.assertEqual(default._rate_for_days(400), 15.0)

    # ------------------------------------------------------------------ gestor
    def test_collector_commission_by_debt_age(self):
        late = self._invoice(1000, -45)
        on_time = self._invoice(500, 10)
        other = self._invoice(800, -100, partner=self.other_customer)
        for invoice in late | on_time | other:
            self._pay(invoice)
        commission = self._commission()
        self.assertEqual(commission.plan_id, self.plan, 'Propone el plan de los gestores de Ajustes.')
        self.assertEqual(commission.line_ids.move_id, late | on_time, 'Solo los clientes de la gestora.')
        line = commission.line_ids.filtered(lambda l: l.move_id == late)
        self.assertEqual((line.days_overdue, line.rate, line.commission_amount), (45, 3.0, 30.0))
        self.assertEqual(commission.amount_recovered, 1500.0)
        self.assertEqual(commission.amount_commission, 30.0)
        commission.action_confirm()
        again = self._commission()
        self.assertFalse(again.line_ids, 'Un cobro comisiona una sola vez.')

    def test_partial_payment_and_period(self):
        invoice = self._invoice(1000, -100)
        self._pay(invoice, amount=400, day=self.today - timedelta(days=20))
        self._pay(invoice, amount=600)
        commission = self._commission()
        self.assertEqual(commission.amount_recovered, 600.0, 'Solo lo cobrado dentro del periodo.')
        self.assertEqual(commission.amount_commission, 60.0)

    # ------------------------------------------------------------------ agencia
    def test_agency_commission_and_collector_exclusion(self):
        before = self._invoice(300, -60)
        self._pay(before, day=self.today - timedelta(days=15))
        self._assign(self.customer, days_ago=10)
        invoice = self._invoice(2000, -120)
        self._pay(invoice)
        agency_commission = self._commission(beneficiary='agency', agency_id=self.agency.id,
                                             date_from=self.today - timedelta(days=30))
        self.assertEqual(agency_commission.line_ids.move_id, invoice,
                         'Solo lo cobrado mientras el cliente estaba en la agencia.')
        self.assertEqual(agency_commission.amount_commission, 200.0)
        collector_commission = self._commission(date_from=self.today - timedelta(days=30))
        self.assertEqual(collector_commission.line_ids.move_id, before,
                         'Al gestor no le cuenta lo cobrado por la agencia.')

    def test_assignment_amounts_and_uniqueness(self):
        self._invoice(700, -40)
        assignment = self._assign(self.customer)
        self.assertEqual(assignment.amount_assigned, 700.0)
        self.assertEqual(self.customer.l10n_pe_collection_agency_id, self.agency)
        self.assertEqual(self.agency.partner_count, 1)
        self.assertEqual(self.agency.portfolio_amount, 700.0)
        other_agency = self.agency.copy({'name': 'Otra agencia', 'user_ids': []})
        wizard = self.env['l10n_pe.collection.agency.assign'].create({
            'agency_id': other_agency.id, 'partner_ids': [Command.set(self.customer.ids)]})
        with self.assertRaises(UserError):
            wizard.action_assign()
        wizard.replace = True
        wizard.action_assign()
        self.assertEqual(assignment.state, 'ended')
        self.assertEqual(assignment.date_to, self.today)
        self.assertEqual(self.customer.l10n_pe_collection_agency_id, other_agency)
        with self.assertRaises(UserError):
            other_agency.assignment_ids.unlink()

    def test_cron_ends_expired_assignments(self):
        assignment = self._assign(self.customer, days_ago=40, date_to=self.today - timedelta(days=1))
        self.env['l10n_pe.collection.agency.assignment']._cron_end_assignments()
        self.assertEqual(assignment.state, 'ended')
        self.assertEqual(assignment.date_to, self.today - timedelta(days=1), 'Conserva el fin pactado.')
        self.assertFalse(self.customer.l10n_pe_collection_agency_id)

    # ------------------------------------------------------------------ reversión y factura
    def test_reversed_payment_is_clawed_back(self):
        self._assign(self.customer, days_ago=10)
        invoice = self._invoice(1000, -100)
        payment = self._pay(invoice)
        first = self._commission(beneficiary='agency', agency_id=self.agency.id)
        first.action_confirm()
        payment.move_id.line_ids.remove_move_reconcile()
        self.assertTrue(first.line_ids.reversed)
        second = self._commission(beneficiary='agency', agency_id=self.agency.id)
        clawback = second.line_ids.filtered(lambda l: l.line_type == 'clawback')
        self.assertEqual(clawback.origin_line_id, first.line_ids)
        self.assertEqual(second.amount_commission, -100.0)
        second.action_confirm()
        third = self._commission(beneficiary='agency', agency_id=self.agency.id)
        self.assertFalse(third.line_ids, 'El descuento se aplica una sola vez.')

    def test_agency_bill(self):
        self._assign(self.customer, days_ago=10)
        self._pay(self._invoice(1000, -45))
        commission = self._commission(beneficiary='agency', agency_id=self.agency.id)
        commission.action_confirm()
        self.company.l10n_pe_collection_commission_product_id = False
        with self.assertRaises(UserError):
            commission.action_create_bill()
        self.company.l10n_pe_collection_commission_product_id = self.env['product.product'].create({
            'name': 'Servicio de cobranza', 'type': 'service', 'supplier_taxes_id': [Command.clear()]})
        commission.action_create_bill()
        bill = commission.invoice_id
        self.assertEqual((bill.move_type, bill.state, bill.partner_id), ('in_invoice', 'draft', self.agency_partner))
        self.assertEqual(bill.amount_untaxed, 30.0)
        self.assertEqual(commission.state, 'billed')
        with self.assertRaises(UserError):
            commission.action_cancel()
        bill.button_cancel()
        commission.action_cancel()
        self.assertEqual(commission.state, 'cancel')

    # ------------------------------------------------------------------ acceso
    def test_agency_user_sees_only_assigned_customers(self):
        group = self.env.ref('al_l10n_pe_collection.group_collection_agency')
        self.assertIn(group, self.agency_user.group_ids, 'El usuario de la agencia recibe su grupo.')
        mine = self._invoice(500, -40)
        theirs = self._invoice(900, -40, partner=self.other_customer)
        self._assign(self.customer)
        Move = self.env['account.move'].with_user(self.agency_user)
        self.assertEqual(Move.search([('id', 'in', (mine | theirs).ids)]), mine)
        with self.assertRaises(AccessError):
            theirs.with_user(self.agency_user).read(['name'])
        portfolio = self.env['l10n_pe.collection.portfolio'].with_user(self.agency_user).search([])
        self.assertEqual(portfolio.partner_id, self.customer)
        Action = self.env['l10n_pe.collection.action'].with_user(self.agency_user)
        action = Action.create({'partner_id': self.customer.id, 'result_id': self.result_no_answer.id,
                                'channel': 'email'})
        self.assertEqual(action.user_id, self.agency_user)
        with self.assertRaises(AccessError):
            Action.create({'partner_id': self.other_customer.id, 'result_id': self.result_no_answer.id,
                           'channel': 'email'})
        worklist = self.env['res.partner'].with_user(self.agency_user).action_l10n_pe_collection_worklist()
        self.assertIn(('l10n_pe_collection_agency_id.user_ids', 'in', [self.agency_user.id]), worklist['domain'])
        self.agency.user_ids = [Command.clear()]
        self.assertNotIn(group, self.agency_user.group_ids, 'Sin agencia, pierde el grupo.')

    def test_collector_sees_only_own_commissions(self):
        self._pay(self._invoice(1000, -45))
        own = self._commission()
        other = self._commission(user_id=self.other_collector.id)
        Commission = self.env['l10n_pe.collection.commission'].with_user(self.collector)
        self.assertEqual(Commission.search([('id', 'in', (own | other).ids)]), own)
        with self.assertRaises(AccessError):
            own.with_user(self.collector).action_compute()
