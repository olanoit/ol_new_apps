# -*- coding: utf-8 -*-
import base64
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

RUC_TEST = '20512528458'


@tagged('post_install', '-at_install')
class TestPleExport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        if (cls.company.vat or '') != RUC_TEST and not (
                cls.company.vat and len(cls.company.vat) == 11):
            cls.company.vat = RUC_TEST
        cls.mixin = cls.env['l10n_pe.ple.mixin']
        Account = cls.env['account.account'].with_company(cls.company)
        cls.account_asset = Account.search(
            [('account_type', '=', 'asset_fixed')], limit=1)
        cls.account_dep = Account.search(
            [('account_type', '=', 'asset_fixed'),
             ('id', '!=', cls.account_asset.id)], limit=1)
        cls.account_exp = Account.search(
            [('account_type', '=', 'expense')], limit=1)
        cls.account_inc = Account.search(
            [('account_type', '=', 'income')], limit=1)
        cls.journal = cls.env['account.journal'].search(
            [('company_id', '=', cls.company.id),
             ('type', '=', 'general')], limit=1)
        cls.asset = cls.env['account.asset'].create({
            'name': 'Camioneta PLE Test',
            'original_value': 12000.0,
            'acquisition_date': date(2025, 1, 10),
            'prorata_date': date(2025, 1, 10),
            'method': 'linear',
            'method_number': 5,
            'method_period': '12',
            'account_asset_id': cls.account_asset.id,
            'account_depreciation_id': cls.account_dep.id,
            'account_depreciation_expense_id': cls.account_exp.id,
            'journal_id': cls.journal.id,
            'l10n_pe_ple_code': 'AF-CAM-001',
            'l10n_pe_asset_type': '1',
            'l10n_pe_brand': 'Toyota',
            'l10n_pe_model': 'Hilux',
            'l10n_pe_plate': 'ABC-123',
        })
        cls.asset.write({'state': 'open'})

    def _wizard(self, **kwargs):
        values = {'year': 2025, 'month': '03', 'export_71': False,
                  'export_73': False, 'export_74': False}
        values.update(kwargs)
        return self.env['l10n_pe.ple.export.wizard'].create(values)

    def _get_lines(self, wizard):
        content = base64.b64decode(wizard.file_data).decode()
        return [line for line in content.split('\r\n') if line]

    # ------------------------------------------------------------------
    # Mixin
    # ------------------------------------------------------------------
    def test_amount_format(self):
        self.assertEqual(self.mixin._ple_amount(1234.5), '1234.50')
        self.assertEqual(self.mixin._ple_amount(-5), '-5.00')
        self.assertEqual(self.mixin._ple_amount(-0.0001), '0.00')
        self.assertEqual(self.mixin._ple_amount(0), '0.00')
        self.assertEqual(self.mixin._ple_rate(3.4567), '3.457')

    def test_text_sanitize(self):
        self.assertEqual(
            self.mixin._ple_text('A|B/C\\D\nE', 50), 'A-B-C-D E')
        self.assertEqual(self.mixin._ple_text(None, 5, '-'), '-')
        self.assertEqual(self.mixin._ple_text('X' * 100, 40), 'X' * 40)

    def test_filename(self):
        name = self.mixin._ple_filename(self.company, '070100', 2025)
        ruc = self.company.vat
        self.assertEqual(name, 'LE%s202500000701000011%s1.txt' % (
            ruc, self.mixin._ple_currency_flag(self.company)))
        self.assertEqual(len(name), 33 + len('.txt'))
        # libro anual: el mes se fuerza a 00 aunque se pase otro valor
        name_month = self.mixin._ple_filename(
            self.company, '070100', 2025, month=7)
        self.assertEqual(name, name_month)
        # sin información → indicador I = 0 (LLLLLL CC O I M G)
        name_empty = self.mixin._ple_filename(
            self.company, '070100', 2025, has_data=False)
        self.assertIn('070100' + '00' + '1' + '0', name_empty)

    def test_line_structure_validation(self):
        with self.assertRaises(UserError):
            self.mixin._ple_line('070100', ['a', 'b'])
        line = self.mixin._ple_line('070400', list(range(11)))
        self.assertTrue(self.mixin._ple_check_structure('070400', line))

    # ------------------------------------------------------------------
    # 7.1
    # ------------------------------------------------------------------
    def test_export_71_structure_and_amounts(self):
        wizard = self._wizard(export_71=True)
        wizard.action_export()
        self.assertTrue(wizard.file_name.startswith('LE'))
        self.assertTrue(wizard.file_name.endswith('070100001111.txt')
                        or wizard.file_name.endswith('070100001112.txt'))
        lines = self._get_lines(wizard)
        row = next(f.split('|') for f in lines
                   if 'AF-CAM-001' in f)
        self.assertEqual(len(row), 37)
        self.assertEqual(row[0], '20250000')
        self.assertEqual(row[2], 'M%d' % self.asset.id)
        self.assertEqual(row[7], '1')          # tipo activo (t18)
        self.assertEqual(row[11], 'Toyota')    # marca
        self.assertEqual(row[14], '0.00')      # saldo inicial
        self.assertEqual(row[15], '12000.00')  # adquisiciones del ejercicio
        self.assertEqual(row[25], '1')         # método línea recta
        self.assertEqual(row[27], '20.00')     # % = 100/5 años
        self.assertEqual(row[36], '1')         # estado

    def test_export_71_requires_asset_type(self):
        self.asset.l10n_pe_asset_type = False
        wizard = self._wizard(export_71=True)
        with self.assertRaises(UserError):
            wizard.action_export()

    def test_export_71_with_depreciation_move(self):
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'date': date(2025, 12, 31),
            'journal_id': self.journal.id,
            'asset_id': self.asset.id,
            'line_ids': [
                (0, 0, {'account_id': self.account_exp.id,
                        'debit': 2400.0, 'credit': 0.0}),
                (0, 0, {'account_id': self.account_dep.id,
                        'debit': 0.0, 'credit': 2400.0}),
            ],
        })
        move.action_post()
        wizard = self._wizard(export_71=True)
        wizard.action_export()
        row = next(f.split('|') for f in self._get_lines(wizard)
                   if 'AF-CAM-001' in f)
        self.assertEqual(row[28], '0.00')     # dep. acumulada anterior
        self.assertEqual(row[29], '2400.00')  # dep. del ejercicio

    # ------------------------------------------------------------------
    # 7.4
    # ------------------------------------------------------------------
    def test_export_74(self):
        self.asset.write({
            'l10n_pe_is_leasing': True,
            'l10n_pe_leasing_contract': 'CT-2025-001',
            'l10n_pe_leasing_date': date(2025, 1, 5),
            'l10n_pe_leasing_start': date(2025, 2, 1),
            'l10n_pe_leasing_installments': 36,
            'l10n_pe_leasing_total': 15000.0,
        })
        wizard = self._wizard(export_74=True)
        wizard.action_export()
        self.assertIn('070400', wizard.file_name)
        row = next(f.split('|') for f in self._get_lines(wizard)
                   if 'CT-2025-001' in f)
        self.assertEqual(len(row), 11)
        self.assertEqual(row[4], 'CT-2025-001')
        self.assertEqual(row[5], '05/01/2025')
        self.assertEqual(row[8], '36')
        self.assertEqual(row[9], '15000.00')

    # ------------------------------------------------------------------
    # 7.3
    # ------------------------------------------------------------------
    def test_export_73(self):
        usd = self.env.ref('base.USD')
        usd.active = True
        self.asset.write({
            'l10n_pe_fx_currency_id': usd.id,
            'l10n_pe_fx_amount': 3200.0,
            'l10n_pe_fx_rate': 3.750,
        })
        wizard = self._wizard(export_73=True)
        wizard.action_export()
        self.assertIn('070300', wizard.file_name)
        row = next(f.split('|') for f in self._get_lines(wizard)
                   if 'AF-CAM-001' in f)
        self.assertEqual(len(row), 15)
        self.assertEqual(row[6], '3200.00')
        self.assertEqual(row[7], '3.750')

    # ------------------------------------------------------------------
    # 4.1 — Retenciones
    # ------------------------------------------------------------------
    def test_export_41(self):
        dni_type = self.env['l10n_latam.identification.type'].search(
            [('l10n_pe_vat_code', '=', '1')], limit=1)
        partner = self.env['res.partner'].create({
            'name': 'Juan Pérez Test',
            'l10n_latam_identification_type_id': dni_type.id,
            'vat': '46779810',
        })
        record = self.env['l10n_pe.ple.withholding'].create({
            'date': date(2025, 3, 15),
            'partner_id': partner.id,
            'gross_amount': 5000.0,
            'withheld_amount': 400.0,
        })
        # fuera del mes exportado: no debe aparecer
        self.env['l10n_pe.ple.withholding'].create({
            'date': date(2025, 4, 2),
            'partner_id': partner.id,
            'gross_amount': 100.0,
        })
        wizard = self._wizard(export_41=True)
        wizard.action_export()
        # libro mensual: MM=03 en el nombre
        self.assertIn('202503', wizard.file_name)
        self.assertIn('040100', wizard.file_name)
        lines = self._get_lines(wizard)
        self.assertEqual(len(lines), 1)
        row = lines[0].split('|')
        self.assertEqual(len(row), 10)
        self.assertEqual(row[0], '20250300')
        self.assertEqual(row[2], 'M%d' % record.id)
        self.assertEqual(row[3], '15/03/2025')
        self.assertEqual(row[4], '1')          # DNI (tabla 2)
        self.assertEqual(row[5], '46779810')
        self.assertEqual(row[7], '5000.00')
        self.assertEqual(row[8], '-400.00')    # retención en negativo
        self.assertEqual(row[9], '1')

    # ------------------------------------------------------------------
    # 9.1 — Consignaciones (consignador)
    # ------------------------------------------------------------------
    def test_export_91(self):
        from datetime import datetime
        product = self.env['product.product'].create({
            'name': 'Producto Consignado Test',
            'type': 'consu',
            'default_code': 'CONS-001',
            'l10n_pe_type_of_existence': '1',
        })
        ruc_type = self.env['l10n_latam.identification.type'].search(
            [('l10n_pe_vat_code', '=', '6')], limit=1)
        partner = self.env['res.partner'].create({
            'name': 'Consignatario SAC',
            'l10n_latam_identification_type_id': ruc_type.id,
            'vat': '20131312955',
        })
        picking_type = self.env['stock.picking.type'].search(
            [('code', '=', 'outgoing'),
             ('company_id', '=', self.company.id)], limit=1)
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'partner_id': partner.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id':
                picking_type.default_location_dest_id.id
                or self.env.ref('stock.stock_location_customers').id,
            'l10n_pe_consignment': 'out_delivery',
            'move_ids': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': 5.0,
                'product_uom': product.uom_id.id,
                'location_id': picking_type.default_location_src_id.id,
                'location_dest_id':
                    picking_type.default_location_dest_id.id
                    or self.env.ref('stock.stock_location_customers').id,
            })],
        })
        picking.move_ids.write({
            'state': 'done', 'date': datetime(2025, 3, 10, 12, 0)})
        picking.write({'state': 'done'})
        wizard = self._wizard(export_91=True)
        wizard.action_export()
        self.assertIn('090100', wizard.file_name)
        lines = self._get_lines(wizard)
        row = next(f.split('|') for f in lines if 'CONS-001' in f)
        self.assertEqual(len(row), 22)
        self.assertEqual(row[0], '20250300')
        self.assertEqual(row[1], '9')           # catálogo propio
        self.assertEqual(row[2], '01')          # tipo existencia (t5)
        self.assertEqual(row[16], '20131312955')  # RUC consignatario
        self.assertEqual(row[18], '5.00')       # cantidad entregada
        self.assertEqual(row[19], '0.00')
        self.assertEqual(row[20], '0.00')
        self.assertEqual(row[21], '1')

    # ------------------------------------------------------------------
    # 3.8 — Inversiones mobiliarias
    # ------------------------------------------------------------------
    def test_export_38(self):
        record = self.env['l10n_pe.ple.investment'].create({
            'date': date(2025, 12, 31),
            'issuer_name': 'Minera Andina S.A.A.',
            'title_code': '1',
            'nominal_value': 10.0,
            'quantity': 500,
            'book_cost': 5500.0,
            'provision': 300.0,
        })
        wizard = self._wizard(
            export_38=True, balance_date=date(2025, 12, 31))
        wizard.action_export()
        # libro 3: día y oportunidad en el nombre
        self.assertIn('20251231', wizard.file_name)
        self.assertIn('03080001', wizard.file_name)
        lines = self._get_lines(wizard)
        row = next(f.split('|') for f in lines
                   if 'Minera Andina' in f)
        self.assertEqual(len(row), 12)
        self.assertEqual(row[0], '20251231')
        self.assertEqual(row[2], 'M%d' % record.id)
        self.assertEqual(row[3], '0')          # emisor sin documento
        self.assertEqual(row[6], '01')         # título con zfill
        self.assertEqual(row[8], '500')
        self.assertEqual(row[10], '-300.00')   # provisión en negativo
        self.assertEqual(row[11], '1')

    # ------------------------------------------------------------------
    # 3.9 — Intangibles (cta. 34)
    # ------------------------------------------------------------------
    def test_export_39(self):
        account_34 = self.env['account.account'].with_company(
            self.company).create({
                'code': '349999',
                'name': 'Intangibles PLE Test',
                'account_type': 'asset_non_current',
            })
        intangible = self.env['account.asset'].create({
            'name': 'Licencia ERP Test',
            'original_value': 8000.0,
            'acquisition_date': date(2024, 6, 1),
            'prorata_date': date(2024, 6, 1),
            'method': 'linear',
            'method_number': 4,
            'method_period': '12',
            'account_asset_id': account_34.id,
            'account_depreciation_id': self.account_dep.id,
            'account_depreciation_expense_id': self.account_exp.id,
            'journal_id': self.journal.id,
        })
        intangible.write({'state': 'open'})
        wizard = self._wizard(
            export_39=True, balance_date=date(2025, 12, 31))
        wizard.action_export()
        self.assertIn('030900', wizard.file_name)
        row = next(f.split('|') for f in self._get_lines(wizard)
                   if 'Licencia ERP' in f)
        self.assertEqual(len(row), 9)
        self.assertEqual(row[0], '20251231')
        self.assertEqual(row[3], '01/06/2024')
        self.assertEqual(row[4], '349999')
        self.assertEqual(row[6], '8000.00')
        self.assertEqual(row[8], '1')
        # el activo del setUp (cuenta de activo fijo, no 34) no aparece
        self.assertFalse([f for f in self._get_lines(wizard)
                          if 'Camioneta' in f])

    # ------------------------------------------------------------------
    # 3.19 — Cambios en el patrimonio neto
    # ------------------------------------------------------------------
    def test_export_319(self):
        rubric = self.env['l10n_pe_reports_lib.financial.rubric'].search(
            [], limit=1)
        self.env['l10n_pe.ple.equity'].create({
            'date': date(2025, 12, 31),
            'rubric_id': rubric.id,
            'capital': 100000.0,
            'retained_earnings': 2500.0,
            'net_result': -1200.0,
        })
        wizard = self._wizard(
            export_319=True, balance_date=date(2025, 12, 31))
        wizard.action_export()
        self.assertIn('031900', wizard.file_name)
        lines = self._get_lines(wizard)
        self.assertEqual(len(lines), 1)
        row = lines[0].split('|')
        self.assertEqual(len(row), 16)
        self.assertEqual(row[2], rubric.name[:6])
        self.assertEqual(row[3], '100000.00')   # capital
        self.assertEqual(row[9], '2500.00')     # resultados acumulados
        self.assertEqual(row[12], '-1200.00')   # resultado neto
        self.assertEqual(row[15], '1')

    # ------------------------------------------------------------------
    # Libro 10 — Registro de Costos
    # ------------------------------------------------------------------
    def test_export_101(self):
        self.env['l10n_pe.ple.cost.sales'].create({
            'year': 2025,
            'initial_finished': 10000.0,
            'production_cost': 50000.0,
            'final_finished': 8000.0,
            'adjustments': 150.0,
        })
        wizard = self._wizard(export_101=True)
        wizard.action_export()
        # libro anual: MM=00 en el nombre
        self.assertIn('20250000100100', wizard.file_name)
        lines = self._get_lines(wizard)
        self.assertEqual(len(lines), 1)
        row = lines[0].split('|')
        self.assertEqual(len(row), 6)
        self.assertEqual(row[0], '20250000')
        self.assertEqual(row[1], '10000.00')
        self.assertEqual(row[3], '-8000.00')   # inventario final en negativo
        self.assertEqual(row[5], '1')

    def test_export_102(self):
        for month, materials in (('02', 300.0), ('01', 200.0)):
            self.env['l10n_pe.ple.cost.element'].create({
                'year': 2025, 'month': month,
                'direct_materials': materials,
                'direct_labor': 100.0,
            })
        wizard = self._wizard(export_102=True)
        wizard.action_export()
        self.assertIn('100200', wizard.file_name)
        lines = self._get_lines(wizard)
        self.assertEqual(len(lines), 2)
        first, second = lines[0].split('|'), lines[1].split('|')
        self.assertEqual(len(first), 8)
        # ordenado por mes dentro del archivo anual
        self.assertEqual(first[0], '20250100')
        self.assertEqual(first[1], '200.00')
        self.assertEqual(second[0], '20250200')
        self.assertEqual(second[1], '300.00')

    def test_export_103_104(self):
        self.env['l10n_pe.ple.cost.production'].create({
            'year': 2025,
            'process_code': 'PR-01',
            'process_name': 'Proceso de ensamblaje',
            'direct_materials': 1000.0,
            'initial_wip': 500.0,
            'final_wip': 200.0,
            'grouping_code': '1',
        })
        center = self.env['l10n_pe.ple.cost.center'].create({
            'year': 2025,
            'cost_center_code': 'CC-100',
            'cost_center_name': 'Planta Lima',
        })
        wizard = self._wizard(export_103=True, export_104=True)
        wizard.action_export()
        self.assertTrue(wizard.file_name.endswith('.zip'))
        import io
        import zipfile
        archive = zipfile.ZipFile(
            io.BytesIO(base64.b64decode(wizard.file_data)))
        names = archive.namelist()
        content_103 = next(archive.read(n).decode() for n in names
                           if '100300' in n)
        row = next(f.split('|') for f in content_103.split('\r\n')
                   if 'PR-01' in f)
        self.assertEqual(len(row), 13)
        self.assertEqual(row[1], 'PR-01')
        self.assertEqual(row[10], '-200.00')   # inv. final en proceso (−)
        self.assertEqual(row[11], '1')         # agrupamiento t21
        content_104 = next(archive.read(n).decode() for n in names
                           if '100400' in n)
        row = next(f.split('|') for f in content_104.split('\r\n')
                   if 'CC-100' in f)
        self.assertEqual(len(row), 7)
        self.assertEqual(row[1], str(center.id))
        self.assertEqual(row[4], 'CC-100')
        self.assertEqual(row[6], '1')

    # ------------------------------------------------------------------
    # Formatos simplificados (5.2 / 5.4 / 8.3 / 14.2)
    # ------------------------------------------------------------------
    def _make_invoice(self, move_type, tax_type):
        journal_type = 'sale' if move_type == 'out_invoice' else 'purchase'
        journal = self.env['account.journal'].create({
            'name': 'PLE Simpl %s' % journal_type,
            'code': 'PS%s' % journal_type[0].upper(),
            'type': journal_type,
            'company_id': self.company.id,
            'l10n_latam_use_documents': False,
        })
        tax = self.env['account.tax'].search([
            ('company_id', '=', self.company.id),
            ('type_tax_use', '=', tax_type),
            ('amount', '=', 18.0),
            ('amount_type', '=', 'percent'),
        ], limit=1)
        partner = self.env['res.partner'].create({
            'name': 'Contraparte Simplificada SAC',
            'vat': '20131312955',
        })
        invoice = self.env['account.move'].create({
            'move_type': move_type,
            'partner_id': partner.id,
            'journal_id': journal.id,
            'invoice_date': date(2025, 3, 20),
            'date': date(2025, 3, 20),
            'ref': 'F001-00000123',
            'invoice_line_ids': [(0, 0, {
                'name': 'Servicio simplificado',
                'quantity': 1.0,
                'price_unit': 100.0,
                'account_id': (self.account_inc.id
                               if move_type == 'out_invoice'
                               else self.account_exp.id),
                'tax_ids': [(6, 0, tax.ids)] if tax else False,
            })],
        })
        invoice.action_post()
        return invoice, tax

    def test_export_simplified_requires_flag(self):
        self.company.l10n_pe_ple_simplified = False
        wizard = self._wizard(export_142=True)
        with self.assertRaises(UserError):
            wizard.action_export()

    def test_export_142(self):
        self.company.l10n_pe_ple_simplified = True
        invoice, tax = self._make_invoice('out_invoice', 'sale')
        wizard = self._wizard(export_142=True)
        wizard.action_export()
        self.assertIn('140200', wizard.file_name)
        row = next(f.split('|') for f in self._get_lines(wizard)
                   if 'M%d' % invoice.id in f.split('|'))
        self.assertEqual(len(row), 26)
        self.assertEqual(row[0], '20250300')
        self.assertEqual(row[3], '20/03/2025')
        self.assertEqual(row[10], '20131312955')
        if tax:
            self.assertEqual(row[12], '100.00')   # BI gravada
            self.assertEqual(row[13], '18.00')    # IGV
            self.assertEqual(row[16], '118.00')   # total
        self.assertEqual(row[17], 'PEN')
        self.assertEqual(row[18], '')             # TC vacío en soles
        self.assertEqual(row[25], '1')

    def test_export_83(self):
        self.company.l10n_pe_ple_simplified = True
        invoice, tax = self._make_invoice('in_invoice', 'purchase')
        wizard = self._wizard(export_83=True)
        wizard.action_export()
        self.assertIn('080300', wizard.file_name)
        row = next(f.split('|') for f in self._get_lines(wizard)
                   if 'M%d' % invoice.id in f.split('|'))
        self.assertEqual(len(row), 32)
        self.assertEqual(row[6], 'F001')          # serie del ref
        self.assertEqual(row[7], '00000123')      # folio del ref
        if tax:
            self.assertEqual(row[16], '118.00')   # total
        self.assertEqual(row[31], '1')

    def test_export_52_54(self):
        self.company.l10n_pe_ple_simplified = True
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'date': date(2025, 3, 25),
            'journal_id': self.journal.id,
            'ref': 'Asiento diario simplificado',
            'line_ids': [
                (0, 0, {'account_id': self.account_exp.id,
                        'debit': 750.0, 'credit': 0.0}),
                (0, 0, {'account_id': self.account_dep.id,
                        'debit': 0.0, 'credit': 750.0}),
            ],
        })
        move.action_post()
        wizard = self._wizard(export_52=True, export_54=True)
        wizard.action_export()
        self.assertTrue(wizard.file_name.endswith('.zip'))
        import io
        import zipfile
        archive = zipfile.ZipFile(
            io.BytesIO(base64.b64decode(wizard.file_data)))
        names = archive.namelist()
        content_52 = next(archive.read(n).decode() for n in names
                          if '050200' in n)
        rows = [f.split('|') for f in content_52.split('\r\n')
                if f and f.split('|')[1] == str(move.id)]
        self.assertEqual(len(rows), 2)            # dos apuntes del asiento
        row = rows[0]
        self.assertEqual(len(row), 21)
        self.assertEqual(row[0], '20250300')
        self.assertEqual(row[6], 'PEN')
        debits = sorted((r[17], r[18]) for r in rows)
        self.assertIn(('0.00', '750.00'), debits)
        self.assertIn(('750.00', '0.00'), debits)
        self.assertEqual(row[20], '1')
        content_54 = next(archive.read(n).decode() for n in names
                          if '050400' in n)
        first = content_54.split('\r\n')[0].split('|')
        self.assertEqual(len(first), 8)
        self.assertEqual(first[0], '20250301')
        self.assertEqual(first[3], '01')          # plan PCGE (t17)

    # ------------------------------------------------------------------
    # Varios formatos → ZIP
    # ------------------------------------------------------------------
    def test_export_zip(self):
        self.asset.write({
            'l10n_pe_is_leasing': True,
            'l10n_pe_leasing_contract': 'CT-2025-001',
            'l10n_pe_leasing_date': date(2025, 1, 5),
        })
        wizard = self._wizard(export_71=True, export_74=True)
        wizard.action_export()
        self.assertTrue(wizard.file_name.endswith('.zip'))
