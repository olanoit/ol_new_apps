# -*- coding: utf-8 -*-
"""Archivo de depósito masivo de detracciones del Banco de la Nación.

El banco rechaza el lote completo si una sola línea no mide lo que debe, así
que la prueba central es la de longitudes y posiciones.
"""
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.al_l10n_pe_detraction.services import bn_txt


@tagged('post_install', '-at_install')
class TestBnTxt(TransactionCase):

    # ------------------------------------------------------------------
    # Formato de campo
    # ------------------------------------------------------------------
    def test_text_pads_and_truncates(self):
        self.assertEqual(bn_txt.text('ABC', 5), 'ABC  ')
        self.assertEqual(bn_txt.text('ABCDEFG', 3), 'ABC')
        self.assertEqual(bn_txt.text(None, 4), '    ')

    def test_number_keeps_last_digits(self):
        self.assertEqual(bn_txt.number('20512528458', 11), '20512528458')
        self.assertEqual(bn_txt.number('123', 8), '00000123')
        self.assertEqual(bn_txt.number('F001-00012345678', 8), '12345678',
                         'de un número largo se toman los últimos 8 dígitos')
        self.assertEqual(bn_txt.number('', 3), '000')

    def test_amount_has_no_decimal_point(self):
        self.assertEqual(bn_txt.amount(1234.56), '000000000123456')
        self.assertEqual(bn_txt.amount(700), '000000000070000')
        self.assertEqual(bn_txt.amount(0), '000000000000000')
        self.assertEqual(len(bn_txt.amount(1)), 15)

    def test_amount_rounds_to_cents(self):
        self.assertEqual(bn_txt.amount(10.005), '000000000001001')
        self.assertEqual(bn_txt.amount(-50.0), '000000000005000',
                         'el importe se escribe siempre en positivo')

    def test_period_format(self):
        self.assertEqual(bn_txt.period(date(2026, 3, 9)), '202603')
        self.assertEqual(bn_txt.period(False), '      ')

    # ------------------------------------------------------------------
    # Cabecera
    # ------------------------------------------------------------------
    def test_header_length_and_positions(self):
        header = bn_txt.build_header(
            bn_txt.MASTER_ACQUIRER, '20512528458', 'SERVICIOS ANDINOS S.A.C.',
            '260001', 1500.0)
        self.assertEqual(len(header), 68)
        self.assertEqual(header[0], '*', 'posición 1: indicador de maestra')
        self.assertEqual(header[1:12], '20512528458', 'posiciones 2-12: RUC')
        self.assertEqual(header[12:47].strip(), 'SERVICIOS ANDINOS S.A.C.')
        self.assertEqual(header[47:53], '260001', 'posiciones 48-53: lote')
        self.assertEqual(header[53:68], '000000000150000',
                         'posiciones 54-68: importe total')

    def test_header_supplier_mode(self):
        header = bn_txt.build_header(
            bn_txt.MASTER_SUPPLIER, '20512528458', 'X', '260002', 0)
        self.assertEqual(header[0], 'P')
        self.assertEqual(len(header), 68)

    def test_header_truncates_long_name(self):
        header = bn_txt.build_header(
            bn_txt.MASTER_ACQUIRER, '20512528458', 'A' * 60, '260001', 1)
        self.assertEqual(len(header), 68)
        self.assertEqual(header[12:47], 'A' * 35)

    # ------------------------------------------------------------------
    # Detalle
    # ------------------------------------------------------------------
    def _detail(self, **kwargs):
        values = {
            'doc_type': bn_txt.DOC_TYPE_RUC,
            'vat': '20601034809',
            'name': '',
            'service_code': '022',
            'bank_account': '00071234567',
            'deposit': 120.0,
            'operation_type': '01',
            'tax_period': '202603',
            'invoice_type': '01',
            'invoice_serie': 'F001',
            'invoice_number': '2644',
        }
        values.update(kwargs)
        return bn_txt.build_detail(**values)

    def test_detail_length_and_positions(self):
        line = self._detail()
        self.assertEqual(len(line), 107)
        self.assertEqual(line[0], '6', 'posición 1: tipo de documento (RUC)')
        self.assertEqual(line[1:12], '20601034809', 'posiciones 2-12: RUC')
        self.assertEqual(line[12:47], ' ' * 35,
                         'posiciones 13-47: el nombre va en blanco')
        self.assertEqual(line[47:56], ' ' * 9, 'posiciones 48-56: proforma')
        self.assertEqual(line[56:59], '022', 'posiciones 57-59: bien/servicio')
        self.assertEqual(line[59:70], '00071234567', 'posiciones 60-70: cuenta')
        self.assertEqual(line[70:85], '000000000012000',
                         'posiciones 71-85: importe del depósito')
        self.assertEqual(line[85:87], '01', 'posiciones 86-87: tipo operación')
        self.assertEqual(line[87:93], '202603', 'posiciones 88-93: periodo')
        self.assertEqual(line[93:95], '01', 'posiciones 94-95: tipo comprobante')
        self.assertEqual(line[95:99], 'F001', 'posiciones 96-99: serie')
        self.assertEqual(line[99:107], '00002644',
                         'posiciones 100-107: número')

    def test_detail_keeps_length_with_long_values(self):
        line = self._detail(invoice_serie='ABCDEFG', invoice_number='1234567890')
        self.assertEqual(len(line), 107)
        self.assertEqual(line[99:107], '34567890',
                         'un número largo se recorta a los últimos 8 dígitos')

    # ------------------------------------------------------------------
    # Archivo completo
    # ------------------------------------------------------------------
    def test_build_file_uses_crlf(self):
        header = bn_txt.build_header(
            bn_txt.MASTER_ACQUIRER, '20512528458', 'X', '260001', 120.0)
        content = bn_txt.build_file(header, [self._detail()])
        self.assertTrue(content.endswith('\r\n'))
        self.assertEqual(len(content.split('\r\n')[0]), 68)
        self.assertEqual(len(content.split('\r\n')[1]), 107)

    def test_check_structure_accepts_valid_file(self):
        header = bn_txt.build_header(
            bn_txt.MASTER_ACQUIRER, '20512528458', 'X', '260001', 120.0)
        content = bn_txt.build_file(header, [self._detail(), self._detail()])
        self.assertEqual(bn_txt.check_structure(content), [])

    def test_check_structure_detects_problems(self):
        self.assertTrue(bn_txt.check_structure(''))
        self.assertTrue(bn_txt.check_structure('X' * 68 + '\r\n'),
                        'la cabecera debe empezar por * o P')
        header = bn_txt.build_header(
            bn_txt.MASTER_ACQUIRER, '20512528458', 'X', '260001', 0)
        problems = bn_txt.check_structure(header + '\r\n' + 'corta\r\n')
        self.assertTrue(any('línea 1' in problem for problem in problems))
