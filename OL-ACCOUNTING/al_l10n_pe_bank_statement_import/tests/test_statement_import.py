"""Importación desde el diario: extracto reconocido directo, sin duplicados; el
resto sigue el importador nativo."""
from odoo.tests import TransactionCase, tagged

from odoo.addons.al_account_base.tests.common import use_pe_company

from .test_statement_parser import DEBIT_CREDIT_CSV, SIGNED_ROWS, xlsx_bytes


@tagged('post_install', '-at_install')
class TestStatementImport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        cls.company = cls.env.company
        # Cuenta transitoria propia: la de la compañía puede tener moneda fija en la base de pruebas.
        suspense = cls.env['account.account'].create({
            'name': 'Transitoria (prueba extractos)', 'code': '109199', 'account_type': 'asset_current'})
        cls.journal = cls.env['account.journal'].create({
            'name': 'Banco extractos', 'code': 'BKEX', 'type': 'bank', 'company_id': cls.company.id,
            'suspense_account_id': suspense.id})

    def _attachment(self, raw, name):
        return self.env['ir.attachment'].create({'name': name, 'raw': raw})

    def _lines(self):
        return self.env['account.bank.statement.line'].search([('journal_id', '=', self.journal.id)],
                                                               order='date, id')

    def test_xlsx_is_imported_without_mapping(self):
        action = self.journal._import_bank_statement(self._attachment(xlsx_bytes(SIGNED_ROWS), 'movimientos.xlsx'))
        self.assertNotEqual(action.get('tag'), 'import_bank_stmt', 'sin el mapeo de columnas nativo')
        lines = self._lines()
        self.assertEqual(lines.mapped('amount'), [-10.5, 2350.5, -1500.0])
        self.assertEqual(lines[0].payment_ref, 'COMISION MANTENIMIENTO')
        statement = lines.statement_id
        self.assertEqual(len(statement), 1)
        self.assertEqual((statement.balance_start, statement.balance_end_real), (7510.0, 8350.0))
        self.assertTrue(statement.is_complete, 'los saldos del banco cuadran con los movimientos')

    def test_reimport_does_not_duplicate(self):
        self.journal._import_bank_statement(self._attachment(DEBIT_CREDIT_CSV, 'estado.csv'))
        self.assertEqual(len(self._lines()), 3)
        try:
            self.journal._import_bank_statement(self._attachment(DEBIT_CREDIT_CSV, 'estado (1).csv'))
        except Exception:  # noqa: BLE001 - el nativo avisa que no hay movimientos nuevos
            pass
        self.assertEqual(len(self._lines()), 3)

    def test_unrecognized_csv_goes_to_native_mapping(self):
        action = self.journal._import_bank_statement(self._attachment(b'col1;col2\na;b\n', 'otro.csv'))
        self.assertEqual(action.get('tag'), 'import_bank_stmt')
