# -*- coding: utf-8 -*-
"""Caja chica del residente locador en el portal (paquete 6, CR-55, P11).
Datos ficticios."""
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.al_construction_portal.tests.test_portal_service import PHOTOS
from odoo.addons.al_construction_portal.tests.test_resident import ResidentCommon


@tagged('post_install', '-at_install')
class TestPortalCash(ResidentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Account = env['account.account']
        if not cls.company._l10n_pe_cash_fund_account('petty_cash'):
            account = Account.create({'code': '1413098', 'name': 'Caja chica de obra (p6)',
                                      'account_type': 'asset_receivable', 'reconcile': True})
            cls.company.write({'l10n_pe_cash_advance_account_id': account.id})
        bank = env['account.journal'].search([
            *env['account.journal']._check_company_domain(cls.company), ('type', '=', 'bank')],
            limit=1)
        # El fondo es del contacto del residente: es locador, sin ficha de empleado.
        cls.fund = env['l10n_pe.cash.fund'].create({
            'fund_type': 'advance', 'partner_id': cls.resident_user.partner_id.id,
            'purpose': 'Gastos menores de obra (p6)', 'amount': 500.0, 'journal_id': bank.id,
            'company_id': cls.company.id})
        cls.fund.state = 'open'
        cls.doc_type = env['l10n_latam.document.type'].search([
            ('code', '=', '03'), ('country_id.code', '=', 'PE')], limit=1)

    def _expense(self, uuid, number, amount, **extra):
        values = dict({'uuid': uuid, 'project_id': self.project.id, 'fund_id': self.fund.id,
                       'doc_type_id': self.doc_type.id, 'ruc': '20100070970', 'number': number,
                       'amount': amount, 'photos': PHOTOS, 'description': 'Clavos y alambre'},
                      **extra)
        return self._service(self.resident_user).expense(values)

    def test_receipt_and_settlement(self):
        service = self._service(self.resident_user)
        cash = service.sync(self.project.id)['resident']['cash']
        self.assertEqual([f['id'] for f in cash['funds']], [self.fund.id])
        self.assertTrue(cash['doc_types'])
        with self.assertRaisesRegex(UserError, '11 dígitos'):
            self._expense('p6-cj-0', 'B001-1', 45.0, ruc='123')
        first = self.env['account.move'].browse(int(
            self._expense('p6-cj-1', 'B001-101', 45.0, task_id=self.wall.task_id.id)['ids']))
        self.assertEqual((first.state, first.move_type, first.amount_total),
                         ('draft', 'in_invoice', 45.0))
        self.assertEqual(first.construction_portal_fund_id, self.fund)
        self.assertEqual(first.construction_portal_task_id, self.wall.task_id)
        self.assertEqual(first.create_uid, self.resident_user)
        self.assertTrue(first.attachment_ids)
        self.assertEqual(first.partner_id.vat, '20100070970')
        with self.assertRaisesRegex(UserError, 'ya está registrado'):
            self._expense('p6-cj-2', 'B001-101', 45.0)
        second = self.env['account.move'].browse(int(
            self._expense('p6-cj-3', 'B001-102', 30.0)['ids']))
        fund = next(f for f in service.sync(self.project.id)['resident']['cash']['funds']
                    if f['id'] == self.fund.id)
        self.assertEqual({r['state'] for r in fund['receipts']}, {'registered'})
        # Rendir los dos: rendición en borrador con sus comprobantes.
        result = service.settle({'uuid': 'p6-cj-4', 'project_id': self.project.id,
                                 'fund_id': self.fund.id, 'receipt_ids': [first.id, second.id]})
        settlement = self.env['l10n_pe.cash.settlement'].browse(int(result['ids']))
        self.assertEqual(settlement.state, 'draft')
        self.assertEqual(settlement.document_line_ids.move_id, first | second)
        self.assertAlmostEqual(settlement.amount_total, 75.0)
        fund = next(f for f in service.sync(self.project.id)['resident']['cash']['funds']
                    if f['id'] == self.fund.id)
        self.assertAlmostEqual(fund['sent'], 75.0)
        self.assertEqual({r['state'] for r in fund['receipts']}, {'sent'})
        with self.assertRaisesRegex(UserError, 'Ya se rindieron'):
            service.settle({'uuid': 'p6-cj-5', 'project_id': self.project.id,
                            'fund_id': self.fund.id, 'receipt_ids': [first.id]})
        # Contabilidad publica los comprobantes y confirma la rendición en el
        # escritorio: queda aprobado y baja el saldo por rendir (P11).
        (first | second).action_post()
        settlement.action_post()
        self.assertEqual(settlement.state, 'posted')
        self.assertEqual(set((first | second).mapped('payment_state')) - {'in_payment'}, {'paid'})
        fund = next(f for f in service.sync(self.project.id)['resident']['cash']['funds']
                    if f['id'] == self.fund.id)
        self.assertAlmostEqual(fund['approved'], 75.0)
        self.assertEqual({r['state'] for r in fund['receipts']}, {'approved'})

    def test_fund_of_another_person(self):
        other = self.env['l10n_pe.cash.fund'].create({
            'fund_type': 'advance', 'partner_id': self.foreman_user.partner_id.id,
            'purpose': 'Otro fondo (p6)', 'amount': 100.0, 'journal_id': self.fund.journal_id.id,
            'company_id': self.company.id})
        other.state = 'open'
        with self.assertRaises(AccessError):
            self._expense('p6-cj-6', 'B001-200', 10.0, fund_id=other.id)
