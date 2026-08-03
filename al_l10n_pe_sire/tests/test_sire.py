import base64
import io
import zipfile
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

RUC_TEST = '20512528458'
PERIOD_YEAR = 2026
PERIOD_MONTH = '07'
PERIOD_DATE = fields.Date.to_date('2026-07-15')


def _rvie_row(car='20512528458010F00100000000012', serie='F001', nro='12',
              base='100.00', igv='18.00', total='118.00'):
    """Fila de 40 columnas del TXT de propuesta RVIE."""
    cols = [''] * 40
    cols[0] = RUC_TEST
    cols[1] = 'EMPRESA DE PRUEBA'
    cols[2] = '%s%s' % (PERIOD_YEAR, PERIOD_MONTH)
    cols[3] = car
    cols[4] = '15/07/2026'
    cols[5] = ''
    cols[6] = '01'
    cols[7] = serie
    cols[8] = nro
    cols[10] = '6'
    cols[11] = '20131312955'
    cols[12] = 'CLIENTE SA'
    cols[13] = '0.00'
    cols[14] = base
    cols[15] = '0.00'
    cols[16] = igv
    cols[17] = '0.00'
    cols[18] = '0.00'
    cols[19] = '0.00'
    cols[20] = '0.00'
    cols[21] = '0.00'
    cols[22] = '0.00'
    cols[23] = '0.00'
    cols[24] = '0.00'
    cols[25] = total
    cols[26] = 'PEN'
    cols[27] = '0.000'
    cols[34] = '1'
    cols[36] = '0.00'
    cols[37] = '0101'
    return '|'.join(cols)


def _rce_row(car='20131312955010F00200000000034', serie='F002', nro='34',
             base='200.00', igv='36.00', total='236.00'):
    """Fila de 41 columnas del TXT de propuesta RCE."""
    cols = [''] * 41
    cols[0] = RUC_TEST
    cols[1] = 'EMPRESA DE PRUEBA'
    cols[2] = '%s%s' % (PERIOD_YEAR, PERIOD_MONTH)
    cols[3] = car
    cols[4] = '15/07/2026'
    cols[5] = ''
    cols[6] = '01'
    cols[7] = serie
    cols[8] = ''
    cols[9] = nro
    cols[11] = '6'
    cols[12] = '20131312955'
    cols[13] = 'PROVEEDOR SA'
    cols[14] = base
    cols[15] = igv
    cols[16] = '0.00'
    cols[17] = '0.00'
    cols[18] = '0.00'
    cols[19] = '0.00'
    cols[20] = '0.00'
    cols[21] = '0.00'
    cols[22] = '0.00'
    cols[23] = '0.00'
    cols[24] = total
    cols[25] = 'PEN'
    cols[26] = '0.000'
    cols[37] = ''
    cols[38] = ''
    cols[39] = '1'
    cols[40] = ''
    return '|'.join(cols)


def _as_proposal(rows):
    header = 'CABECERA'
    return base64.b64encode(('\n'.join([header] + rows)).encode('utf-8'))


@tagged('post_install', '-at_install')
class TestSire(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        if (cls.company.vat or '') != RUC_TEST:
            cls.company.vat = RUC_TEST
        # Un periodo es único por libro y compañía, y la base de pruebas
        # puede traer ya el de este mes —el script de demostración crea
        # uno—. Se limpia dentro de la transacción del test, que se
        # revierte al terminar: la base no se toca.
        for model in ('l10n_pe.sire.rvie', 'l10n_pe.sire.rce'):
            existing = cls.env[model].search([
                ('year', '=', PERIOD_YEAR),
                ('month', '=', PERIOD_MONTH),
                ('company_id', '=', cls.company.id),
            ])
            if existing:
                existing.state = 'draft'
                existing.unlink()
        cls.rvie = cls.env['l10n_pe.sire.rvie'].create({
            'year': PERIOD_YEAR,
            'month': PERIOD_MONTH,
            'company_id': cls.company.id,
            'download_manual': True,
        })
        cls.rce = cls.env['l10n_pe.sire.rce'].create({
            'year': PERIOD_YEAR,
            'month': PERIOD_MONTH,
            'company_id': cls.company.id,
            'download_manual': True,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Socio SIRE Test',
            'vat': '20131312955',
            'country_id': cls.env.ref('base.pe').id,
            'l10n_latam_identification_type_id': cls.env['l10n_latam.identification.type'].search([
                ('l10n_pe_vat_code', '=', '6')], limit=1).id,
        })

    def _tax(self, type_tax_use):
        return self.env['account.tax'].search([
            ('company_id', '=', self.company.id),
            ('type_tax_use', '=', type_tax_use),
            ('amount', '=', 18),
            ('l10n_pe_edi_tax_code', '=', '1000'),
        ], limit=1)

    def _make_invoice(self, move_type, document_number=None, invoice_date=PERIOD_DATE):
        tax = self._tax('sale' if move_type.startswith('out') else 'purchase')
        self.assertTrue(tax, 'No se encontró IGV 18%% para %s' % move_type)
        vals = {
            'move_type': move_type,
            'partner_id': self.partner.id,
            'invoice_date': invoice_date,
            'invoice_line_ids': [(0, 0, {
                'name': 'Producto de prueba',
                'quantity': 1,
                'price_unit': 1000.0,
                'tax_ids': [(6, 0, tax.ids)],
            })],
        }
        if move_type.startswith('in'):
            doc_type = self.env['l10n_latam.document.type'].search([
                ('code', '=', '01'), ('country_id.code', '=', 'PE')], limit=1)
            vals.update({
                'l10n_latam_document_type_id': doc_type.id,
                'l10n_latam_document_number': document_number or 'F002-34',
                'ref': document_number or 'F002-34',
            })
        invoice = self.env['account.move'].create(vals)
        invoice.action_post()
        return invoice

    # ------------------------------------------------------------------
    # Configuración
    # ------------------------------------------------------------------

    def test_compare_fields_data(self):
        CompareField = self.env['l10n_pe.sire.compare.field']
        self.assertTrue(CompareField.search_count([('book_type', '=', 'rce')]))
        self.assertTrue(CompareField.search_count([('book_type', '=', 'rvie')]))

    def test_credentials_required(self):
        self.company.write({
            'l10n_pe_sire_sol_user': False,
            'l10n_pe_sire_sol_password': False,
            'l10n_pe_sire_client_id': False,
            'l10n_pe_sire_client_secret': False,
        })
        with self.assertRaises(UserError):
            self.env['l10n_pe.sire.api']._sire_credentials(self.company)

    def test_manual_confirm_requires_file(self):
        with self.assertRaises(UserError):
            self.rvie.action_request_proposal()

    # ------------------------------------------------------------------
    # Parseo de la propuesta
    # ------------------------------------------------------------------

    def test_rvie_parse_proposal(self):
        self.rvie.proposal_file = _as_proposal([_rvie_row()])
        self.rvie.action_load_sire()
        self.assertEqual(self.rvie.state, 'sire_loaded')
        line = self.rvie.sire_line_ids
        self.assertEqual(len(line), 1)
        self.assertEqual(line.tipo_cp, '01')
        self.assertEqual(line.serie_cp, 'F001')
        self.assertEqual(line.nro_cp, '12')
        self.assertEqual(line.fecha_emision, PERIOD_DATE)
        self.assertAlmostEqual(line.bi_gravada, 100.0)
        self.assertAlmostEqual(line.igv_ipm, 18.0)
        self.assertAlmostEqual(line.total_cp, 118.0)
        self.assertEqual(line.moneda, 'PEN')
        self.assertEqual(line.estado_cp, '1')
        self.assertEqual(line.tipo_operacion, '0101')

    def test_rce_parse_proposal(self):
        self.rce.proposal_file = _as_proposal([_rce_row()])
        self.rce.action_load_sire()
        line = self.rce.sire_line_ids
        self.assertEqual(len(line), 1)
        self.assertEqual(line.serie_cp, 'F002')
        self.assertEqual(line.nro_cp, '34')
        self.assertAlmostEqual(line.bi_gravada_dg, 200.0)
        self.assertAlmostEqual(line.igv_dg, 36.0)
        self.assertAlmostEqual(line.total_cp, 236.0)
        self.assertEqual(line.detraccion, 'No')
        self.assertEqual(line.estado_cp, '1')

    def test_parse_rejects_short_rows(self):
        self.rvie.proposal_file = base64.b64encode(b'CABECERA\na|b|c')
        with self.assertRaises(UserError):
            self.rvie.action_load_sire()

    # ------------------------------------------------------------------
    # Líneas del sistema
    # ------------------------------------------------------------------

    def test_rvie_system_lines(self):
        invoice = self._make_invoice('out_invoice')
        self.rvie.action_load_system()
        line = self.rvie.system_line_ids.filtered(lambda l: l.move_id == invoice)
        self.assertEqual(len(line), 1)
        self.assertEqual(line.tipo_doc_identidad, '6')
        self.assertEqual(line.nro_doc_identidad, '20131312955')
        self.assertAlmostEqual(line.bi_gravada, 1000.0, places=2)
        self.assertAlmostEqual(line.igv_ipm, 180.0, places=2)
        self.assertAlmostEqual(line.total_cp, 1180.0, places=2)
        self.assertEqual(line.estado_cp, '1')
        self.assertEqual(line.moneda, 'PEN')
        self.assertFalse(line.tipo_cambio)
        self.assertEqual(len(line.car_sunat), 27)
        self.assertTrue(line.car_sunat.startswith(RUC_TEST))

    def test_rce_system_lines(self):
        bill = self._make_invoice('in_invoice', document_number='F002-34')
        bill.l10n_pe_sire_goods_class = '1'
        self.rce.action_load_system()
        line = self.rce.system_line_ids.filtered(lambda l: l.move_id == bill)
        self.assertEqual(len(line), 1)
        self.assertEqual(line.serie_cp, 'F002')
        self.assertEqual(line.nro_cp, '34')
        self.assertAlmostEqual(line.bi_gravada_dg, 1000.0, places=2)
        self.assertAlmostEqual(line.igv_dg, 180.0, places=2)
        self.assertAlmostEqual(line.total_cp, 1180.0, places=2)
        self.assertEqual(line.clasif_bienes, '1')
        self.assertEqual(line.detraccion, 'No')
        self.assertTrue(line.car_sunat.startswith('20131312955'))

    def test_rvie_refund_previous_period_discount_columns(self):
        invoice = self._make_invoice(
            'out_invoice', invoice_date=fields.Date.to_date('2026-06-10'))
        reversal = self.env['account.move.reversal'].with_context(
            active_model='account.move', active_ids=invoice.ids).create({
                'journal_id': invoice.journal_id.id,
                'date': PERIOD_DATE,
            })
        action = reversal.refund_moves()
        refund = self.env['account.move'].browse(action['res_id'])
        refund.invoice_date = PERIOD_DATE
        refund.action_post()
        self.rvie.action_load_system()
        line = self.rvie.system_line_ids.filtered(lambda l: l.move_id == refund)
        self.assertEqual(len(line), 1)
        self.assertAlmostEqual(line.bi_gravada, 0.0, places=2)
        self.assertAlmostEqual(line.dscto_bi, -1000.0, places=2)
        self.assertAlmostEqual(line.dscto_igv, -180.0, places=2)
        self.assertAlmostEqual(line.total_cp, -1180.0, places=2)
        self.assertEqual(line.tipo_cp_mod, '01')

    # ------------------------------------------------------------------
    # Comparación
    # ------------------------------------------------------------------

    def _load_matching_lines(self, record, line_model, common):
        self.env[line_model].create([
            dict(common, sire_id=record.id, type_line='sire'),
            dict(common, sire_id=record.id, type_line='system'),
        ])

    def test_compare_states(self):
        Line = self.env['l10n_pe.sire.rvie.line']
        common = {
            'car_sunat': 'CAR-IGUAL',
            'fecha_emision': PERIOD_DATE,
            'tipo_cp': '01',
            'serie_cp': 'F001',
            'nro_cp': '1',
            'tipo_doc_identidad': '6',
            'nro_doc_identidad': '20131312955',
            'bi_gravada': 100.0,
            'igv_ipm': 18.0,
            'total_cp': 118.0,
            'moneda': 'PEN',
            'estado_cp': '1',
        }
        self._load_matching_lines(self.rvie, 'l10n_pe.sire.rvie.line', common)
        Line.create([
            dict(common, sire_id=self.rvie.id, type_line='sire',
                 car_sunat='CAR-DIFF', total_cp=118.0),
            dict(common, sire_id=self.rvie.id, type_line='system',
                 car_sunat='CAR-DIFF', total_cp=120.0),
            dict(common, sire_id=self.rvie.id, type_line='sire', car_sunat='CAR-SOLO-SIRE'),
            dict(common, sire_id=self.rvie.id, type_line='system', car_sunat='CAR-SOLO-SISTEMA'),
        ])
        self.rvie.action_compare()
        self.assertEqual(self.rvie.state, 'compared')
        by_car = {}
        for line in self.rvie.sire_line_ids | self.rvie.system_line_ids:
            by_car.setdefault(line.car_sunat, set()).add(line.compare_state)
        self.assertEqual(by_car['CAR-IGUAL'], {'0'})
        self.assertEqual(by_car['CAR-DIFF'], {'1'})
        self.assertEqual(by_car['CAR-SOLO-SIRE'], {'2'})
        self.assertEqual(by_car['CAR-SOLO-SISTEMA'], {'3'})
        diff_line = self.rvie.sire_line_ids.filtered(lambda l: l.car_sunat == 'CAR-DIFF')
        self.assertIn('Total CP', diff_line.diff_detail)
        self.assertIn('118.00', diff_line.diff_detail)
        self.assertIn('120.00', diff_line.diff_detail)
        self.assertEqual(len(self.rvie.diff_line_ids), 4)

    # ------------------------------------------------------------------
    # Exportables
    # ------------------------------------------------------------------

    def _read_zip_txt(self, record):
        payload = base64.b64decode(record.export_file)
        archive = zipfile.ZipFile(io.BytesIO(payload))
        name = archive.namelist()[0]
        return name, archive.read(name).decode('utf-8')

    def test_rvie_replacement_txt(self):
        self._make_invoice('out_invoice')
        self.rvie.action_load_system()
        self.rvie.action_export_replacement()
        name, content = self._read_zip_txt(self.rvie)
        self.assertEqual(name, 'LE%s%s%s00140400021112.txt' % (RUC_TEST, PERIOD_YEAR, PERIOD_MONTH))
        for row in content.split('\n'):
            self.assertEqual(len(row.split('|')), 34)

    def test_rce_replacement_txt(self):
        self._make_invoice('in_invoice', document_number='F002-35')
        self.rce.action_load_system()
        self.rce.action_export_replacement()
        name, content = self._read_zip_txt(self.rce)
        self.assertEqual(name, 'LE%s%s%s00080400021112.txt' % (RUC_TEST, PERIOD_YEAR, PERIOD_MONTH))
        for row in content.split('\n'):
            self.assertEqual(len(row.split('|')), 37)

    def test_xlsx_export(self):
        self.rvie.proposal_file = _as_proposal([_rvie_row()])
        self.rvie.action_load_sire()
        self.rvie.action_export_xlsx()
        self.assertTrue(self.rvie.export_file)
        self.assertEqual(self.rvie.export_filename, 'RVIE_%s_%s.xlsx' % (PERIOD_MONTH, PERIOD_YEAR))

    # ------------------------------------------------------------------
    # Flujo
    # ------------------------------------------------------------------

    def test_reset_and_done_guard(self):
        self.rvie.proposal_file = _as_proposal([_rvie_row()])
        self.rvie.action_load_sire()
        self.rvie.action_reset()
        self.assertFalse(self.rvie.sire_line_ids)
        self.assertEqual(self.rvie.state, 'downloaded')
        self.rvie.action_done()
        with self.assertRaises(UserError):
            self.rvie.unlink()

    # ------------------------------------------------------------------
    # Envío a SUNAT (aceptación, reemplazo y preliminar)
    # ------------------------------------------------------------------

    def _compared(self, record, rows=(), moves=None):
        """Deja un periodo comparado con un lado «sistema» controlado.

        La base de pruebas ya tiene comprobantes del periodo, así que el
        sistema se fija a lo que cada caso necesita en vez de depender de
        lo que haya cargado antes.
        """
        record.proposal_file = _as_proposal(list(rows))
        record.action_load_sire()
        moves = self.env['account.move'] if moves is None else moves
        with patch.object(type(record), '_sire_system_moves', return_value=moves):
            record.action_load_system()
        record.action_compare()
        return record

    def test_accept_needs_a_comparison(self):
        """Aceptar antes de comparar es aceptar a ciegas."""
        with self.assertRaises(UserError):
            self.rvie.action_accept_proposal()

    def test_accept_refuses_with_differences(self):
        """Con diferencias, aceptar daría por buena la propuesta."""
        self._compared(self.rvie, rows=[_rvie_row()])
        self.assertEqual(self.rvie.count_only_sire, 1)
        with self.assertRaises(UserError) as error:
            self.rvie.action_accept_proposal()
        self.assertIn('reemplazo', str(error.exception))

    def test_accept_sends_and_stores_the_ticket(self):
        self._compared(self.rvie)
        self.assertEqual(self.rvie.count_sire, 0)
        with patch.object(
                type(self.rvie), '_sire_get_token', return_value='tok'), \
             patch.object(
                type(self.rvie), '_sire_accept_proposal',
                return_value='2026000001') as accept:
            self.rvie.action_accept_proposal()
        self.assertEqual(self.rvie.submission_type, 'accept')
        self.assertEqual(self.rvie.submission_ticket, '2026000001')
        self.assertEqual(self.rvie.state, 'submitted')
        # El endpoint es el del RVIE, con su periodo
        self.assertIn('/libros/rvie/propuesta/web/propuesta/%s%s/aceptapropuesta'
                      % (PERIOD_YEAR, PERIOD_MONTH), accept.call_args[0][1])

    def test_replacement_upload_carries_the_official_metadata(self):
        invoice = self._make_invoice('out_invoice', document_number='F003-77')
        self._compared(self.rvie, moves=invoice)
        with patch.object(
                type(self.rvie), '_sire_get_token', return_value='tok'), \
             patch.object(
                type(self.rvie), '_sire_upload',
                return_value='2026000002') as upload:
            self.rvie.action_send_replacement()
        metadata = upload.call_args[0][3]
        self.assertEqual(metadata['codLibro'], '140000', 'libro del RVIE')
        self.assertEqual(metadata['codProceso'], '3', 'reemplazo del RVIE')
        self.assertEqual(metadata['codOrigenEnvio'], '2', 'servicio web')
        self.assertEqual(metadata['codTipoCorrelativo'], '01')
        self.assertEqual(metadata['numRuc'], RUC_TEST)
        self.assertEqual(metadata['perTributario'], '%s%s' % (PERIOD_YEAR, PERIOD_MONTH))
        self.assertTrue(metadata['filename'].endswith('.zip'))
        self.assertEqual(self.rvie.submission_type, 'replace')
        self.assertEqual(self.rvie.state, 'submitted')

    def test_rce_replacement_uses_its_own_codes(self):
        invoice = self._make_invoice('in_invoice', document_number='F004-88')
        self._compared(self.rce, moves=invoice)
        with patch.object(
                type(self.rce), '_sire_get_token', return_value='tok'), \
             patch.object(
                type(self.rce), '_sire_upload', return_value='T') as upload:
            self.rce.action_send_replacement()
        metadata = upload.call_args[0][3]
        self.assertEqual(metadata['codLibro'], '080000', 'libro del RCE')
        self.assertEqual(metadata['codProceso'], '61', 'reemplazo del RCE')

    def test_only_one_submission_per_period(self):
        self._compared(self.rvie)
        with patch.object(
                type(self.rvie), '_sire_get_token', return_value='tok'), \
             patch.object(
                type(self.rvie), '_sire_accept_proposal', return_value='T1'):
            self.rvie.action_accept_proposal()
            with self.assertRaises(UserError):
                self.rvie.action_accept_proposal()

    def test_reset_is_blocked_after_submitting(self):
        """Rehacer las líneas no deshace lo declarado."""
        self._compared(self.rvie)
        with patch.object(
                type(self.rvie), '_sire_get_token', return_value='tok'), \
             patch.object(
                type(self.rvie), '_sire_accept_proposal', return_value='T1'):
            self.rvie.action_accept_proposal()
        with self.assertRaises(UserError):
            self.rvie.action_reset()

    def test_preliminary_needs_a_submission(self):
        self._compared(self.rvie)
        with self.assertRaises(UserError):
            self.rvie.action_register_preliminary()

    def test_preliminary_closes_the_period(self):
        self._compared(self.rce)
        with patch.object(
                type(self.rce), '_sire_get_token', return_value='tok'), \
             patch.object(
                type(self.rce), '_sire_accept_proposal', return_value='T1'), \
             patch.object(
                type(self.rce), '_sire_register_preliminary',
                return_value=True) as register:
            self.rce.action_accept_proposal()
            self.rce.action_register_preliminary()
        self.assertTrue(self.rce.preliminary_registered)
        self.assertEqual(self.rce.state, 'done')
        self.assertIn('registrapreliminares', register.call_args[0][1])

    # ------------------------------------------------------------------
    # Refactor: unicidad, resumen y codificación
    # ------------------------------------------------------------------

    def test_one_period_per_book_and_company(self):
        with self.assertRaises(UserError):
            self.env['l10n_pe.sire.rvie'].create({
                'year': PERIOD_YEAR, 'month': PERIOD_MONTH,
                'company_id': self.company.id})

    def test_compare_counts_summarise_the_result(self):
        invoice = self._make_invoice('out_invoice', document_number='F005-99')
        self._compared(self.rvie, rows=[_rvie_row()], moves=invoice)
        self.assertEqual(self.rvie.count_sire, 1)
        self.assertEqual(self.rvie.count_system, 1)
        self.assertEqual(
            self.rvie.count_ok + self.rvie.count_diff + self.rvie.count_only_sire,
            self.rvie.count_sire, 'cada línea de la propuesta tiene un estado')

    def test_latin1_proposals_are_readable(self):
        """SUNAT ha entregado TXT en latin-1; no debe reventar el flujo."""
        api = self.env['l10n_pe.sire.api']
        self.assertEqual(api._sire_decode('Ñandú S.A.C.'.encode('latin-1')),
                         'Ñandú S.A.C.')
        self.assertEqual(api._sire_decode('Ñandú S.A.C.'.encode('utf-8')),
                         'Ñandú S.A.C.')

    def test_tus_metadata_is_base64(self):
        api = self.env['l10n_pe.sire.api']
        header = api._sire_tus_metadata({'numRuc': RUC_TEST, 'codLibro': '140000'})
        self.assertEqual(
            header,
            'numRuc %s,codLibro %s' % (
                base64.b64encode(RUC_TEST.encode()).decode(),
                base64.b64encode(b'140000').decode()))
