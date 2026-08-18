# -*- coding: utf-8 -*-
"""Formato RCE 8.4 — Registro de Compras.

Contrasta la salida contra la estructura oficial de la RS 040-2022/SUNAT
(anexo 8), documentada en ``docs/tecport/ESTRUCTURA_RCE_8_4_8_5.md``.
"""
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

RUC_COMPANY = '20512528458'
RUC_SUPPLIER = '20601034809'

# Posición (1-based) de los campos que se verifican por nombre
F_RUC, F_ID, F_PERIOD, F_CAR = 1, 2, 3, 4
F_ISSUE_DATE, F_DUE_DATE, F_DOC_TYPE = 5, 6, 7
F_SERIE, F_YEAR, F_NUMBER = 8, 9, 10
F_PARTNER_DOC_TYPE, F_PARTNER_VAT, F_PARTNER_NAME = 12, 13, 14
F_BASE_DG, F_IGV_DG = 15, 16
F_TOTAL, F_CURRENCY, F_RATE = 25, 26, 27
F_CLASSIFICATION = 33
F_DETRACTION, F_NOTE_TYPE, F_STATUS = 38, 39, 40


@tagged('post_install', '-at_install')
class TestRce84(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.vat = RUC_COMPANY
        cls.common = cls.env['l10n_pe.rce.common']
        cls.handler = cls.env['l10n_pe.tax.ple.8.1.report.handler']

    # ------------------------------------------------------------------
    # Serialización y estructura
    # ------------------------------------------------------------------
    def test_line_has_41_fields_and_closing_pipe(self):
        row = ['x'] * 41
        content = self.common._rce_serialize('080400', [row]).decode()
        self.assertTrue(content.endswith('\r\n'),
                        'cada línea debe cerrarse con CRLF')
        line = content.rstrip('\r\n')
        self.assertTrue(line.endswith('|'),
                        'la línea debe terminar en pipe de cierre')
        self.assertEqual(line.count('|'), 41,
                         'el 8.4 tiene 41 campos, luego 41 pipes con el de cierre')

    def test_wrong_field_count_is_rejected(self):
        for size in (38, 40, 42):
            with self.assertRaises(UserError, msg='%d campos debería fallar' % size):
                self.common._rce_serialize('080400', [['x'] * size])

    def test_85_expects_35_fields(self):
        content = self.common._rce_serialize('080500', [['x'] * 35]).decode()
        self.assertEqual(content.rstrip('\r\n').count('|'), 35)
        with self.assertRaises(UserError):
            self.common._rce_serialize('080500', [['x'] * 36])

    def test_empty_book_has_no_content(self):
        self.assertEqual(self.common._rce_serialize('080400', []), b'')

    # ------------------------------------------------------------------
    # Nomenclatura del archivo (Tabla 13 del Anexo 1)
    # ------------------------------------------------------------------
    def test_filename_structure(self):
        name = self.common._rce_filename(
            self.company, '080400', date(2026, 3, 1),
            opportunity='02', has_data=True)
        self.assertEqual(len(name), 33, 'el nombre del RCE tiene 33 caracteres')
        self.assertEqual(name[:2], 'LE')
        self.assertEqual(name[2:13], RUC_COMPANY)
        self.assertEqual(name[13:17], '2026')
        self.assertEqual(name[17:19], '03')
        self.assertEqual(name[19:21], '00', 'el RCE consigna siempre DD=00')
        self.assertEqual(name[21:27], '080400')
        self.assertEqual(name[27:29], '02', 'oportunidad: reemplaza la propuesta')
        self.assertEqual(name[29], '1', 'empresa operativa')
        self.assertEqual(name[30], '1', 'con información')
        self.assertEqual(name[31], '1', 'moneda: soles')
        self.assertEqual(name[32], '2', 'generado por el SIRE')

    def test_filename_flags_no_data(self):
        name = self.common._rce_filename(
            self.company, '080500', date(2026, 1, 1),
            opportunity='00', has_data=False)
        self.assertEqual(name[30], '0', 'sin información')
        self.assertEqual(name[21:27], '080500')
        self.assertEqual(name[27:29], '00')

    def test_filename_marks_usd_bookkeeping(self):
        """Una compañía que lleva contabilidad en dólares marca moneda 2."""
        usd = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
        if not usd:
            self.skipTest('la moneda USD no está disponible')
        company = self.env['res.company'].create({
            'name': 'RCE USD Test',
            'vat': RUC_COMPANY,
            'currency_id': usd.id,
        })
        name = self.common._rce_filename(
            company, '080400', date(2026, 1, 1),
            opportunity='02', has_data=True)
        self.assertEqual(name[31], '2')

    def test_filename_requires_valid_ruc(self):
        """Sin RUC de 11 dígitos el nombre del archivo sería inválido."""
        company = self.env['res.company'].create({'name': 'RCE Sin RUC Test'})
        with self.assertRaises(UserError):
            self.common._rce_filename(
                company, '080400', date(2026, 3, 1),
                opportunity='02', has_data=True)

    # ------------------------------------------------------------------
    # Formato de los campos
    # ------------------------------------------------------------------
    def test_amount_format(self):
        self.assertEqual(self.common._rce_amount(1234.5), '1234.50')
        self.assertEqual(self.common._rce_amount(-253.607), '-253.61')
        self.assertEqual(self.common._rce_amount(0), '0.00')
        self.assertEqual(self.common._rce_amount(None), '0.00')
        self.assertEqual(self.common._rce_amount(-0.001), '0.00',
                         'no debe emitirse «-0.00»')

    def test_rate_format(self):
        self.assertEqual(self.common._rce_rate(3.45, 'USD'), '3.450')
        self.assertEqual(self.common._rce_rate(3.4567, 'USD'), '3.457')
        self.assertEqual(self.common._rce_rate(1.0, 'PEN'), '',
                         'en soles no se informa tipo de cambio')
        self.assertEqual(self.common._rce_rate(0, 'USD'), '')

    def test_date_format(self):
        self.assertEqual(self.common._rce_date(date(2026, 3, 9)), '09/03/2026')
        self.assertEqual(self.common._rce_date(False), '')

    def test_text_is_sanitised(self):
        self.assertEqual(
            self.common._rce_text('EURO|CAPITAL\nS.A.C.', 1500),
            'EURO CAPITAL S.A.C.',
            'el pipe rompería la estructura del archivo')
        self.assertEqual(self.common._rce_text('ABCDEF', 3), 'ABC')
        self.assertEqual(self.common._rce_text(None, 10), '')
