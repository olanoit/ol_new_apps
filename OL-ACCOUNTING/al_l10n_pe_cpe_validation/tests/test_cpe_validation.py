# -*- coding: utf-8 -*-
"""Consulta integrada de comprobantes de SUNAT, con respuestas simuladas."""
from unittest.mock import patch

from stdnum.pe import ruc as stdnum_ruc

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..services import sunat_cpe

SERVICE = 'odoo.addons.al_l10n_pe_cpe_validation.services.sunat_cpe'


def _ruc(body):
    return body + stdnum_ruc.calc_check_digit(body)


class FakeResponse:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


@tagged('post_install', '-at_install')
class TestCpeValidation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        if cls.company.account_fiscal_country_id.code != 'PE':
            cls.skipTest(cls, 'La compañía de prueba no es peruana')
        cls.company.root_id.sudo().write({
            'l10n_pe_cpe_client_id': 'cid-test', 'l10n_pe_cpe_client_secret': 'secret-test',
            'l10n_pe_cpe_token': False, 'l10n_pe_cpe_token_expiry': False})
        cls.company.l10n_pe_cpe_post_mode = 'none'
        cls.vendor = cls.env['res.partner'].create({
            'name': 'PROVEEDOR CPE (test)', 'country_id': cls.env.ref('base.pe').id,
            'vat': _ruc('2060112233'),
        })
        cls.journal = cls.env['account.journal'].search([
            ('type', '=', 'purchase'), ('company_id', '=', cls.company.id)], limit=1)
        cls.invoice_type = cls.env.ref('l10n_pe.document_type01')

    def _bill(self, number='F001-00000123', doc_type=None, post=False, date='2026-10-01'):
        move = self.env['account.move'].create({
            'move_type': 'in_invoice', 'partner_id': self.vendor.id,
            'journal_id': self.journal.id, 'invoice_date': date,
            'l10n_latam_document_type_id': (doc_type or self.invoice_type).id,
            'l10n_latam_document_number': number,
            'invoice_line_ids': [(0, 0, {'name': 'Servicio', 'quantity': 1, 'price_unit': 1000.0,
                                         'tax_ids': [(6, 0, [])]})],
        })
        if post:
            move.action_post()
        return move

    def _respond(self, cp='1', ruc='00', dom='00', notes=None, calls=None):
        def fake_post(url, data=None, json=None, headers=None, timeout=None):
            if calls is not None:
                calls.append((url, data, json, headers))
            if 'oauth2/token' in url:
                return FakeResponse(200, {'access_token': 'tok-1', 'expires_in': 3600})
            return FakeResponse(200, {'success': True, 'message': 'Operation Success! ',
                                      'data': {'estadoCp': cp, 'estadoRuc': ruc,
                                               'condDomiRuc': dom,
                                               'observaciones': notes or []}})
        return patch(SERVICE + '.requests.post', side_effect=fake_post)

    def test_query_values_follow_the_manual(self):
        move = self._bill()
        values = move._l10n_pe_cpe_query_values()
        self.assertEqual(values, {
            'numRuc': self.vendor.vat, 'codComp': '01', 'numeroSerie': 'F001', 'numero': 123,
            'fechaEmision': '01/10/2026', 'monto': '%.2f' % move.amount_total})
        # Comprobante físico (serie numérica): sin monto.
        self.assertNotIn('monto', self._bill(number='0001-456')._l10n_pe_cpe_query_values())

    def test_valid_invoice_and_token_reuse(self):
        calls = []
        move = self._bill()
        with self._respond(calls=calls):
            move.action_l10n_pe_cpe_validate()
            move.action_l10n_pe_cpe_validate()
        self.assertEqual(move.l10n_pe_cpe_result, 'valid')
        self.assertEqual(move.l10n_pe_cpe_doc_state, '1')
        self.assertTrue(move.l10n_pe_cpe_checked_on)
        token_calls = [c for c in calls if 'oauth2/token' in c[0]]
        self.assertEqual(len(token_calls), 1, 'el token se reutiliza mientras está vigente')
        self.assertEqual(token_calls[0][1]['grant_type'], 'client_credentials')
        self.assertEqual(token_calls[0][1]['scope'], sunat_cpe.SCOPE)
        query = [c for c in calls if 'validarcomprobante' in c[0]][0]
        self.assertIn(self.company.root_id.vat, query[0])
        self.assertEqual(query[3]['Authorization'], 'Bearer tok-1')

    def test_observed_and_invalid(self):
        observed, invalid = self._bill(), self._bill(number='F001-00000124')
        with self._respond(cp='1', dom='12'):
            observed.action_l10n_pe_cpe_validate()
        with self._respond(cp='0', notes=['Comprobante no informado']):
            invalid.action_l10n_pe_cpe_validate()
        self.assertEqual(observed.l10n_pe_cpe_result, 'observed')
        self.assertEqual(observed.l10n_pe_cpe_domicile, '12')
        self.assertEqual(invalid.l10n_pe_cpe_result, 'invalid')
        self.assertIn('no informado', invalid.l10n_pe_cpe_message)

    def test_block_on_post(self):
        self.company.l10n_pe_cpe_post_mode = 'block'
        move = self._bill()
        with self._respond(cp='2'), self.assertRaises(UserError):
            move.action_post()
        self.assertEqual(move.state, 'draft')
        valid = self._bill(number='F001-00000125')
        with self._respond(cp='1'):
            valid.action_post()
        self.assertEqual(valid.state, 'posted')

    def test_warn_on_post_and_service_error_does_not_block(self):
        self.company.l10n_pe_cpe_post_mode = 'warn'
        move = self._bill()
        with self._respond(cp='0'):
            move.action_post()
        self.assertEqual(move.state, 'posted')
        self.assertIn('Consulta en SUNAT', move.message_ids[0].body)
        self.company.l10n_pe_cpe_post_mode = 'block'
        other = self._bill(number='F001-00000126')
        with patch(SERVICE + '.requests.post',
                   return_value=FakeResponse(500, {'success': False, 'message': 'Error'})):
            other.action_post()
        self.assertEqual(other.state, 'posted', 'sin respuesta de SUNAT no se bloquea')
        self.assertIn('No se pudo consultar', other.message_ids[0].body)

    def test_fee_receipt_uses_r1_and_bad_credentials(self):
        fee_type = self.env['l10n_latam.document.type'].search(
            [('code', '=', '02'), ('country_id.code', '=', 'PE')], limit=1)
        if fee_type:
            move = self._bill(number='E001-15', doc_type=fee_type)
            self.assertEqual(move._l10n_pe_cpe_query_values()['codComp'], 'R1')
        move = self._bill()
        with patch(SERVICE + '.requests.post',
                   return_value=FakeResponse(401, {'error': 'invalid_client'})), \
                self.assertRaises(UserError):
            move.action_l10n_pe_cpe_validate()

    def test_not_applicable_is_skipped(self):
        move = self._bill()
        move.l10n_latam_document_number = 'SINGUION'
        with self._respond():
            action = move.action_l10n_pe_cpe_validate()
        self.assertFalse(move.l10n_pe_cpe_result)
        self.assertIn('no se consultó', action['params']['message'])

    def test_cron_checks_unchecked_bills(self):
        move = self._bill(post=True, date=fields.Date.context_today(self.env['account.move']))
        with self._respond():
            self.env['account.move']._cron_l10n_pe_cpe_validate()
        self.assertEqual(move.l10n_pe_cpe_result, 'valid')
