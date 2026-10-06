import base64
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.al_l10n_pe_sire.models.sire_mixin import SIRE_POLL_MAX_ATTEMPTS
from odoo.addons.al_l10n_pe_sire.models.sire_validation import ruc_is_valid, tax_mismatch

from .test_sire import PERIOD_DATE, TestSire


@tagged('post_install', '-at_install')
class TestSireValidation(TestSire):
    """Validaciones previas al envío, consulta automática de tickets y DG/DGNG/DNG."""

    def _system_line(self, record, move):
        with patch.object(type(record), '_sire_system_moves', return_value=move):
            record.action_load_system()
        return record.system_line_ids.filtered(lambda l: l.move_id == move)

    # ------------------------------------------------------------------
    # RUC
    # ------------------------------------------------------------------

    def test_ruc_check_digit(self):
        self.assertTrue(ruc_is_valid('20512528458'))
        self.assertTrue(ruc_is_valid('20131312955'))
        self.assertTrue(ruc_is_valid('10072486892'))
        self.assertFalse(ruc_is_valid('20512528459'), 'dígito verificador')
        self.assertFalse(ruc_is_valid('30512528458'), 'prefijo')
        self.assertFalse(ruc_is_valid('2051252845'), 'longitud')
        self.assertFalse(ruc_is_valid('2051252845A'))
        self.assertFalse(ruc_is_valid(False))

    def test_company_ruc_check_digit(self):
        company = self.env['res.company'].new({'name': 'RUC mal escrito', 'vat': '20512528459'})
        with self.assertRaisesRegex(UserError, 'dígito verificador'):
            self.env['l10n_pe.sire.api']._sire_check_ruc(company)

    # ------------------------------------------------------------------
    # Validación de líneas
    # ------------------------------------------------------------------

    def test_tax_mismatch_rates(self):
        self.assertFalse(tax_mismatch(1000, 180, (0.18, 0.10)))
        self.assertFalse(tax_mismatch(1000, 100, (0.18, 0.10)), 'restaurantes MYPE')
        self.assertFalse(tax_mismatch(1000, 180.9, (0.18,)), 'redondeo por línea')
        self.assertTrue(tax_mismatch(1000, 150, (0.18, 0.10)))
        self.assertTrue(tax_mismatch(0, 18, (0.18,)), 'IGV sin base')
        self.assertFalse(tax_mismatch(0, 0, (0.18,)))

    def test_valid_invoice_has_no_observations(self):
        invoice = self._make_invoice('out_invoice')
        line = self._system_line(self.rvie, invoice)
        self.assertFalse(line.check_detail, line.check_detail)
        self.assertEqual(self.rvie.count_invalid, 0)

    def test_valid_bill_has_no_observations(self):
        bill = self._make_invoice('in_invoice', document_number='F002-35')
        line = self._system_line(self.rce, bill)
        self.assertFalse(line.check_detail, line.check_detail)

    def test_rules_flag_each_problem(self):
        invoice = self._make_invoice('out_invoice')
        line = self._system_line(self.rvie, invoice)
        line.write({
            'nro_doc_identidad': '20131312956',
            'serie_cp': 'F01',
            'igv_ipm': 150.0,
            'moneda': 'USD',
            'tipo_cambio': 0.0,
        })
        self.rvie.action_validate()
        detail = line.check_detail
        self.assertIn('RUC 20131312956', detail)
        self.assertIn('serie', detail)
        self.assertIn('IGV/IPM', detail)
        self.assertIn('total', detail)
        self.assertIn('tipo de cambio', detail)
        self.assertEqual(self.rvie.count_invalid, 1)
        self.assertEqual(self.rvie.invalid_line_ids, line)

    def test_invoice_requires_customer_ruc(self):
        invoice = self._make_invoice('out_invoice')
        line = self._system_line(self.rvie, invoice)
        line.write({'tipo_doc_identidad': '1', 'nro_doc_identidad': '12345678'})
        self.rvie.action_validate()
        self.assertIn('RUC del cliente', line.check_detail)

    def test_note_requires_its_origin(self):
        invoice = self._make_invoice('out_invoice')
        line = self._system_line(self.rvie, invoice)
        line.write({'tipo_cp': '07'})
        self.rvie.action_validate()
        self.assertIn('comprobante que modifica', line.check_detail)

    def test_rce_due_date_types(self):
        bill = self._make_invoice('in_invoice', document_number='F002-36')
        line = self._system_line(self.rce, bill)
        line.write({'tipo_cp': '14', 'fecha_vencimiento': False})
        self.rce.action_validate()
        self.assertIn('fecha de vencimiento', line.check_detail)

    def test_cancelled_lines_skip_amount_rules(self):
        invoice = self._make_invoice('out_invoice')
        line = self._system_line(self.rvie, invoice)
        line.write({'estado_cp': '2', 'igv_ipm': 0.0, 'total_cp': 0.0, 'bi_gravada': 5.0})
        self.rvie.action_validate()
        self.assertFalse(line.check_detail)

    def test_observations_block_the_replacement(self):
        invoice = self._make_invoice('out_invoice', document_number='F003-78')
        self._compared(self.rvie, moves=invoice)
        self.rvie.system_line_ids.write({'nro_doc_identidad': '20131312956'})
        with patch.object(type(self.rvie), '_sire_get_token', return_value='tok'), \
                patch.object(type(self.rvie), '_sire_upload') as upload:
            with self.assertRaisesRegex(UserError, 'observaciones'):
                self.rvie.action_send_replacement()
        upload.assert_not_called()
        self.assertFalse(self.rvie.submission_ticket)

    def test_year_must_be_a_tax_period(self):
        with self.assertRaises(ValidationError):
            self.rvie.year = 202

    # ------------------------------------------------------------------
    # Montos: líneas negativas y destino de las compras
    # ------------------------------------------------------------------

    def test_negative_line_subtracts(self):
        """Una deducción (anticipo, descuento) resta de la base, no suma."""
        tax = self._tax('sale')
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_date': PERIOD_DATE,
            'invoice_line_ids': [
                (0, 0, {'name': 'Producto', 'quantity': 1, 'price_unit': 1000.0,
                        'tax_ids': [(6, 0, tax.ids)]}),
                (0, 0, {'name': 'Deducción', 'quantity': 1, 'price_unit': -200.0,
                        'tax_ids': [(6, 0, tax.ids)]}),
            ],
        })
        invoice.action_post()
        line = self._system_line(self.rvie, invoice)
        self.assertAlmostEqual(line.bi_gravada, 800.0, places=2)
        self.assertAlmostEqual(line.igv_ipm, 144.0, places=2)
        self.assertAlmostEqual(line.total_cp, 944.0, places=2)
        self.assertFalse(line.check_detail, line.check_detail)

    def test_line_without_tax_is_not_taxed(self):
        """Sin impuesto la compra es no gravada, no una base gravada sin IGV."""
        bill = self._make_invoice('in_invoice', document_number='F002-38')
        bill.button_draft()
        bill.invoice_line_ids.tax_ids = False
        bill.action_post()
        line = self._system_line(self.rce, bill)
        self.assertAlmostEqual(line.bi_gravada_dg, 0.0, places=2)
        self.assertAlmostEqual(line.valor_adq_ng, 1000.0, places=2)
        self.assertFalse(line.check_detail, line.check_detail)

    def _purchase_tax(self, xmlid):
        tax = self.env.ref('account.%s_%s' % (self.company.id, xmlid), raise_if_not_found=False)
        if not tax:
            self.skipTest('El plan contable de la compañía no tiene %s.' % xmlid)
        return tax

    def test_rce_destination_columns(self):
        g_ng = self._purchase_tax('purchase_tax_igv_18g_ng')
        ng = self._purchase_tax('purchase_tax_igv_18_ng')
        bill = self._make_invoice('in_invoice', document_number='F002-37')
        bill.button_draft()
        bill.write({'invoice_line_ids': [
            (0, 0, {'name': 'Compra mixta', 'quantity': 1, 'price_unit': 500.0,
                    'tax_ids': [(6, 0, g_ng.ids)]}),
            (0, 0, {'name': 'Compra no gravada', 'quantity': 1, 'price_unit': 300.0,
                    'tax_ids': [(6, 0, ng.ids)]}),
        ]})
        bill.action_post()
        line = self._system_line(self.rce, bill)
        self.assertAlmostEqual(line.bi_gravada_dg, 1000.0, places=2)
        self.assertAlmostEqual(line.igv_dg, 180.0, places=2)
        self.assertAlmostEqual(line.bi_gravada_dgng, 500.0, places=2)
        self.assertAlmostEqual(line.igv_dgng, 90.0, places=2)
        self.assertAlmostEqual(line.bi_gravada_dng, 300.0, places=2)
        self.assertAlmostEqual(line.igv_dng, 54.0, places=2)
        self.assertFalse(line.check_detail, line.check_detail)

    # ------------------------------------------------------------------
    # Consulta automática de tickets
    # ------------------------------------------------------------------

    def _requested(self, record):
        record.download_manual = False
        with patch.object(type(record), '_sire_get_token', return_value='tok'), \
                patch.object(type(record), '_sire_request_proposal', return_value='T1'):
            record.action_request_proposal()
        return record

    def _poll(self, record, status, **patches):
        with patch.object(type(record), '_sire_get_token', return_value='tok'), \
                patch.object(type(record), '_sire_ticket_status', return_value=status), \
                patch.object(type(record), '_sire_download_report',
                             return_value=base64.b64encode(b'CABECERA')) as download:
            record._sire_poll_once()
        return download

    def test_request_schedules_the_poll(self):
        self._requested(self.rvie)
        self.assertTrue(self.rvie.poll_next_date)
        self.assertEqual(self.rvie.poll_attempts, 0)
        cron = self.env.ref('al_l10n_pe_sire.ir_cron_sire_rvie_poll')
        trigger = self.env['ir.cron.trigger'].search([('cron_id', '=', cron.id)])
        self.assertIn(self.rvie.poll_next_date, trigger.mapped('call_at'))

    def test_poll_downloads_when_finished(self):
        self._requested(self.rvie)
        download = self._poll(self.rvie, ('06', 'reporte.zip'))
        download.assert_called_once()
        self.assertEqual(self.rvie.state, 'downloaded')
        self.assertTrue(self.rvie.proposal_file)
        self.assertFalse(self.rvie.poll_next_date)

    def test_poll_waits_longer_each_time(self):
        self._requested(self.rce)
        first = self.rce.poll_next_date
        self._poll(self.rce, ('05', ''))
        self.assertEqual(self.rce.poll_attempts, 1)
        self.assertEqual(self.rce.state, 'requested')
        self._poll(self.rce, ('05', ''))
        self.assertEqual(self.rce.poll_attempts, 2)
        self.assertGreater(self.rce.poll_next_date, first + timedelta(minutes=3))

    def test_poll_failure_warns_the_user(self):
        self._requested(self.rvie)
        self._poll(self.rvie, ('00', ''))
        self.assertFalse(self.rvie.poll_next_date)
        self.assertTrue(self.rvie.activity_ids)

    def test_poll_gives_up(self):
        self._requested(self.rvie)
        self.rvie.poll_attempts = SIRE_POLL_MAX_ATTEMPTS - 1
        self._poll(self.rvie, ('05', ''))
        self.assertFalse(self.rvie.poll_next_date)
        self.assertTrue(self.rvie.activity_ids)

    def test_poll_follows_the_submission(self):
        self._compared(self.rvie)
        with patch.object(type(self.rvie), '_sire_get_token', return_value='tok'), \
                patch.object(type(self.rvie), '_sire_accept_proposal', return_value='S1'):
            self.rvie.action_accept_proposal()
        self.assertTrue(self.rvie.poll_next_date)
        self._poll(self.rvie, ('06', ''))
        self.assertEqual(self.rvie.submission_state, '06')
        self.assertFalse(self.rvie.poll_next_date)

    @mute_logger('odoo.addons.al_l10n_pe_sire.models.sire_mixin')
    def test_cron_survives_connection_errors(self):
        self._requested(self.rvie)
        self.rvie.poll_next_date = fields.Datetime.now() - timedelta(minutes=1)
        cron_model = type(self.env['ir.cron'])
        with patch.object(cron_model, '_commit_progress', return_value=1.0), \
                patch.object(type(self.rvie), '_sire_get_token',
                             side_effect=UserError('No se pudo conectar con SUNAT')):
            self.env['l10n_pe.sire.rvie']._cron_sire_poll_tickets()
        self.assertEqual(self.rvie.poll_attempts, 1)
        self.assertGreater(self.rvie.poll_next_date, fields.Datetime.now())


# Los tests heredados de TestSire ya corren en su propia clase: aquí solo se
# reutilizan su preparación y sus utilidades.
for _name in dir(TestSire):
    if _name.startswith('test_') and _name not in TestSireValidation.__dict__:
        setattr(TestSireValidation, _name, None)
