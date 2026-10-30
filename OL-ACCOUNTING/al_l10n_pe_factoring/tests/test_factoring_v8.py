# -*- coding: utf-8 -*-
"""Versión 8: contrato y simulación, línea de crédito, revisión previa,
factura negociable (conformidad presunta, eventos y orden), desembolso
parcial, cobro recibido por la empresa y transferencia, prórroga,
notificación, archivo para el factor y CAVALI (servicios web, Factrack e
importación de estados)."""
import io
import json
import zipfile
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import BinaryBytes

from .common import FactoringCommon

CAVALI_POST = 'odoo.addons.al_l10n_pe_factoring.models.cavali.requests.post'


class FakeResponse:
    def __init__(self, data, status=200):
        self._data, self.status_code = data, status
        self.text = json.dumps(data)

    def json(self):
        return self._data


@tagged('post_install', '-at_install')
class TestFactoringV8(FactoringCommon):

    # ------------------------------------------------------------------
    # Ayudantes
    # ------------------------------------------------------------------
    def _invoice(self, amount=1000.0, days=60, invoice_date=None, name=None, partner=None):
        invoice_date = invoice_date or self.today
        vals = {
            'move_type': 'out_invoice', 'partner_id': (partner or self.customer).id,
            'journal_id': self.sale_journal.id, 'invoice_date': invoice_date,
            'invoice_date_due': invoice_date + timedelta(days=days),
            'invoice_line_ids': [(0, 0, {
                'name': 'Servicio', 'quantity': 1, 'price_unit': amount,
                'account_id': self.income.id, 'tax_ids': [(6, 0, [])]})],
        }
        if name:
            vals['name'] = name
        move = self.env['account.move'].create(vals)
        move.action_post()
        return move

    def _contract(self, **vals):
        return self.env['l10n_pe.factoring.contract'].create(dict({
            'name': 'Línea test', 'factor_id': self.factor.id, 'modality': 'without_recourse',
            'advance_percent': 90.0, 'annual_rate': 12.0, 'fee_percent': 0.5, 'fee_min': 50.0,
            'expense_fixed': 10.0, 'fee_with_igv': True, 'date_start': self.today - timedelta(days=30),
        }, **vals))

    def _contract_operation(self, contract, invoices):
        operation = self._operation(invoices, modality=contract.modality, percent=contract.advance_percent)
        operation.contract_id = contract
        return operation

    def _register(self, invoice, accept=True):
        if accept:
            invoice._l10n_pe_add_negotiable_event('accepted')
        invoice._l10n_pe_add_negotiable_event('registered', reference='AN-%s' % invoice.id)

    # ------------------------------------------------------------------
    # 1-2. Contrato, simulación y línea de crédito
    # ------------------------------------------------------------------
    def test_contract_simulation(self):
        contract = self._contract()
        invoice = self._invoice(1000.0, days=60)
        operation = self._contract_operation(contract, invoice)
        operation.action_simulate()
        interest = round(900.0 * ((1.12) ** (60 / 360.0) - 1), 2)
        self.assertEqual(operation.line_ids.estimated_days, 60)
        self.assertAlmostEqual(operation.estimated_interest, interest, places=2)
        self.assertEqual(operation.estimated_fee, 50.0, 'comisión mínima por factura')
        self.assertEqual(operation.estimated_fee_igv, 9.0)
        self.assertEqual(operation.estimated_expense, 10.0)
        self.assertAlmostEqual(operation.estimated_net, 900.0 - interest - 50.0 - 9.0 - 10.0, places=2)
        operation.action_assign()
        wizard = self.env['l10n_pe.factoring.wizard'].create({
            'factoring_id': operation.id, 'operation': 'disburse', 'date': self.today,
            'bank_journal_id': self.bank_journal.id, 'interest_amount': interest,
            'fee_amount': 59.0, 'expense_amount': 12.0})
        self.assertAlmostEqual(wizard.estimated_charges, interest + 59.0 + 10.0, places=2)
        self.assertAlmostEqual(wizard.estimate_difference, 2.0, places=2, msg='gastos reales mayores')

    def test_credit_and_debtor_limits(self):
        contract = self._contract(advance_percent=100.0, credit_limit=1500.0, debtor_limit=1000.0)
        first = self._contract_operation(contract, self._invoice(800.0))
        first.action_assign()
        self.assertEqual(contract.used_amount, 800.0)
        self.assertEqual(contract.available_amount, 700.0)
        second = self._contract_operation(contract, self._invoice(500.0))
        with self.assertRaisesRegex(UserError, 'límite por cliente'):
            second.action_assign()
        contract.debtor_limit = 0.0
        second.action_assign()
        other = self.env['res.partner'].create({'name': 'OTRO CLIENTE SAC', 'vat': '20100113610'})
        third = self._contract_operation(contract, self._invoice(300.0, partner=other))
        with self.assertRaisesRegex(UserError, 'línea'):
            third.action_assign()

    # ------------------------------------------------------------------
    # 3. Revisión previa
    # ------------------------------------------------------------------
    def test_eligibility_review_lists_all_reasons(self):
        good = self._invoice(400.0)
        rejected = self._invoice(500.0)
        rejected._l10n_pe_add_negotiable_event('rejected', note='Precio errado')
        overdue = self._invoice(600.0, days=5, invoice_date=self.today - timedelta(days=30))
        action = (good + rejected + overdue).action_l10n_pe_factoring_create()
        review = self.env['l10n_pe.factoring.eligibility'].browse(action['res_id'])
        self.assertEqual((review.eligible_count, review.excluded_count), (1, 2))
        reasons = dict((line.move_id, line.errors or '') for line in review.line_ids)
        self.assertIn('disconformidad', reasons[rejected])
        self.assertIn('venció', reasons[overdue])
        operation = self.env['l10n_pe.factoring'].browse(review.action_create_operation()['res_id'])
        self.assertEqual(operation.line_ids.move_id, good)

    def test_assign_collects_all_errors(self):
        operation = self._operation(self._invoice(100.0) + self._invoice(200.0))
        operation.line_ids[0].nominal_amount = 999.0
        operation.line_ids[1].move_id._l10n_pe_add_negotiable_event('rejected')
        with self.assertRaises(UserError) as error:
            operation.action_assign()
        self.assertIn('supera su saldo', str(error.exception))
        self.assertIn('disconformidad', str(error.exception))

    # ------------------------------------------------------------------
    # 4-5. Conformidad presunta y eventos de la factura negociable
    # ------------------------------------------------------------------
    def test_presumed_conformity_cron(self):
        old = self._invoice(invoice_date=self.today - timedelta(days=10))
        soon = self._invoice(invoice_date=self.today - timedelta(days=7))
        cash = self._invoice(days=0, invoice_date=self.today - timedelta(days=10))
        self.env['account.move']._cron_l10n_pe_presumed_conformity()
        self.assertEqual(old.l10n_pe_conformity_state, 'presumed')
        self.assertEqual(old.l10n_pe_conformity_date, old.invoice_date + timedelta(days=8))
        self.assertEqual(old.l10n_pe_negotiable_event_ids.event_type, 'presumed')
        self.assertEqual(old.l10n_pe_negotiable_event_ids.source, 'cron')
        self.assertEqual(soon.l10n_pe_conformity_state, 'pending')
        self.assertTrue(soon.activity_ids, 'aviso del plazo que vence')
        self.assertEqual(cash.l10n_pe_conformity_state, 'pending', 'al contado no aplica')

    def test_negotiable_event_order(self):
        invoice = self._invoice()
        with self.assertRaises(UserError, msg='no se transfiere sin anotación'):
            invoice._l10n_pe_add_negotiable_event('transferred', partner=self.factor)
        invoice._l10n_pe_add_negotiable_event('registered', reference='AN-1')
        self.assertEqual(invoice.l10n_pe_negotiable_state, 'registered')
        self.assertEqual(invoice.l10n_pe_negotiable_holder_id, self.company.partner_id)
        with self.assertRaises(UserError, msg='no se transfiere sin conformidad'):
            invoice._l10n_pe_add_negotiable_event('transferred', partner=self.factor)
        wizard = self.env['l10n_pe.negotiable.event.wizard'].create({
            'move_ids': [(6, 0, invoice.ids)], 'event_type': 'accepted'})
        wizard.action_apply()
        invoice._l10n_pe_add_negotiable_event('transferred', partner=self.factor)
        self.assertEqual(invoice.l10n_pe_negotiable_holder_id, self.factor)
        invoice._l10n_pe_add_negotiable_event('paid', amount=1000.0)
        with self.assertRaises(UserError, msg='pagada, no admite prórroga'):
            invoice._l10n_pe_add_negotiable_event('extended', due_date=self.today + timedelta(days=90))
        cash = self._invoice(days=0)
        with self.assertRaisesRegex(UserError, 'al contado'):
            cash._l10n_pe_add_negotiable_event('registered')

    def test_assign_transfers_registered_invoice(self):
        invoice = self._invoice()
        self._register(invoice)
        operation = self._operation(invoice)
        operation.action_assign()
        self.assertEqual(invoice.l10n_pe_negotiable_state, 'transferred')
        self.assertEqual(invoice.l10n_pe_negotiable_holder_id, self.factor)
        event = invoice.l10n_pe_negotiable_event_ids.filtered(lambda e: e.event_type == 'transferred')
        self.assertEqual((event.source, event.reference), ('factoring', operation.name))
        operation.action_cancel()
        self.assertEqual(invoice.l10n_pe_negotiable_state, 'registered', 'la cancelación revierte')
        self.assertEqual(invoice.l10n_pe_negotiable_holder_id, self.company.partner_id)

    def test_contract_requires_cavali(self):
        contract = self._contract(require_cavali=True)
        invoice = self._invoice()
        operation = self._contract_operation(contract, invoice)
        with self.assertRaisesRegex(UserError, 'CAVALI'):
            operation.action_assign()
        self._register(invoice)
        operation.action_assign()

    # ------------------------------------------------------------------
    # 7. Cobro recibido por la empresa y transferencia al factor
    # ------------------------------------------------------------------
    def test_company_collect_without_recourse(self):
        invoice = self._invoice(1000.0)
        operation = self._operation(invoice, percent=90.0)
        operation.action_assign()
        self._wizard(operation, 'disburse')
        config = operation._config()
        self._wizard(operation, 'company_collect')
        line = operation.line_ids
        self.assertEqual(line.state, 'collected')
        self.assertEqual(line.company_collected_amount, 1000.0)
        self.assertEqual(operation.transfer_pending_amount, 900.0)
        self.assertEqual(operation.state, 'disbursed', 'falta transferir al factor')
        self.assertEqual(self._balance(operation, config.transfer_account_id), -900.0)
        self.assertEqual(self._balance(operation, config.assigned_account_id), 0.0, 'retenido de la empresa')
        self._wizard(operation, 'transfer')
        self.assertEqual(operation.state, 'done')
        self.assertEqual(self._balance(operation, config.transfer_account_id), 0.0)
        self.assertTrue(operation.move_ids.line_ids.filtered(
            lambda l: l.account_id == config.transfer_account_id).mapped('reconciled')[0])
        self._assert_balanced(operation)

    def test_company_collect_with_recourse(self):
        invoice = self._invoice(1000.0)
        operation = self._operation(invoice, modality='with_recourse', percent=80.0)
        operation.action_assign()
        self._wizard(operation, 'disburse')
        config = operation._config()
        self._wizard(operation, 'company_collect')
        self.assertEqual(invoice.payment_state, 'paid')
        self.assertEqual(operation.transfer_pending_amount, 800.0)
        self.assertEqual(self._balance(operation, config.obligation_account_id), -800.0)
        self._wizard(operation, 'transfer')
        self.assertEqual(self._balance(operation, config.obligation_account_id), 0.0)
        self.assertEqual(operation.state, 'done')
        self._assert_balanced(operation)

    # ------------------------------------------------------------------
    # 8. Prórroga
    # ------------------------------------------------------------------
    def test_extension(self):
        contract = self._contract()
        invoice = self._invoice(1000.0, days=30)
        self._register(invoice)
        operation = self._contract_operation(contract, invoice)
        operation.action_assign()
        self._wizard(operation, 'disburse', interest_amount=10.0)
        new_due = invoice.invoice_date_due + timedelta(days=30)
        wizard = self.env['l10n_pe.factoring.wizard'].create({
            'factoring_id': operation.id, 'operation': 'extend', 'date': self.today,
            'bank_journal_id': self.bank_journal.id, 'new_due_date': new_due})
        expected = contract._interest(900.0, 30)
        self.assertAlmostEqual(wizard.estimated_charges, expected, places=2)
        wizard.interest_amount = expected
        wizard.action_apply()
        self.assertEqual(operation.line_ids.due_date, new_due)
        self.assertEqual(invoice.l10n_pe_negotiable_due_date, new_due)
        self.assertIn('extended', invoice.l10n_pe_negotiable_event_ids.mapped('event_type'))
        self.assertAlmostEqual(operation.interest_amount, 10.0 + expected, places=2)
        with self.assertRaises(UserError, msg='la fecha debe ser posterior'):
            self._wizard(operation, 'extend', new_due_date=new_due)
        self._assert_balanced(operation)

    # ------------------------------------------------------------------
    # 10. Desembolso parcial
    # ------------------------------------------------------------------
    def test_partial_disbursement(self):
        first, second = self._invoice(300.0), self._invoice(700.0)
        operation = self._operation(first + second, percent=90.0)
        operation.action_assign()
        self._wizard(operation, 'disburse', line_ids=[(6, 0, operation.line_ids.filtered(
            lambda l: l.move_id == first).ids)])
        self.assertEqual(operation.state, 'disbursed')
        self.assertTrue(operation.has_undisbursed)
        self.assertEqual(operation.net_amount, 270.0)
        settle = self.env['l10n_pe.factoring.wizard'].create({
            'factoring_id': operation.id, 'operation': 'settle', 'date': self.today,
            'bank_journal_id': self.bank_journal.id})
        self.assertEqual(settle.line_ids.move_id, first, 'solo se cobran las desembolsadas')
        self._wizard(operation, 'disburse')
        self.assertFalse(operation.has_undisbursed)
        self.assertEqual(operation.net_amount, 900.0)
        self._wizard(operation, 'settle')
        self.assertEqual(operation.state, 'done')
        self._assert_balanced(operation)

    # ------------------------------------------------------------------
    # 6 y 9. Notificación al cliente y archivo para el factor
    # ------------------------------------------------------------------
    def test_notice_and_export_file(self):
        import openpyxl

        invoice = self._invoice()
        self._register(invoice)
        operation = self._operation(invoice)
        operation.action_assign()
        operation.action_send_notice()
        message = operation.message_ids.filtered(lambda m: self.customer in m.partner_ids)
        self.assertTrue(message)
        self.assertEqual(message[0].attachment_ids.mimetype, 'application/pdf')
        self.assertIn('notified', invoice.l10n_pe_negotiable_event_ids.mapped('event_type'))
        attachment = operation._export_attachment()
        book = openpyxl.load_workbook(io.BytesIO(attachment.raw.content))
        sheet = book.worksheets[0]
        self.assertEqual(sheet['B1'].value, operation.name)
        self.assertEqual(sheet['H5'].value, 1000.0)
        self.assertEqual(sheet['K5'].value, invoice.l10n_pe_cavali_number)

    # ------------------------------------------------------------------
    # CAVALI
    # ------------------------------------------------------------------
    def _enable_cavali(self):
        self.company.write({
            'l10n_pe_cavali_mode': 'webservice', 'l10n_pe_cavali_environment': 'test',
            'l10n_pe_cavali_url_test': 'https://cavali.test/api/', 'l10n_pe_cavali_user': 'usuario',
            'l10n_pe_cavali_password': 'clave', 'l10n_pe_cavali_rut': 'RUT1'})
        self.customer.street = 'Av. Javier Prado 123'
        self.company.partner_id.street = 'Av. Arequipa 456'

    def test_cavali_webservice_register_transfer_and_payment(self):
        self._enable_cavali()
        invoice = self._invoice(1000.0)
        ok = FakeResponse({'codigo': '0', 'mensaje': 'Correcto', 'codigoAnotacion': 'AN-77',
                           'estado': 'ANOTADA'})
        with patch(CAVALI_POST, return_value=ok) as post:
            invoice.action_l10n_pe_cavali_register()
        url, = post.call_args.args
        payload = post.call_args.kwargs['json']
        self.assertEqual(url, 'https://cavali.test/api/facturas/registro')
        self.assertEqual(payload['montoNetoPendiente'], 1000.0)
        self.assertEqual(payload['rucAdquirente'], self.customer.vat)
        self.assertEqual(len(payload['cuotas']), 1)
        self.assertEqual(post.call_args.kwargs['auth'], ('usuario', 'clave'))
        self.assertEqual((invoice.l10n_pe_negotiable_state, invoice.l10n_pe_cavali_number),
                         ('registered', 'AN-77'))
        log = invoice.l10n_pe_cavali_log_ids
        self.assertEqual((log.operation, log.state), ('register', 'ok'))
        self.assertNotIn('clave', log.request_body, 'las credenciales no quedan en el registro')
        invoice._l10n_pe_add_negotiable_event('accepted')
        operation = self._operation(invoice)
        with patch(CAVALI_POST, return_value=FakeResponse({'codigo': '0'})) as post:
            operation.action_assign()
        self.assertEqual(post.call_args.args[0], 'https://cavali.test/api/facturas/transferencia')
        self.assertEqual(invoice.l10n_pe_negotiable_state, 'transferred')
        self._wizard(operation, 'disburse')
        with patch(CAVALI_POST, return_value=FakeResponse({'codigo': '0'})) as post:
            self._wizard(operation, 'settle')
        self.assertEqual(post.call_args.kwargs['json']['montoPagado'], 1000.0)
        self.assertEqual(invoice.l10n_pe_negotiable_state, 'paid')

    def test_cavali_error_keeps_log(self):
        self._enable_cavali()
        invoice = self._invoice()
        with patch(CAVALI_POST, return_value=FakeResponse({'codigo': '45', 'mensaje': 'RUC no habido'}, 400)):
            with self.assertRaisesRegex(UserError, 'RUC no habido'):
                invoice.action_l10n_pe_cavali_register()
            # Odoo 20: assertRaises deshace lo hecho en su bloque; el registro
            # del envío fallido (que fuera de pruebas se guarda en otro
            # cursor) se comprueba con la llamada directa.
            log = self.env['l10n_pe.cavali.log']._call(
                invoice.company_id, 'register', invoice._l10n_pe_cavali_payload(), move=invoice)
        self.assertEqual(invoice.l10n_pe_negotiable_state, 'none')
        self.assertEqual((log.state, log.http_status), ('error', 400))

    def test_cavali_status_query(self):
        self._enable_cavali()
        invoice = self._invoice()
        self._register(invoice, accept=False)
        with patch(CAVALI_POST, return_value=FakeResponse({'codigo': '0', 'estado': 'Conformidad presunta'})):
            self.env['account.move']._cron_l10n_pe_cavali_status()
        self.assertEqual(invoice.l10n_pe_conformity_state, 'presumed')

    def test_cavali_missing_data(self):
        self._enable_cavali()
        self.customer.street = False
        with self.assertRaisesRegex(UserError, 'domicilio del cliente'):
            self._invoice().action_l10n_pe_cavali_register()

    def test_factrack_package_and_status_import(self):
        self.customer.street = 'Av. Javier Prado 123'
        self.company.partner_id.street = 'Av. Arequipa 456'
        invoice = self._invoice(1000.0, name='F001-00000123')
        invoice._l10n_pe_add_negotiable_event('accepted')
        attachment = invoice._l10n_pe_factrack_attachment()
        with zipfile.ZipFile(io.BytesIO(attachment.raw.content)) as archive:
            self.assertIn('informacion_adicional.xlsx', archive.namelist())
        content = 'Serie;Número;Estado;Fecha;Código anotación\nF001;123;Anotada;%s;AN-9\n' % (
            fields.Date.to_string(self.today))
        wizard = self.env['l10n_pe.cavali.import'].create({
            'file': BinaryBytes(content.encode()), 'filename': 'factrack.csv'})
        wizard.action_import()
        self.assertEqual((invoice.l10n_pe_negotiable_state, invoice.l10n_pe_cavali_number),
                         ('registered', 'AN-9'))
        self.assertIn('Actualizadas: 1', wizard.result)
        wizard2 = self.env['l10n_pe.cavali.import'].create({
            'file': BinaryBytes('Serie;Número;Estado\nF001;999;Anotada\n'.encode()),
            'filename': 'factrack.csv'})
        wizard2.action_import()
        self.assertIn('no encontrada', wizard2.result)
