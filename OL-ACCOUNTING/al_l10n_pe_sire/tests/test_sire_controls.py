"""Controles del SIRE: reglas al publicar, roles, bitácora de la API y avisos."""
import io
import zipfile
from datetime import timedelta
from unittest.mock import MagicMock, patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged
from odoo.tools import BinaryBytes

from odoo.addons.al_l10n_pe_sire.models.sire_validation import is_anonymous, months_between

from .test_sire import PERIOD_DATE, TestSire, _rvie_row


@tagged('post_install', '-at_install')
class TestSireControls(TestSire):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.accountant = new_test_user(
            cls.env, login='sire_preparer', groups='account.group_account_user',
            company_id=cls.company.id)
        cls.approver = new_test_user(
            cls.env, login='sire_approver', groups='al_l10n_pe_sire.group_sire_approver',
            company_id=cls.company.id)

    def _system_line(self, record, move):
        with patch.object(type(record), '_sire_system_moves', return_value=move):
            record.action_load_system()
        return record.system_line_ids.filtered(lambda l: l.move_id == move)

    # ------------------------------------------------------------------
    # Reglas nuevas del libro
    # ------------------------------------------------------------------

    def test_helpers(self):
        self.assertTrue(is_anonymous('0', '-'))
        self.assertTrue(is_anonymous('1', '00000000'))
        self.assertFalse(is_anonymous('1', '45678912'))
        self.assertEqual(months_between(fields.Date.to_date('2025-07-31'),
                                        fields.Date.to_date('2026-07-01')), 12)

    def test_boleta_over_limit_needs_the_customer(self):
        invoice = self._make_invoice('out_invoice')
        line = self._system_line(self.rvie, invoice)
        line.write({'tipo_cp': '03', 'serie_cp': 'B001',
                    'tipo_doc_identidad': '0', 'nro_doc_identidad': '-'})
        self.rvie.action_validate()
        self.assertIn('S/ 700.00', line.check_detail)

        line.write({'nro_final': '250'})
        self.rvie.action_validate()
        self.assertFalse(line.check_detail, 'un resumen de boletas no identifica clientes')

        line.write({'nro_final': False, 'tipo_doc_identidad': '1',
                    'nro_doc_identidad': '45678912'})
        self.rvie.action_validate()
        self.assertFalse(line.check_detail)

    def test_rce_late_purchase_is_a_warning(self):
        bill = self._make_invoice('in_invoice', document_number='F002-41')
        line = self._system_line(self.rce, bill)
        # Periodo 07/2026: junio de 2025 son 13 periodos; julio de 2025, 12.
        line.write({'fecha_emision': fields.Date.to_date('2025-07-20')})
        self.rce.action_validate()
        self.assertFalse(line.check_warning)
        line.write({'fecha_emision': fields.Date.to_date('2025-06-20')})
        self.rce.action_validate()
        self.assertIn('crédito fiscal', line.check_warning)
        self.assertFalse(line.check_detail, 'SUNAT la recibe: no bloquea el envío')
        self.assertEqual(self.rce.count_warning, 1)
        self.assertEqual(self.rce.count_invalid, 0)
        self.assertIn(line, self.rce.invalid_line_ids)

    def test_zipped_proposal_loads(self):
        content = '\n'.join(['CABECERA', _rvie_row()]).encode('utf-8')
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('LE2051252845820260700140400021112.txt', content)
        self.rvie.proposal_file = BinaryBytes(buffer.getvalue())
        self.rvie.action_load_sire()
        self.assertEqual(len(self.rvie.sire_line_ids), 1)

        empty = io.BytesIO()
        with zipfile.ZipFile(empty, 'w') as archive:
            archive.writestr('leame.pdf', b'x')
        self.rvie.proposal_file = BinaryBytes(empty.getvalue())
        with self.assertRaisesRegex(UserError, 'ningún TXT'):
            self.rvie.action_load_sire()

    # ------------------------------------------------------------------
    # Validación al publicar
    # ------------------------------------------------------------------

    def test_valid_documents_pass_on_post(self):
        """Sin falsos positivos: lo que el libro acepta, se publica en silencio."""
        invoice = self._make_invoice('out_invoice')
        bill = self._make_invoice('in_invoice', document_number='F002-42')
        for move in invoice | bill:
            with self.subTest(move=move.display_name):
                self.assertEqual(move._l10n_pe_sire_book_check(), ([], []))

    def _dni_bill(self, number):
        partner = self.env['res.partner'].create({
            'name': 'Proveedor con DNI',
            'additional_identifiers': {'PE_DNI': '45678912'},
            'country_id': self.env.ref('base.pe').id,
        })
        doc_type = self.env['l10n_latam.document.type'].search([
            ('code', '=', '01'), ('country_id.code', '=', 'PE')], limit=1)
        return self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': partner.id,
            'invoice_date': PERIOD_DATE,
            'l10n_latam_document_type_id': doc_type.id,
            'l10n_latam_document_number': number,
            'invoice_line_ids': [(0, 0, {
                'name': 'Servicio', 'quantity': 1, 'price_unit': 100.0,
                'tax_ids': [(6, 0, self._tax('purchase').ids)],
            })],
        })

    def test_post_check_block(self):
        self.company.l10n_pe_sire_post_check = 'block'
        bill = self._dni_bill('F002-43')
        with self.assertRaisesRegex(UserError, 'RUC del proveedor'):
            bill.action_post()

    def test_post_check_warn(self):
        self.company.l10n_pe_sire_post_check = 'warn'
        bill = self._dni_bill('F002-44')
        bill.action_post()
        self.assertEqual(bill.state, 'posted')
        self.assertTrue(any('RUC del proveedor' in message.body for message in bill.message_ids))

    def test_post_check_none(self):
        self.company.l10n_pe_sire_post_check = 'none'
        bill = self._dni_bill('F002-45')
        with patch.object(type(bill), '_l10n_pe_sire_book_check') as check:
            bill.action_post()
        check.assert_not_called()

    # ------------------------------------------------------------------
    # Compras: Tabla 30 y no domiciliados
    # ------------------------------------------------------------------

    def test_goods_class_is_suggested_on_post(self):
        bill = self._make_invoice('in_invoice', document_number='F002-46')
        self.assertEqual(bill.l10n_pe_sire_goods_class, '5', 'línea sin producto: gasto')
        product = self.env['product.product'].create({'name': 'Tornillos', 'type': 'consu'})
        goods = self._dni_bill('F002-49')
        goods.partner_id = self.partner
        goods.invoice_line_ids.product_id = product
        goods.action_post()
        self.assertEqual(goods.l10n_pe_sire_goods_class, '1')
        chosen = self._dni_bill('F002-50')
        chosen.write({'partner_id': self.partner.id, 'l10n_pe_sire_goods_class': '4'})
        chosen.action_post()
        self.assertEqual(chosen.l10n_pe_sire_goods_class, '4', 'se respeta lo elegido')

    def test_non_domiciled_withholding_is_computed(self):
        bill = self._make_invoice('in_invoice', document_number='F002-47')
        bill.write({'l10n_pe_sire_nd_gross_income': 1000.0,
                    'l10n_pe_sire_nd_withholding_rate': 30.0})
        self.assertAlmostEqual(bill.l10n_pe_sire_nd_withheld_tax, 300.0)
        bill.l10n_pe_sire_nd_withheld_tax = 295.0
        self.assertAlmostEqual(bill.l10n_pe_sire_nd_withheld_tax, 295.0)

    def test_invoice_shows_its_period(self):
        bill = self._make_invoice('in_invoice', document_number='F002-48')
        self.assertFalse(bill.l10n_pe_sire_book_info)
        self._system_line(self.rce, bill)
        bill.invalidate_recordset(['l10n_pe_sire_book_info', 'l10n_pe_sire_declared'])
        self.assertIn(self.rce.display_name, bill.l10n_pe_sire_book_info)
        self.assertFalse(bill.l10n_pe_sire_declared)
        self.rce.state = 'submitted'
        bill.invalidate_recordset(['l10n_pe_sire_book_info', 'l10n_pe_sire_declared'])
        self.assertTrue(bill.l10n_pe_sire_declared)

    # ------------------------------------------------------------------
    # Roles: quien prepara no declara
    # ------------------------------------------------------------------

    def test_preparer_cannot_submit_or_close(self):
        self._compared(self.rvie)
        record = self.rvie.with_user(self.accountant)
        with patch.object(type(self.rvie), '_sire_get_token', return_value='tok'), \
                patch.object(type(self.rvie), '_sire_accept_proposal',
                             return_value='T1') as accept:
            for method in ('action_accept_proposal', 'action_send_replacement',
                           'action_done'):
                with self.subTest(method=method), self.assertRaises(AccessError):
                    getattr(record, method)()
            accept.assert_not_called()
            # el preparador sí compara y valida
            record.action_validate()
            self.rvie.with_user(self.approver).action_accept_proposal()
        self.assertEqual(self.rvie.submission_ticket, 'T1')

    def test_account_managers_are_approvers(self):
        manager = new_test_user(
            self.env, login='sire_manager', groups='account.group_account_manager',
            company_id=self.company.id)
        self.assertTrue(manager.has_group('al_l10n_pe_sire.group_sire_approver'))

    def test_done_needs_clean_lines(self):
        invoice = self._make_invoice('out_invoice')
        self._compared(self.rvie, moves=invoice)
        self.rvie.system_line_ids.write({'nro_doc_identidad': '20131312956'})
        self.rvie.action_validate()
        with self.assertRaisesRegex(UserError, 'observaciones'):
            self.rvie.action_done()

    def test_reopen_asks_for_a_reason(self):
        self._compared(self.rvie)
        self.rvie.with_user(self.approver).action_done()
        self.assertEqual(self.rvie.state, 'done')
        with self.assertRaises(AccessError):
            self.rvie.with_user(self.accountant).action_reopen()
        action = self.rvie.with_user(self.approver).action_reopen()
        wizard = self.env[action['res_model']].with_user(self.approver).with_context(
            action['context']).create({'reason': 'Falta una nota de crédito'})
        wizard.action_apply()
        self.assertEqual(self.rvie.state, 'compared')
        self.assertTrue(any('Falta una nota de crédito' in message.body
                            for message in self.rvie.message_ids))

    # ------------------------------------------------------------------
    # Bitácora de la API
    # ------------------------------------------------------------------

    def test_failed_calls_are_logged(self):
        Log = self.env['l10n_pe.sire.api.log']
        response = MagicMock(status_code=500, text='{"msg": "Servicio no disponible"}',
                             content=b'{}', headers={'Content-Type': 'application/json'})
        # Sin assertRaises: deshace su bloque con un savepoint, y la bitácora
        # (que en producción va por su propio cursor) se perdería con él.
        with patch('odoo.addons.al_l10n_pe_sire.models.sire_api.requests.request',
                   return_value=response):
            try:
                self.rvie._sire_get('tok', '/libros/rvie/propuesta/web/propuesta/202607')
            except UserError:
                pass
            else:
                self.fail('un HTTP 500 debe ser un UserError')
        log = Log.search([('res_model', '=', self.rvie._name),
                          ('res_id', '=', self.rvie.id)], limit=1)
        self.assertTrue(log.is_error)
        self.assertEqual(log.status_code, 500)
        self.assertEqual(log.endpoint, '/libros/rvie/propuesta/web/propuesta/202607')
        self.assertIn('Servicio no disponible', log.response)

    def test_token_is_never_logged(self):
        self.company.sudo().write({
            'l10n_pe_sire_sol_user': 'USER', 'l10n_pe_sire_sol_password': 'x',
            'l10n_pe_sire_client_id': 'cid', 'l10n_pe_sire_client_secret': 's',
            'l10n_pe_sire_token': False, 'l10n_pe_sire_token_expiry': False,
        })
        response = MagicMock(status_code=200, text='{"access_token": "SECRETO"}')
        response.json.return_value = {'access_token': 'SECRETO', 'expires_in': 3600}
        with patch('odoo.addons.al_l10n_pe_sire.models.sire_api.requests.post',
                   return_value=response):
            self.env['l10n_pe.sire.api']._sire_get_token(self.company)
        logs = self.env['l10n_pe.sire.api.log'].search([('url', 'like', 'oauth2')])
        self.assertTrue(logs)
        self.assertFalse(any('SECRETO' in (log.response or '') for log in logs))
        self.assertFalse(any('cid' in log.url for log in logs))

    def test_old_logs_are_removed(self):
        Log = self.env['l10n_pe.sire.api.log']
        old = Log.create({'method': 'GET', 'endpoint': '/x',
                          'date': fields.Datetime.now() - timedelta(days=120)})
        recent = Log.create({'method': 'GET', 'endpoint': '/y'})
        Log._gc_sire_logs()
        self.assertFalse(old.exists())
        self.assertTrue(recent.exists())

    def test_log_is_read_only_for_approvers(self):
        self.assertFalse(self.env['l10n_pe.sire.api.log'].with_user(
            self.accountant).has_access('read'))
        self.assertTrue(self.env['l10n_pe.sire.api.log'].with_user(
            self.approver).has_access('read'))
        self.assertFalse(self.env['l10n_pe.sire.api.log'].with_user(
            self.approver).has_access('create'))
