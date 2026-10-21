"""Lectura de archivos de movimientos con las estructuras habituales de la banca
por internet peruana (títulos arriba, monto con signo o cargo y abono, Excel que
en realidad es HTML). Los archivos se arman aquí: no son copias de un banco."""
import datetime
import io

from odoo.tests import BaseCase, tagged

from odoo.addons.al_l10n_pe_bank_statement_import.models.statement_parser import (
    StatementParseError, find_header, parse_amount, parse_date, parse_statement,
)


def xlsx_bytes(rows):
    import openpyxl  # noqa: PLC0415
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    stream = io.BytesIO()
    workbook.save(stream)
    return stream.getvalue()


#: Movimientos con títulos arriba, monto con signo, del más reciente al más antiguo.
SIGNED_ROWS = [
    ['Movimientos de la cuenta'],
    ['Cuenta corriente', '193-0000000-0-00', 'Moneda', 'Soles'],
    [],
    ['Fecha', 'Fecha valuta', 'Descripción operación', 'Monto', 'Saldo', 'Sucursal - agencia',
     'Operación - Número'],
    ['23/10/2026', '23/10/2026', 'PAGO PROVEEDOR ANDINA', -1500.0, 8350.0, '111', '000451'],
    ['22/10/2026', '22/10/2026', 'ABONO CLIENTE NORTE SAC', 2350.5, 9850.0, '111', '000452'],
    ['21/10/2026', '21/10/2026', 'COMISION MANTENIMIENTO', -10.5, 7499.5, '111', '000453'],
    [None, None, 'Total', 840.0],
]

#: CSV con «;», cargo y abono, coma decimal.
DEBIT_CREDIT_CSV = (
    "Estado de cuenta\n"
    "Fecha de operación;Fecha de proceso;Nro. de operación;Descripción;Cargo;Abono;Saldo contable\n"
    "01/10/2026;01/10/2026;778899;TRANSFERENCIA RECIBIDA;;1.250,00;3.250,00\n"
    "02/10/2026;02/10/2026;778900;PAGO DE HABERES;800,00;;2.450,00\n"
    "02/10/2026;02/10/2026;778901;ITF;0,05;;2.449,95\n"
).encode('cp1252')

#: «Excel» descargado que en realidad es una tabla HTML.
HTML_XLS = """<html><body><table>
<tr><td>Consulta de movimientos</td></tr>
<tr><th>F. Operación</th><th>Concepto</th><th>Nº. Doc.</th><th>Importe</th></tr>
<tr><td>05/10/2026</td><td>DEPOSITO EN EFECTIVO</td><td>12345</td><td>S/ 500.00</td></tr>
<tr><td>06/10/2026</td><td>CHEQUE COBRADO</td><td>12346</td><td>S/ -120.00</td></tr>
</table></body></html>""".encode()


@tagged('post_install', '-at_install')
class TestStatementParser(BaseCase):

    def test_values(self):
        cases = {'S/ 1,234.56': 1234.56, '-1,234.56': -1234.56, '1.234,56': 1234.56, '(150.00)': -150.0,
                 '150.00-': -150.0, 'S/ -150.00': -150.0, '': None, 'abc': None, 1500.5: 1500.5}
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(parse_amount(value), expected)
        self.assertEqual(parse_date('21/10/2026 10:15'), datetime.date(2026, 10, 21))
        self.assertEqual(parse_date(datetime.datetime(2026, 10, 21, 8, 0)), datetime.date(2026, 10, 21))
        self.assertIsNone(parse_date('Total'))

    def test_header_below_titles(self):
        index, columns = find_header(SIGNED_ROWS)
        self.assertEqual(index, 3)
        self.assertEqual((columns['date'], columns['description'], columns['amount'], columns['balance'],
                          columns['ref']), (0, 2, 3, 4, 6))

    def test_signed_amount_xlsx(self):
        data = parse_statement(xlsx_bytes(SIGNED_ROWS))
        lines = data['transactions']
        self.assertEqual([line['amount'] for line in lines], [-10.5, 2350.5, -1500.0], 'cronológico')
        self.assertEqual(lines[0]['payment_ref'], 'COMISION MANTENIMIENTO')
        self.assertEqual(lines[0]['ref'], '000453')
        self.assertEqual((data['balance_start'], data['balance_end_real']), (7510.0, 8350.0))
        self.assertEqual((data['date_from'], data['date_to']), (datetime.date(2026, 10, 21), datetime.date(2026, 10, 23)))

    def test_debit_credit_csv(self):
        data = parse_statement(DEBIT_CREDIT_CSV)
        self.assertEqual([line['amount'] for line in data['transactions']], [1250.0, -800.0, -0.05])
        self.assertEqual(data['transactions'][1]['ref'], '778900')
        self.assertEqual((data['balance_start'], data['balance_end_real']), (2000.0, 2449.95))

    def test_html_disguised_as_excel(self):
        data = parse_statement(HTML_XLS)
        self.assertEqual([(line['payment_ref'], line['amount']) for line in data['transactions']],
                         [('DEPOSITO EN EFECTIVO', 500.0), ('CHEQUE COBRADO', -120.0)])
        self.assertEqual(data['transactions'][0]['ref'], '12345')
        self.assertNotIn('balance_start', data, 'sin columna de saldo')

    def test_unique_ids_are_stable_and_distinct(self):
        first = parse_statement(DEBIT_CREDIT_CSV)['transactions']
        again = parse_statement(DEBIT_CREDIT_CSV)['transactions']
        self.assertEqual([l['unique_import_id'] for l in first], [l['unique_import_id'] for l in again])
        twins = parse_statement((
            "Fecha;Descripción;Monto\n03/10/2026;ITF;-0,05\n03/10/2026;ITF;-0,05\n").encode())['transactions']
        self.assertNotEqual(twins[0]['unique_import_id'], twins[1]['unique_import_id'])

    def test_unknown_file_is_refused(self):
        for raw in (b'<?xml version="1.0"?><Document></Document>', b'nombre;edad\nAna;30\n', b''):
            with self.subTest(raw=raw[:20]), self.assertRaises(StatementParseError):
                parse_statement(raw)
