# -*- coding: utf-8 -*-
"""Auditoría del 07/10/2026: un valor del archivo que empieza por «=» no se
escribe como fórmula en el reporte de resultados."""
import openpyxl

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestImportFormulaInjection(TransactionCase):

    def test_user_value_is_written_as_text(self):
        mixin = type(self.env['al.import.payroll.mixin'])
        ws = openpyxl.Workbook().active
        cell = ws.cell(row=1, column=1, value='=HYPERLINK("http://x","clic")')
        self.assertEqual(cell.data_type, 'f')
        mixin._as_text(cell)
        self.assertEqual(cell.data_type, 's')
