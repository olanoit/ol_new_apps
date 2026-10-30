"""Recaudación bancaria: formato BCP, archivo de deudores y respuesta."""
import base64
from datetime import timedelta

from psycopg2 import IntegrityError

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger
from odoo.tools import BinaryBytes

from odoo.addons.al_l10n_pe_collection.tests.common import CollectionCommon


@tagged('post_install', '-at_install')
class TestBankCollection(CollectionCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer.write({'vat': '20100047218', 'name': 'COMPAÑÍA ÑANDÚ SAC'})
        cls.other_customer.vat = '20131312955'
        cls.debtors_layout = cls.env.ref('al_l10n_pe_bank_collection.layout_bcp_crep_debtors')
        cls.response_layout = cls.env.ref('al_l10n_pe_bank_collection.layout_bcp_crep_response')
        cls.agreement = cls.env['l10n_pe.bank.collection.agreement'].create({
            'name': 'BCP soles (prueba)', 'journal_id': cls.bank.id, 'account_branch': '191',
            'account_number': '1234567', 'company_name': 'MI EMPRESA SAC',
            'debtors_layout_id': cls.debtors_layout.id, 'response_layout_id': cls.response_layout.id,
            'days_ahead': 10,
        })

    def _batch(self, partners=None):
        partners = partners or (self.customer | self.other_customer)
        batch = self.env['l10n_pe.bank.collection.batch'].create({
            'agreement_id': self.agreement.id, 'partner_ids': [Command.set(partners.ids)]})
        batch.action_load()
        return batch

    def _response_file(self, rows):
        """Archivo de respuesta como el del banco, armado con el mismo formato."""
        details = [{
            'account_branch': '191', 'account_number': '1234567', 'currency': self.agreement.currency_id,
            'depositor_code': code, 'return_info': info, 'payment_date': self.today, 'due_date': self.today,
            'paid_amount': amount, 'late_amount': 0.0, 'paid_total': amount, 'branch': '000191',
            'operation_number': operation, 'channel': 'AGENTE',
        } for code, info, amount, operation in rows]
        header = {'account_branch': '191', 'account_number': '1234567', 'currency': self.agreement.currency_id,
                  'file_date': self.today, 'record_count': len(rows), 'total_amount': sum(r[2] for r in rows)}
        return BinaryBytes(self.response_layout._build_file(header, details))

    def _response(self, rows):
        response = self.env['l10n_pe.bank.collection.response'].create({
            'agreement_id': self.agreement.id, 'file': self._response_file(rows), 'filename': 'abonos.txt'})
        response.action_import()
        return response

    # ------------------------------------------------------------------ archivo de deudores
    def test_debtors_file_bcp_positions(self):
        overdue = self._invoice(1234.56, -10)
        self._invoice(100, 5)  # vence dentro de los 10 días
        self._invoice(100, 40)  # vence después: no se envía
        batch = self._batch()
        self.assertEqual(batch.line_count, 2)
        self.assertAlmostEqual(batch.amount_total, 1334.56)
        batch.action_generate()
        self.assertEqual(batch.state, 'generated')
        self.assertTrue(batch.filename.startswith('CREP_0_'))
        lines = batch.file.content.decode('ascii').split('\r\n')
        self.assertEqual(len(lines), 3)
        self.assertTrue(all(len(line) == 250 for line in lines))
        header, first = lines[0], lines[1]
        self.assertEqual(header[0:13], 'CC1910' + '1234567')
        self.assertEqual(header[13], 'C')
        self.assertEqual(header[14:54].rstrip(), 'MI EMPRESA SAC')
        self.assertEqual(header[54:62], batch.date.strftime('%Y%m%d'))
        self.assertEqual(header[62:71], '000000002')
        self.assertEqual(header[71:86], '000000000133456')
        self.assertEqual(header[86], 'R')
        self.assertEqual(first[0:2], 'DD')
        self.assertEqual(first[13:27].rstrip(), '20100047218')
        self.assertEqual(first[27:67].rstrip(), 'COMPANIA NANDU SAC', 'ASCII sin cambiar la longitud')
        self.assertEqual(first[67:97].rstrip(), overdue.name)
        self.assertEqual(first[105:113], overdue.invoice_date_due.strftime('%Y%m%d'))
        self.assertEqual(first[113:128], '000000000123456')
        self.assertEqual(first[143:152], '000123456', 'mínimo = total en validación completa')
        self.assertEqual(first[152], 'A')

    def test_debtors_skip_disputed_and_partners_without_code(self):
        disputed = self._invoice(300, -5)
        self.env['l10n_pe.collection.dispute'].create({
            'partner_id': self.customer.id, 'reason_id': self.env.ref('al_l10n_pe_collection.dispute_reason_price').id,
            'line_ids': [Command.set(self._receivable(disputed).ids)]})
        nocode = self.env['res.partner'].create({'name': 'SIN RUC SAC', 'is_company': True})
        self._invoice(50, -5, partner=nocode)
        batch = self._batch(self.customer | nocode)
        self.assertFalse(batch.line_ids)
        self.assertIn('SIN RUC SAC', batch.warning)

    def test_own_collection_code(self):
        self.agreement.code_source = 'code'
        self.customer.l10n_pe_bank_collection_code = 'CLI-0001'
        self._invoice(100, -1)
        batch = self._batch()
        self.assertEqual(batch.line_ids.depositor_code, 'CLI-0001')
        self.assertEqual(self.agreement._partner_by_code('CLI-0001'), self.customer)
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            self.other_customer.l10n_pe_bank_collection_code = 'CLI-0001'
            self.other_customer.flush_recordset()

    # ------------------------------------------------------------------ respuesta
    def test_response_matches_document_and_reconciles(self):
        invoice = self._invoice(500, -3)
        response = self._response([('20100047218', invoice.name, 500.0, '123456')])
        line = response.line_ids
        self.assertEqual((line.state, line.partner_id), ('matched', self.customer))
        self.assertEqual(line.move_line_ids, self._receivable(invoice))
        self.assertEqual(response.header_count, 1)
        response.action_process()
        self.assertEqual(response.state, 'done')
        self.assertEqual(line.state, 'done')
        self.assertTrue(line.payment_id)
        self.assertEqual(line.payment_id.journal_id, self.bank)
        self.assertIn('123456', line.payment_id.memo)
        self.assertIn(invoice.payment_state, ('paid', 'in_payment'))
        # El mismo archivo otra vez: operación ya procesada.
        again = self._response([('20100047218', invoice.name, 500.0, '123456')])
        self.assertEqual(again.line_ids.state, 'duplicate')
        self.assertEqual(again.payable_count, 0, 'sin cobros por pagar no se ofrece procesar')
        with self.assertRaises(UserError):
            again.action_process()
        with self.assertRaises(UserError):
            response.action_import()

    def test_response_without_document_pays_oldest_first(self):
        old = self._invoice(300, -20)
        newer = self._invoice(400, -5)
        response = self._response([('0020100047218', '', 500.0, '000777')])
        line = response.line_ids
        self.assertEqual(line.state, 'partner', 'ceros a la izquierda del banco')
        self.assertEqual(line.move_line_ids, self._receivable(old | newer))
        response.action_process()
        self.assertIn(old.payment_state, ('paid', 'in_payment'))
        self.assertAlmostEqual(newer.amount_residual, 200.0)

    def test_response_unmatched_then_manual_partner(self):
        invoice = self._invoice(80, -2, partner=self.other_customer)
        response = self._response([('99999999999', 'X', 80.0, '000001')])
        line = response.line_ids
        self.assertEqual(line.state, 'unmatched')
        self.assertEqual(response.pending_count, 1)
        with self.assertRaises(UserError):
            response.action_process()
        line.partner_id = self.other_customer
        line.action_rematch()
        self.assertEqual(line.state, 'partner')
        response.action_process()
        self.assertIn(invoice.payment_state, ('paid', 'in_payment'))

    def test_response_without_open_lines_is_advance(self):
        response = self._response([('20131312955', '', 60.0, '000009')])
        line = response.line_ids
        self.assertEqual(line.state, 'partner')
        self.assertFalse(line.move_line_ids)
        response.action_process()
        self.assertEqual(line.payment_id.partner_id, self.other_customer)
        self.assertAlmostEqual(line.payment_id.amount, 60.0)
        self.assertNotEqual(line.payment_id.state, 'draft')

    def test_parse_rejects_foreign_lines(self):
        response = self.env['l10n_pe.bank.collection.response'].create({
            'agreement_id': self.agreement.id, 'file': BinaryBytes(b'XX esto no es un CREP\r\n')})
        with self.assertRaises(UserError):
            response.action_import()

    # ------------------------------------------------------------------ formato
    def test_layout_validation(self):
        with self.assertRaises(ValidationError):
            self.env['l10n_pe.bank.collection.layout'].create({
                'name': 'Malo', 'file_type': 'debtors', 'record_length': 10,
                'field_ids': [Command.create({'name': 'A', 'start': 1, 'length': 5, 'kind': 'text'}),
                              Command.create({'name': 'B', 'start': 4, 'length': 5, 'kind': 'text'})]})
        with self.assertRaises(ValidationError):
            self.env['l10n_pe.bank.collection.layout'].create({
                'name': 'Constante', 'file_type': 'debtors',
                'field_ids': [Command.create({'name': 'Tipo', 'start': 1, 'length': 2, 'kind': 'constant',
                                              'value': 'D'})]})

    def test_amount_too_long(self):
        amount_field = self.debtors_layout.field_ids.filtered(lambda f: f.key == 'amount')
        self.assertEqual(amount_field._format(12.5, self.debtors_layout), '000000000001250')
        with self.assertRaises(UserError):
            amount_field._format(10 ** 13, self.debtors_layout)

    def test_agreement_currency_must_match_journal(self):
        usd = self.env.ref('base.USD')
        with self.assertRaises(ValidationError):
            self.agreement.currency_id = usd


@tagged('post_install', '-at_install')
class TestBankCollectionBBVA(CollectionCommon):
    """Formato oficial BBVA (ficha técnica E1891 V21)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.vat = '20100130204'
        cls.customer.write({'vat': '20100047218', 'name': 'ÑANDÚ, CÍA; S.A.C.'})
        cls.agreement = cls.env['l10n_pe.bank.collection.agreement'].create({
            'name': 'BBVA soles (prueba)', 'journal_id': cls.bank.id, 'service_code': '123',
            'account_number': '001102410100001250',
            'debtors_layout_id': cls.env.ref('al_l10n_pe_bank_collection.layout_bbva_debtors').id,
            'response_layout_id': cls.env.ref('al_l10n_pe_bank_collection.layout_bbva_response').id,
            'days_ahead': 0, 'block_days': 30,
        })

    def _batch(self, mode='replace'):
        batch = self.env['l10n_pe.bank.collection.batch'].create({
            'agreement_id': self.agreement.id, 'mode': mode,
            'partner_ids': [Command.set(self.customer.ids)]})
        batch.action_load()
        batch.action_generate()
        return batch

    def test_input_file_positions(self):
        invoice = self._invoice(1500.25, -4)
        self._invoice(99.75, -2)
        batch = self._batch()
        self.assertEqual(batch.filename, 'RC_123_%s.TXT' % batch.date.strftime('%Y%m%d'))
        lines = batch.file.content.decode('ascii').split('\r\n')
        self.assertEqual(len(lines), 4)
        self.assertTrue(all(len(line) == 360 for line in lines))
        header, first, footer = lines[0], lines[1], lines[-1]
        self.assertEqual(header[0:2], '01')
        self.assertEqual(header[2:13], '20100130204')
        self.assertEqual(header[13:16], '123')
        self.assertEqual(header[16:19], 'PEN')
        self.assertEqual(header[19:27], batch.date.strftime('%Y%m%d'))
        self.assertEqual(header[27:30], '000', 'primera versión del día')
        self.assertEqual(header[37], 'T', 'carga total')
        self.assertEqual(first[0:2], '02')
        self.assertEqual(first[2:32].rstrip(), 'NANDU  CIA  S.A.C.', 'tildes y caracteres especiales')
        self.assertEqual(first[32:43], '20100047218')
        self.assertEqual(first[43:80].rstrip(), invoice.name.replace('/', ' '), 'BBVA no acepta «/»')
        self.assertEqual(first[80:88], invoice.invoice_date_due.strftime('%Y%m%d'))
        self.assertEqual(first[88:96], (batch.date + timedelta(days=30)).strftime('%Y%m%d'),
                         'vencida: bloqueo a 30 días de hoy')
        self.assertEqual(first[96:98], '00')
        self.assertEqual(first[98:113], '000000000150025')
        self.assertEqual(first[113:128], '000000000150025', 'validación completa: mínimo = máximo')
        self.assertEqual(first[128:288], '0' * 160)
        self.assertEqual(first[288:308], '0' * 20)
        self.assertEqual(first[308], 'R')
        self.assertEqual(first[309:324].rstrip(), '20100047218')
        self.assertEqual(footer[0:2], '03')
        self.assertEqual(footer[2:11], '000000002')
        self.assertEqual(footer[11:29], '000000000000160000')
        self.assertEqual(footer[29:47], '000000000000160000')
        self.assertEqual(footer[47:65], '0' * 18)

    def test_second_file_same_day_is_next_version(self):
        self._invoice(100, -1)
        self._batch()
        second = self._batch(mode='update')
        header = second.file.content.decode('ascii')[:38]
        self.assertEqual(header[27:30], '001')
        self.assertEqual(header[37], 'P')

    def test_response_official_sample_layout(self):
        """Respuesta de 152 bytes armada a mano según la ficha técnica."""
        invoice = self._invoice(5045.43, -3)
        today = self.today.strftime('%Y%m%d')
        header = '01' + '20100130204' + '123' + 'PEN' + today + '001102410100001250'
        # El banco devuelve la referencia tal como se envió: sin «/».
        detail = ('02' + 'NANDU CIA SAC'.ljust(30) + '20100047218' + invoice.name.replace('/', ' ').ljust(37)
                  + '000000000504543' + '000000000504543' + '000000000000000' + '0241' + '520578'
                  + today + '01' + '06')
        footer = '03' + '000000001' + '000000000504543' + '000000000504543' + '000000000000000'
        content = '\r\n'.join(line.ljust(152) for line in (header, detail, footer)).encode('ascii')
        response = self.env['l10n_pe.bank.collection.response'].create({
            'agreement_id': self.agreement.id, 'file': BinaryBytes(content), 'filename': 'recaudos.txt'})
        response.action_import()
        line = response.line_ids
        self.assertEqual(len(line), 1)
        self.assertEqual((line.state, line.partner_id), ('matched', self.customer))
        self.assertAlmostEqual(line.amount, 5045.43)
        self.assertEqual(line.operation_number, '520578')
        self.assertEqual(line.branch, '0241')
        self.assertEqual(line.channel, 'Agentes')
        self.assertEqual(line.payment_date, self.today)
        self.assertEqual((response.header_count, response.header_amount), (1, 5045.43))
        response.action_process()
        self.assertIn(invoice.payment_state, ('paid', 'in_payment'))


@tagged('post_install', '-at_install')
class TestBankCollectionScotiabank(CollectionCommon):
    """Formato de Scotiabank (macro oficial de validación completa)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer.write({'vat': '20100047218', 'name': 'COMPAÑÍA, LÓPEZ & HIJOS S.A.'})
        cls.agreement = cls.env['l10n_pe.bank.collection.agreement'].create({
            'name': 'Scotiabank soles (prueba)', 'journal_id': cls.bank.id, 'account_branch': '000',
            'account_number': '7654321', 'company_name': 'MI EMPRESA SAC',
            'debtors_layout_id': cls.env.ref('al_l10n_pe_bank_collection.layout_scotiabank_debtors').id,
            'response_layout_id': cls.env.ref('al_l10n_pe_bank_collection.layout_scotiabank_response').id,
            'days_ahead': 0,
        })

    def test_input_file_positions(self):
        invoice = self._invoice(250.5, -6)
        batch = self.env['l10n_pe.bank.collection.batch'].create({
            'agreement_id': self.agreement.id, 'partner_ids': [Command.set(self.customer.ids)]})
        batch.action_load()
        batch.action_generate()
        self.assertEqual(batch.filename, 'RECAUDAC.TXT')
        header, detail = batch.file.content.decode('ascii').split('\r\n')
        self.assertEqual((len(header), len(detail)), (200, 200))
        self.assertEqual(header[0:14], 'CC' + '000' + '0' + '7654321' + 'C')
        self.assertEqual(header[14:54].rstrip(), 'MI EMPRESA SAC')
        self.assertEqual(header[54:62], batch.date.strftime('%Y%m%d'))
        self.assertEqual(header[62:71], '000000001')
        self.assertEqual(header[71:86], '000000000025050')
        self.assertEqual(header[86], 'R')
        self.assertEqual(detail[0:13], 'DD' + '000' + '0' + '7654321')
        self.assertEqual(detail[13:27].rstrip(), '20100047218')
        self.assertEqual(detail[27:67].rstrip(), 'COMPANIA  LOPEZ   HIJOS S A', 'sin tildes, eñes ni signos')
        self.assertEqual(detail[67:97].rstrip(), invoice.name.replace('/', ' '))
        self.assertEqual(detail[105:113], invoice.invoice_date_due.strftime('%Y%m%d'))
        self.assertEqual(detail[113:128], '000000000025050')
        self.assertEqual(detail[128:143], '0' * 15)
        self.assertEqual(detail[143:152], '000025050')
        self.assertEqual(detail[152], 'A')

    def test_results_file(self):
        invoice = self._invoice(250.5, -6)
        today = self.today.strftime('%Y%m%d')
        header = 'CC' + '000' + '0' + '7654321' + 'C' + today + '000000001' + '000000000025050'
        detail = ('DD' + '000' + '0' + '7654321' + '20100047218'.ljust(14)
                  + invoice.name.replace('/', ' ').ljust(30) + today + today
                  + '000000000025050' + '000000000000000' + '000000000025050'
                  + '193' + '000045678' + 'REF'.ljust(22) + 'T001' + 'AGENTE'.ljust(12) + '103015'
                  + ' ' * 10 + '00' + '0' * 15)
        content = (header + '\r\n' + detail).encode('ascii')
        response = self.env['l10n_pe.bank.collection.response'].create({
            'agreement_id': self.agreement.id, 'file': BinaryBytes(content)})
        response.action_import()
        line = response.line_ids
        self.assertEqual((line.state, line.partner_id), ('matched', self.customer))
        self.assertAlmostEqual(line.amount, 250.5)
        self.assertEqual((line.branch, line.operation_number, line.channel), ('193', '000045678', 'AGENTE'))
        self.assertEqual((response.header_count, response.header_amount), (1, 250.5))
        response.action_process()
        self.assertIn(invoice.payment_state, ('paid', 'in_payment'))

    # ------------------------------------------------------------------ validación parcial
    def _partial_agreement(self):
        self.agreement.write({
            'validation': 'partial',
            'debtors_layout_id': self.env.ref('al_l10n_pe_bank_collection.layout_scotiabank_partial_debtors').id,
            'response_layout_id': self.env.ref('al_l10n_pe_bank_collection.layout_scotiabank_partial_response').id,
        })

    def test_partial_one_line_per_customer(self):
        self._partial_agreement()
        self._invoice(100, -20)
        self._invoice(50, -5)
        batch = self.env['l10n_pe.bank.collection.batch'].create({
            'agreement_id': self.agreement.id, 'partner_ids': [Command.set(self.customer.ids)]})
        batch.action_load()
        self.assertEqual(len(batch.line_ids), 1)
        self.assertAlmostEqual(batch.line_ids.amount, 150.0)
        batch.action_generate()
        header, detail = batch.file.content.decode('ascii').split('\r\n')
        self.assertEqual((len(header), len(detail)), (200, 200))
        self.assertEqual(header[13], 'P')
        self.assertEqual(header[62:71], '000000001')
        self.assertEqual(header[71:86], ' ' * 15, 'sin importe total')
        self.assertEqual(header[86], 'R')
        self.assertEqual(detail[13:27].rstrip(), '20100047218')
        self.assertEqual(detail[67:97], ' ' * 30, 'sin documento: se aplica a lo más antiguo')
        self.assertEqual(detail[97:152], ' ' * 55)
        self.assertEqual(detail[152], 'A')

    def test_partial_results_pay_oldest_first(self):
        self._partial_agreement()
        old = self._invoice(100, -20)
        newer = self._invoice(50, -5)
        today = self.today.strftime('%Y%m%d')
        header = 'CC' + '000' + '0' + '7654321' + 'P' + today + '000000001' + '000000000012000'
        detail = ('DD' + '000' + '0' + '7654321' + '20100047218'.ljust(14) + ' ' * 30 + today + ' ' * 8
                  + '000000000012000' + ' ' * 30 + '193' + '000000777' + ' ' * 22 + 'T001'
                  + 'BANCA INTERN' + '090000')
        response = self.env['l10n_pe.bank.collection.response'].create({
            'agreement_id': self.agreement.id, 'file': BinaryBytes((header + '\r\n' + detail).encode())})
        response.action_import()
        line = response.line_ids
        self.assertEqual((line.state, line.partner_id), ('partner', self.customer))
        self.assertAlmostEqual(line.amount, 120.0)
        response.action_process()
        self.assertIn(old.payment_state, ('paid', 'in_payment'))
        self.assertAlmostEqual(newer.amount_residual, 30.0)

    # ------------------------------------------------------------------ validación de importes
    def _amounts_agreement(self):
        self.agreement.write({
            'validation': 'amounts',
            'debtors_layout_id': self.env.ref('al_l10n_pe_bank_collection.layout_scotiabank_amounts_debtors').id,
            'response_layout_id': self.env.ref('al_l10n_pe_bank_collection.layout_scotiabank_amounts_response').id,
            'payment_type_ids': [
                Command.create({'code': 'TRAMITE01', 'name': 'Derecho de trámite', 'amount': 50.0, 'surcharge': 2.5}),
                Command.create({'code': 'CONSTANCIA', 'name': 'Constancia', 'amount': 20.0}),
            ],
        })

    def test_amounts_payment_types_file(self):
        self._amounts_agreement()
        batch = self.env['l10n_pe.bank.collection.batch'].create({'agreement_id': self.agreement.id})
        batch.action_load()
        self.assertEqual(len(batch.line_ids), 2)
        batch.action_generate()
        header, first, second = batch.file.content.decode('ascii').split('\r\n')
        self.assertTrue(all(len(line) == 200 for line in (header, first, second)))
        self.assertEqual(header[13], '7')
        self.assertEqual(header[62:71], '000000002')
        self.assertEqual(first[13:33].rstrip(), 'TRAMITE01')
        self.assertEqual(first[33:73].rstrip(), 'Derecho de tramite')
        self.assertEqual(first[103:112], '000005000')
        self.assertEqual(first[112:121], '000000250')
        self.assertEqual(first[121:130], '000005250')
        self.assertEqual(second[121:130], '000002000')

    def test_amounts_results_identify_payer(self):
        self._amounts_agreement()
        today = self.today.strftime('%Y%m%d')
        header = 'CC' + '000' + '0' + '7654321' + '7' + today + '000000002' + '000000000007250'
        payer = ('DD' + '000' + '0' + '7654321' + 'TRAMITE01'.ljust(20) + 'DERECHO DE TRAMITE'.ljust(40) + today
                 + '20100047218'.ljust(40) + ' ' * 30 + '000005000' + '000000250' + '000005250' + '193'
                 + '000000888' + ' ' * 22 + 'T001' + 'AGENTE'.ljust(12) + '101500')
        unknown = payer.replace('20100047218', '99999999   ').replace('000000888', '000000889')
        response = self.env['l10n_pe.bank.collection.response'].create({
            'agreement_id': self.agreement.id,
            'file': BinaryBytes((header + '\r\n' + payer + '\r\n' + unknown).encode())})
        response.action_import()
        known, other = response.line_ids.sorted('line_number')
        self.assertEqual((known.state, known.partner_id), ('partner', self.customer))
        self.assertEqual((known.payment_type, known.reference), ('TRAMITE01', 'DERECHO DE TRAMITE'))
        self.assertAlmostEqual(known.amount, 52.5)
        self.assertEqual(other.state, 'unmatched')
        other.action_skip()
        response.action_process()
        self.assertEqual(known.payment_id.partner_id, self.customer)
        self.assertAlmostEqual(known.payment_id.amount, 52.5)
        self.assertEqual(response.state, 'done')
