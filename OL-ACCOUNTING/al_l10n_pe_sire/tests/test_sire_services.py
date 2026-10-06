"""Servicios SIRE de las fases 1 a 6: reportes, tipo de cambio, no domiciliados,
complementos, ajustes posteriores y eliminaciones.

Ninguna prueba sale a SUNAT: se fija lo que se enviaría (endpoint, metadatos,
nombre y columnas del archivo) contra los manuales y anexos oficiales
(``docs/sire/SERVICIOS_*.md`` y ``docs/sire/ESTRUCTURAS_TXT.md``).
"""
import base64
import io
import json
import zipfile
from unittest.mock import MagicMock, patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.al_l10n_pe_sire.models.sire_api import (
    SIRE_UPLOAD_ADJUSTMENT_ENDPOINT, SIRE_UPLOAD_ENDPOINT, SIRE_UPLOAD_PRELIMINARY_ENDPOINT,
)

from .test_sire import PERIOD_MONTH, PERIOD_YEAR, RUC_TEST, TestSire

PERIOD = '%s%s' % (PERIOD_YEAR, PERIOD_MONTH)

CAR = '20131312955010F00200000000034'


def _response(content=b'', json_data=None, status=200, text=None):
    response = MagicMock(status_code=status, content=content, headers={})
    response.text = text if text is not None else (
        json.dumps(json_data) if json_data is not None else content.decode('latin-1'))
    response.json.side_effect = (lambda: json_data) if json_data is not None else ValueError
    return response


@tagged('post_install', '-at_install')
class TestSireServices(TestSire):

    def setUp(self):
        super().setUp()
        for record in (self.rvie, self.rce):
            patcher = patch.object(type(record), '_sire_get_token', return_value='tok')
            patcher.start()
            self.addCleanup(patcher.stop)

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def _upload(self, call, **kwargs):
        """Ejecuta ``call`` con la subida TUS simulada; devuelve (resultado, llamada)."""
        with patch.object(type(self.rvie), '_sire_upload', return_value='20260700000001') as rvie, \
                patch.object(type(self.rce), '_sire_upload', return_value='20260700000002') as rce:
            result = call()
        upload = rvie if rvie.called else rce
        self.assertTrue(upload.called, 'no se subió nada')
        return result, upload.call_args

    @staticmethod
    def _rows(call_args):
        token, filename, payload, metadata = call_args.args[:4]
        archive = zipfile.ZipFile(io.BytesIO(payload))
        txt = archive.namelist()[0]
        return filename, txt, [row.split('|') for row in archive.read(txt).decode().split('\n')]

    def _done(self, record):
        record.write({'state': 'done', 'preliminary_registered': True})
        return record

    def _proposal_line(self, record, **vals):
        model = record.sire_line_ids._name
        values = {'sire_id': record.id, 'type_line': 'sire', 'car_sunat': CAR,
                  'tipo_cp': '01', 'serie_cp': 'F002', 'nro_cp': '34', 'moneda': 'PEN'}
        values.update(vals)
        return self.env[model].create(values)

    # ------------------------------------------------------------------
    # Fase 1: tickets, reportes, constancia, inconsistencias
    # ------------------------------------------------------------------

    def test_tus_ticket_comes_as_plain_text(self):
        """Manual v22: la carga TUS devuelve el ticket en texto plano."""
        api = self.env['l10n_pe.sire.api']
        self.assertEqual(api._sire_ticket_from(_response(text='20230100000124')), '20230100000124')
        self.assertEqual(api._sire_ticket_from(_response(text='"20230100000124"')), '20230100000124')
        self.assertEqual(api._sire_ticket_from(_response(json_data={'numTicket': 'X1'})), 'X1')
        self.assertEqual(api._sire_ticket_from(_response(text='OK')), '')

    def test_report_type_keeps_the_manual_typo(self):
        api = self.env['l10n_pe.sire.api']
        self.assertEqual(api._sire_report_type({'codTipoAchivoReporte': '01'}), '01')
        self.assertEqual(api._sire_report_type({'codTipoAchivoReporte': None}), 'null')

    def test_reports_are_attached_once(self):
        register = {'numTicket': 'T1', 'archivoReporte': [
            {'nomArchivoReporte': 'inconsistencias.zip', 'codTipoAchivoReporte': '01'},
            {'nomArchivoReporte': 'resumen.zip', 'codTipoAchivoReporte': None}]}
        with patch.object(type(self.rce), '_sire_download_file', return_value=b'PK..') as download:
            first = self.rce._sire_attach_reports('tok', register)
            second = self.rce._sire_attach_reports('tok', register)
        self.assertEqual(sorted(first.mapped('name')), ['inconsistencias.zip', 'resumen.zip'])
        self.assertFalse(second, 'no se duplican')
        self.assertEqual(download.call_args_list[0].args[2], '080000')

    def test_finished_submission_attaches_its_reports(self):
        self.rvie.write({'submission_ticket': 'S1', 'submission_state': '01', 'state': 'submitted'})
        register = {'detalleTicket': {'codEstadoEnvio': '03'},
                    'archivoReporte': [{'nomArchivoReporte': 'errores.txt'}]}
        with patch.object(type(self.rvie), '_sire_ticket_register', return_value=register), \
                patch.object(type(self.rvie), '_sire_download_file', return_value=b'error'):
            self.rvie.action_check_submission()
        self.assertEqual(self.rvie.submission_state, '03')
        self.assertTrue(self.env['ir.attachment'].search([
            ('res_model', '=', 'l10n_pe.sire.rvie'), ('res_id', '=', self.rvie.id),
            ('name', '=', 'errores.txt')]))

    def test_operation_poll_downloads_reports(self):
        operation = self.rce._sire_new_operation('non_domiciled', ticket='20260700000009')
        self.assertTrue(operation.poll_next_date)
        register = {'detalleTicket': {'codEstadoEnvio': '06', 'cntCPError': 0},
                    'archivoReporte': [{'nomArchivoReporte': 'nd.zip'}]}
        with patch.object(type(self.rce), '_sire_ticket_register', return_value=register), \
                patch.object(type(self.rce), '_sire_download_file', return_value=b'PK'):
            operation.action_check()
        self.assertEqual(operation.state, 'done')
        self.assertEqual(operation.report_ids.name, 'nd.zip')
        self.assertFalse(operation.poll_next_date)

    def test_operation_with_errors_warns(self):
        operation = self.rce._sire_new_operation('complement', ticket='20260700000010')
        register = {'detalleTicket': {'codEstadoEnvio': '03'}, 'archivoReporte': []}
        with patch.object(type(self.rce), '_sire_ticket_register', return_value=register):
            operation.action_check()
        self.assertEqual(operation.state, 'error')
        self.assertTrue(self.rce.activity_ids)

    def test_operation_keeps_polling(self):
        operation = self.rce._sire_new_operation('complement', ticket='20260700000011')
        register = {'detalleTicket': {'codEstadoEnvio': '05'}}
        with patch.object(type(self.rce), '_sire_ticket_register', return_value=register):
            operation.action_check()
        self.assertEqual(operation.state, 'sent')
        self.assertEqual(operation.poll_attempts, 1)

    @mute_logger('odoo.addons.al_l10n_pe_sire.models.sire_operation')
    def test_operation_cron_survives_errors(self):
        operation = self.rce._sire_new_operation('complement', ticket='20260700000012')
        operation.poll_next_date = fields.Datetime.now()
        with patch.object(type(self.env['ir.cron']), '_commit_progress', return_value=1.0), \
                patch.object(type(self.rce), '_sire_ticket_register',
                             side_effect=UserError('sin conexión')):
            self.env['l10n_pe.sire.operation']._cron_sire_poll_operations()
        self.assertEqual(operation.poll_attempts, 1)

    def test_receipt_tries_the_official_names(self):
        self._done(self.rce)
        pdf = b'%PDF-1.5 constancia'
        calls = []

        def receipt(token, name):
            calls.append(name)
            if len(calls) < 3:
                raise UserError('no existe')
            return _response(json_data={'archivoPdf': list(pdf)})
        with patch.object(type(self.rce), '_sire_receipt_request', side_effect=receipt):
            operation = self.rce.action_sire_receipt()
        self.assertEqual(calls[0], 'LE%s%s00080400011112.pdf' % (RUC_TEST, PERIOD))
        self.assertEqual(operation.report_ids.raw, pdf)
        self.assertEqual(self.rce.receipt_name, calls[2])

    def test_receipt_base64_rvie(self):
        self._done(self.rvie)
        pdf = b'%PDF-1.4 rvie'
        response = _response(json_data={'archivoPdf': base64.b64encode(pdf).decode()})
        with patch.object(type(self.rvie), '_sire_receipt_request', return_value=response):
            operation = self.rvie.action_sire_receipt()
        self.assertEqual(operation.report_ids.raw, pdf)

    def test_receipt_not_found(self):
        self._done(self.rvie)
        with patch.object(type(self.rvie), '_sire_receipt_request',
                          side_effect=UserError('no existe')):
            with self.assertRaisesRegex(UserError, 'constancia'):
                self.rvie.action_sire_receipt()

    def test_inconsistency_summary_asks_the_four_types(self):
        data = {'cantidad': {'total': 5, 'porcentajeRelFiscal': 20}, 'monto': {'total': 100}}
        with patch.object(type(self.rce), '_sire_inconsistency_summary_request',
                          return_value=_response(json_data=data)) as request:
            operation = self.rce.action_sire_inconsistency_summary()
        self.assertEqual([c.args[1] for c in request.call_args_list], ['1', '2', '3', '4'])
        self.assertEqual(operation.detail.count('5 CP'), 4)

    # ------------------------------------------------------------------
    # Fase 2: tipo de cambio
    # ------------------------------------------------------------------

    def test_rvie_exchange_rates_json(self):
        rates = [(PERIOD_DATE_OBJ, 'USD', 3.745)]
        with patch.object(type(self.rvie), '_sire_send_json', return_value=_response(text='')) as send:
            self.rvie._sire_send_exchange_rates(rates)
        method, token, endpoint, payload = send.call_args.args[:4]
        self.assertEqual(method, 'POST')
        self.assertEqual(endpoint, '/libros/rvie/propuesta/web/masivo/%s/guardacomplementomasivo'
                         % PERIOD)
        self.assertEqual(payload, [{'fecEmision': '2026-07-15', 'codMoneda': 'USD',
                                    'mtoTipoCambio': '3.745'}])

    def test_rce_exchange_rates_file(self):
        rates = [(PERIOD_DATE_OBJ, 'USD', 3.745)]
        with patch.object(type(self.rce), '_sire_request',
                          return_value=_response(text='20260700000003')) as request:
            operation = self.rce._sire_send_exchange_rates(rates)
        name, content, mimetype = request.call_args.kwargs['files']['archivo']
        self.assertEqual(name, '%s-RCETCA-%s-01.txt' % (RUC_TEST, PERIOD))
        self.assertEqual(content.decode(), '%s|15/07/2026|USD|3.745|' % PERIOD)
        self.assertIn('/080000/resumenfechatipocambio', request.call_args.args[2])
        self.assertEqual(operation.ticket, '20260700000003')

    def test_exchange_rates_need_foreign_currency(self):
        self.rvie.action_load_system()
        with patch.object(type(self.rvie), '_sire_exchange_rates', return_value=[]):
            with self.assertRaisesRegex(UserError, 'moneda extranjera'):
                self.rvie.action_sire_send_exchange_rates()

    # ------------------------------------------------------------------
    # Fase 3: no domiciliados
    # ------------------------------------------------------------------

    def _nd_bill(self, **move_vals):
        partner = self.env['res.partner'].create({
            'name': 'Cloud Services Inc', 'vat': '98-7654321', 'street': '1 Main St',
            'country_id': self.env.ref('base.us').id,
        })
        doc_type = self.env['l10n_latam.document.type'].search([
            ('code', '=', '91'), ('country_id.code', '=', 'PE')], limit=1)
        vals = {
            'move_type': 'in_invoice', 'partner_id': partner.id,
            'invoice_date': PERIOD_DATE_OBJ,
            'l10n_latam_document_type_id': doc_type.id,
            'l10n_latam_document_number': 'INV-2026001',
            'invoice_line_ids': [(0, 0, {'name': 'Licencia', 'quantity': 1, 'price_unit': 500.0,
                                         'tax_ids': [(6, 0, [])]})],
            'l10n_pe_sire_nd_income_type': '18',
            'l10n_pe_sire_nd_agreement': '00',
        }
        vals.update(move_vals)
        bill = self.env['account.move'].create(vals)
        bill.action_post()
        return bill

    def test_non_domiciled_bill_leaves_the_rce(self):
        bill = self._nd_bill()
        self.assertTrue(bill.l10n_pe_sire_is_non_domiciled)
        self.assertNotIn(bill, self.rce._sire_system_moves())
        self.assertIn(bill, self.rce._sire_nd_moves())

    def test_non_domiciled_row(self):
        bill = self._nd_bill(l10n_pe_sire_nd_gross_income=500.0,
                             l10n_pe_sire_nd_withholding_rate=30.0,
                             l10n_pe_sire_nd_withheld_tax=150.0)
        with patch.object(type(self.rce), '_sire_nd_moves', return_value=bill):
            self.rce.action_sire_load_nd()
        line = self.rce.nd_line_ids
        self.assertFalse(line.check_detail, line.check_detail)
        row = self.rce._sire_nd_row(line)
        self.assertEqual(len(row), 35)
        self.assertEqual(row[0], PERIOD)
        self.assertEqual(row[3], '91')
        self.assertEqual(row[5], '2026001')
        self.assertEqual(row[16], '9249', 'Estados Unidos, tabla 16')
        self.assertEqual(row[17], 'Cloud Services Inc')
        self.assertEqual(row[24], '500.00')
        self.assertEqual(row[26], '500.00', 'renta neta = bruta - deducción')
        self.assertEqual(row[29], '00')
        self.assertEqual(row[31], '18')
        self.assertEqual(row[34], '')

    def test_non_domiciled_requires_income_type(self):
        bill = self._nd_bill(l10n_pe_sire_nd_income_type=False)
        with patch.object(type(self.rce), '_sire_nd_moves', return_value=bill):
            self.rce.action_sire_load_nd()
        self.assertIn('tipo de renta', self.rce.nd_line_ids.check_detail)
        self.rce.submission_ticket = 'S1'
        with self.assertRaisesRegex(UserError, 'observaciones'):
            self.rce.action_sire_send_nd()

    def test_non_domiciled_upload(self):
        bill = self._nd_bill()
        with patch.object(type(self.rce), '_sire_nd_moves', return_value=bill):
            self.rce.action_sire_load_nd()
        with self.assertRaisesRegex(UserError, 'aceptar la propuesta'):
            self.rce.action_sire_send_nd()
        self.rce.submission_ticket = 'S1'
        operation, call = self._upload(self.rce.action_sire_send_nd)
        filename, txt, rows = self._rows(call)
        self.assertEqual(txt, 'LE%s%s00080500001112.txt' % (RUC_TEST, PERIOD))
        self.assertEqual(filename, txt.replace('.txt', '.zip'))
        self.assertEqual(call.args[3]['codProceso'], '56')
        self.assertEqual(call.kwargs['endpoint'], SIRE_UPLOAD_PRELIMINARY_ENDPOINT)
        self.assertEqual(len(rows[0]), 35)
        self.assertEqual(operation.kind, 'non_domiciled')
        self.assertTrue(operation.file)

    def test_country_codes_loaded(self):
        self.assertEqual(self.env.ref('base.pe').l10n_pe_sire_country_code, '9589')
        self.assertEqual(self.env.ref('base.es').l10n_pe_sire_country_code, '9245')

    # ------------------------------------------------------------------
    # Fase 4: complementos, incluir/excluir y nuevos CP
    # ------------------------------------------------------------------

    def test_exclude_and_include(self):
        line = self._proposal_line(self.rce)
        operation, call = self._upload(line.action_sire_exclude)
        filename, txt, rows = self._rows(call)
        self.assertEqual(txt, '%s-RCEINEX-%s-01.txt' % (RUC_TEST, PERIOD))
        self.assertEqual(call.args[3]['codProceso'], '55')
        self.assertEqual(call.kwargs['endpoint'], SIRE_UPLOAD_ENDPOINT)
        self.assertEqual(len(rows[0]), 37)
        self.assertEqual((rows[0][3], rows[0][36]), (CAR, '1'))
        self.assertEqual(set(rows[0][:3] + rows[0][4:36]), {''})
        operation, call = self._upload(line.action_sire_include)
        filename, txt, rows = self._rows(call)
        self.assertTrue(txt.endswith('-02.txt'), 'correlativo')
        self.assertEqual(rows[0][36], '2')

    def test_credit_notes_cannot_be_excluded(self):
        line = self._proposal_line(self.rce, tipo_cp='07')
        with self.assertRaisesRegex(UserError, 'notas de crédito'):
            line.action_sire_exclude()

    def test_complement_relocates_with_system_data(self):
        bill = self._make_invoice('in_invoice', document_number='F002-34')
        bill.l10n_pe_sire_goods_class = '2'
        with patch.object(type(self.rce), '_sire_system_moves', return_value=bill):
            self.rce.action_load_system()
        system = self.rce.system_line_ids
        line = self._proposal_line(self.rce, car_sunat=system.car_sunat,
                                   bi_gravada_dg=1000.0, igv_dg=180.0)
        operation, call = self._upload(line.action_sire_complement)
        filename, txt, rows = self._rows(call)
        self.assertEqual(txt, '%s-RCECOM-%s-01.txt' % (RUC_TEST, PERIOD))
        self.assertEqual(call.args[3]['codProceso'], '54')
        row = rows[0]
        self.assertEqual(row[3], system.car_sunat)
        self.assertEqual((row[14], row[15]), ('1000.00', '180.00'))
        self.assertEqual(row[32], '2', 'clasificación de bienes')
        self.assertEqual(row[0], '', 'el RUC no va en la variante A')

    def test_complement_refuses_different_amounts(self):
        bill = self._make_invoice('in_invoice', document_number='F002-34')
        with patch.object(type(self.rce), '_sire_system_moves', return_value=bill):
            self.rce.action_load_system()
        line = self._proposal_line(self.rce, car_sunat=self.rce.system_line_ids.car_sunat,
                                   bi_gravada_dg=900.0)
        with self.assertRaisesRegex(UserError, 'no suma'):
            line.action_sire_complement()

    def test_new_cp_to_the_proposal(self):
        invoice = self._make_invoice('out_invoice')
        with patch.object(type(self.rvie), '_sire_system_moves', return_value=invoice):
            self.rvie.action_load_system()
        operation, call = self._upload(self.rvie.system_line_ids.action_sire_add_to_proposal)
        filename, txt, rows = self._rows(call)
        self.assertEqual(txt, '%s-CPF-%s-01.txt' % (RUC_TEST, PERIOD))
        self.assertEqual(call.args[3]['codProceso'], '1')
        self.assertEqual(len(rows[0]), 33)
        bill = self._make_invoice('in_invoice', document_number='F009-1')
        with patch.object(type(self.rce), '_sire_system_moves', return_value=bill):
            self.rce.action_load_system()
        operation, call = self._upload(self.rce.system_line_ids.action_sire_add_to_proposal)
        filename, txt, rows = self._rows(call)
        self.assertEqual(txt, '%s-CP-%s-01.txt' % (RUC_TEST, PERIOD))
        self.assertEqual(len(rows[0]), 37)

    def test_new_cp_to_the_preliminary_needs_a_replacement(self):
        bill = self._make_invoice('in_invoice', document_number='F009-2')
        with patch.object(type(self.rce), '_sire_system_moves', return_value=bill):
            self.rce.action_load_system()
        with self.assertRaisesRegex(UserError, 'reemplazar'):
            self.rce.system_line_ids.action_sire_add_to_preliminary()
        self.rce.submission_type = 'replace'
        operation, call = self._upload(self.rce.system_line_ids.action_sire_add_to_preliminary)
        filename, txt, rows = self._rows(call)
        self.assertEqual(txt, 'LE%s%s00080400021112.txt' % (RUC_TEST, PERIOD))
        self.assertEqual(call.args[3]['codProceso'], '4')
        self.assertEqual(call.kwargs['endpoint'], SIRE_UPLOAD_PRELIMINARY_ENDPOINT)

    def test_invalid_lines_are_not_sent(self):
        bill = self._make_invoice('in_invoice', document_number='F009-3')
        with patch.object(type(self.rce), '_sire_system_moves', return_value=bill):
            self.rce.action_load_system()
        self.rce.system_line_ids.nro_doc_identidad = '20131312956'
        with patch.object(type(self.rce), '_sire_upload') as upload:
            with self.assertRaisesRegex(UserError, 'observaciones'):
                self.rce.system_line_ids.action_sire_add_to_proposal()
        upload.assert_not_called()

    # ------------------------------------------------------------------
    # Fase 5: ajustes posteriores
    # ------------------------------------------------------------------

    def test_rvie_adjustment(self):
        invoice = self._make_invoice('out_invoice')
        with patch.object(type(self.rvie), '_sire_system_moves', return_value=invoice):
            self.rvie.action_load_system()
        system = self.rvie.system_line_ids
        with self.assertRaisesRegex(UserError, 'ya generado'):
            system.action_sire_send_adjustment()
        self._done(self.rvie)
        self._proposal_line(self.rvie, car_sunat=system.car_sunat)
        operation, call = self._upload(system.action_sire_send_adjustment)
        filename, txt, rows = self._rows(call)
        self.assertEqual(txt, 'LE%s%s0014040003111201.txt' % (RUC_TEST, PERIOD))
        self.assertEqual(call.args[3]['codProceso'], '6')
        self.assertEqual(call.kwargs['endpoint'], SIRE_UPLOAD_ADJUSTMENT_ENDPOINT)
        self.assertEqual(len(rows[0]), 34)
        self.assertEqual(rows[0][33], system.car_sunat, 'CAR del anotado (campo 41)')
        self.assertEqual(operation.adjustment_kind, 'adjustment')

    def test_rce_adjustment_and_send(self):
        bill = self._make_invoice('in_invoice', document_number='F002-34')
        with patch.object(type(self.rce), '_sire_system_moves', return_value=bill):
            self.rce.action_load_system()
        self._done(self.rce)
        system = self.rce.system_line_ids
        with patch.object(type(self.rce), '_sire_upload', return_value='') as upload:
            operation = system.action_sire_send_adjustment()
        filename, txt, rows = self._rows(upload.call_args)
        self.assertEqual(txt, 'LE%s%s0008040003111201.txt' % (RUC_TEST, PERIOD))
        self.assertFalse(upload.call_args.kwargs['ticket_required'], '5.18 responde «OK»')
        self.assertEqual(rows[0][36], '', 'sin CAR: comprobante nuevo')
        self.assertTrue(operation.can_send_adjustment)
        with patch.object(type(self.rce), '_sire_send_json',
                          return_value=_response(text='"OK"')) as send:
            operation.action_send_adjustment()
        method, token, endpoint, body = send.call_args.args[:4]
        self.assertEqual(endpoint, '/libros/rce/ajustesposteriores/web/comprobantesajuspost/'
                                   '%s/2/registrarajustesposterioresrc' % PERIOD)
        self.assertEqual(body['controlProcesos']['lisFases'][0]['codFase'], '9')
        self.assertTrue(operation.adjustment_sent)

    def test_nd_adjustment_needs_its_number(self):
        bill = self._nd_bill()
        with patch.object(type(self.rce), '_sire_nd_moves', return_value=bill):
            self.rce.action_sire_load_nd()
        self._done(self.rce)
        line = self.rce.nd_line_ids
        line.car_sunat = 'X' * 27
        operation, call = self._upload(line.action_sire_send_nd_adjustment)
        filename, txt, rows = self._rows(call)
        self.assertEqual(txt, 'LE%s%s0008050003111201.txt' % (RUC_TEST, PERIOD))
        self.assertEqual(call.args[3]['codProceso'], '60')
        self.assertEqual(rows[0][34], 'X' * 27)
        operation.state = 'done'
        with patch.object(type(self.rce), '_sire_find_adjustment_number', return_value=''):
            with self.assertRaisesRegex(UserError, 'número de ajuste'):
                self.rce._sire_send_adjustment(operation)
        operation.adjustment_number = '3'
        with patch.object(type(self.rce), '_sire_send_json', return_value=_response(text='OK')) as send:
            self.rce._sire_send_adjustment(operation)
        self.assertTrue(send.call_args.args[2].endswith(
            '/3/080000/%s/registrarajustesposterioresrcnd' % operation.ticket))
        self.assertEqual(send.call_args.args[3]['controlProcesos']['lisFases'][0]['codFase'], '10')

    def test_previous_period_adjustments(self):
        self._done(self.rvie)
        self._done(self.rce)
        old_date = fields.Date.to_date('2023-05-10')
        invoice = self._make_invoice('out_invoice', invoice_date=old_date)
        bill = self._make_invoice('in_invoice', document_number='F002-99', invoice_date=old_date)
        wizard = self.env['l10n_pe.sire.action.wizard'].create({
            'res_model': self.rvie._name, 'res_id': self.rvie.id,
            'action': 'adjust_previous', 'adjust_state': '8',
            'move_ids': [(6, 0, (invoice | bill).ids)]})
        with patch.object(type(self.rvie), '_sire_upload', return_value='T1') as upload:
            wizard.action_apply()
        filename, txt, rows = self._rows(upload.call_args)
        self.assertEqual(txt, 'LE%s%s0014040004111201.txt' % (RUC_TEST, PERIOD))
        self.assertEqual(upload.call_args.args[3]['codProceso'], '7')
        self.assertEqual(len(rows), 1, 'solo los comprobantes de ventas')
        self.assertEqual(len(rows[0]), 35)
        self.assertEqual((rows[0][0], rows[0][34]), ('20230500', '8'))
        wizard = self.env['l10n_pe.sire.action.wizard'].create({
            'res_model': self.rce._name, 'res_id': self.rce.id,
            'action': 'adjust_previous', 'move_ids': [(6, 0, bill.ids)]})
        with patch.object(type(self.rce), '_sire_upload', return_value='T2') as upload:
            wizard.action_apply()
        filename, txt, rows = self._rows(upload.call_args)
        self.assertEqual(txt, 'LE%s%s0008040004111201.txt' % (RUC_TEST, PERIOD))
        self.assertEqual(len(rows[0]), 42)
        self.assertEqual((rows[0][0], rows[0][41]), ('20230500', '9'))
        self.assertEqual(rows[0][23], '1180.00', 'total = suma de los campos 14 a 23')

    # ------------------------------------------------------------------
    # Fase 6: eliminaciones y crédito fiscal
    # ------------------------------------------------------------------

    def test_delete_from_proposal(self):
        line = self._proposal_line(self.rce)
        with patch.object(type(self.rce), '_sire_send_json', return_value=_response(text='"OK"')) as send:
            line.action_sire_delete_from_proposal()
        method, token, endpoint, payload = send.call_args.args[:4]
        self.assertEqual((method, endpoint), ('DELETE', '/libros/rce/propuesta/web/propuestarce/%s'
                                                        % PERIOD))
        self.assertEqual(payload, [{'codCar': CAR, 'codTipoCDP': '01', 'numSerieCDP': 'F002',
                                    'numCDP': '34'}])
        line = self._proposal_line(self.rvie, car_sunat='2051252845801F00100000000012')
        with patch.object(type(self.rvie), '_sire_send_json', return_value=_response(text='"OK"')) as send:
            line.action_sire_withdraw()
        self.assertEqual(send.call_args.kwargs['params'],
                         {'codCar': '2051252845801F00100000000012', 'codSituacion': '0'})

    def test_deletions_are_for_managers(self):
        line = self._proposal_line(self.rce)
        user = self.env['res.users'].create({
            'name': 'Contable SIRE', 'login': 'contable_sire_services',
            'group_ids': [(6, 0, [self.env.ref('account.group_account_user').id])],
        })
        with self.assertRaisesRegex(UserError, 'responsable'):
            line.with_user(user).action_sire_delete_from_proposal()

    def test_fiscal_credit_and_prorrata(self):
        wizard = self.env['l10n_pe.sire.action.wizard'].create({
            'res_model': self.rce._name, 'res_id': self.rce.id,
            'action': 'fiscal_prorrata', 'value': 0.75})
        with patch.object(type(self.rce), '_sire_send_json', return_value=_response(text='"OK"')) as send:
            wizard.action_apply()
        method, token, endpoint, payload = send.call_args.args[:4]
        self.assertEqual((method, endpoint), ('PUT', '/libros/rce/propuesta/web/%s/grabacreditofiscal'
                                                     % PERIOD))
        self.assertEqual(payload, {'registros': {'factProrrata': 0.75}})
        self.assertEqual(self.rce.operation_ids.kind, 'fiscal_credit')

    def test_wizard_deletions_need_confirmation(self):
        wizard = self.env['l10n_pe.sire.action.wizard'].create({
            'res_model': self.rce._name, 'res_id': self.rce.id, 'action': 'delete_registered'})
        with self.assertRaisesRegex(UserError, 'Confirme'):
            wizard.action_apply()
        wizard.confirm = True
        self.rce.preliminary_registered = True
        with patch.object(type(self.rce), '_sire_send_json', return_value=_response(text='"OK"')) as send:
            wizard.action_apply()
        self.assertEqual(send.call_args.args[2],
                         '/libros/rce/preliminar/web/registroslibros/%s/1/eliminapreliminar' % PERIOD)
        self.assertFalse(self.rce.preliminary_registered)

    def test_wizard_rejects_actions_of_the_other_book(self):
        with self.assertRaises(UserError):
            self.env['l10n_pe.sire.action.wizard'].create({
                'res_model': self.rvie._name, 'res_id': self.rvie.id, 'action': 'fiscal_prorrata'})


PERIOD_DATE_OBJ = fields.Date.to_date('2026-07-15')

# Los tests heredados de TestSire ya corren en su propia clase.
for _name in dir(TestSire):
    if _name.startswith('test_') and _name not in TestSireServices.__dict__:
        setattr(TestSireServices, _name, None)
