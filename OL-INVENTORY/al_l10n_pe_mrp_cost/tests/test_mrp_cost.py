# -*- coding: utf-8 -*-
import io
from datetime import date, datetime, timedelta

from dateutil.relativedelta import relativedelta
from openpyxl import Workbook

from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import Form, tagged
from odoo.tools import BinaryBytes


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestMrpCost(AccountTestInvoicingCommon):
    """Costeo de órdenes de fabricación.

    Orden de 2 mesas: 4 tableros a 10 (40), una operación de 2 h en un centro
    de 30 por hora (máquina 60) y 2 h de un operario a 10 por hora (mano de
    obra 20). En el mes, el costo hora real del operario es 15 (ajuste 10) y
    la bolsa de CIF tiene 300.
    """

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.env.user.group_ids |= cls.env.ref('mrp.group_mrp_manager') | cls.env.ref('hr.group_hr_user') \
            | cls.env.ref('stock.group_stock_manager') | cls.env.ref('mrp.group_mrp_routings') \
            | cls.env.ref('hr_payroll.group_hr_payroll_manager')
        cls.categ = cls.env['product.category'].create({
            'name': 'Muebles AVCO', 'property_cost_method': 'average', 'property_valuation': 'real_time',
        })
        cls.board = cls.env['product.product'].create({
            'name': 'Tablero melamina', 'is_storable': True, 'categ_id': cls.categ.id, 'standard_price': 10.0,
        })
        cls.table = cls.env['product.product'].create({
            'name': 'Mesa de centro', 'is_storable': True, 'categ_id': cls.categ.id,
            'weight': 12.0, 'volume': 0.5,
        })
        cls.workcenter = cls.env['mrp.workcenter'].create({
            'name': 'Seccionadora', 'code': 'SEC', 'costs_hour': 30.0, 'company_id': cls.company.id,
        })
        cls.bom = cls.env['mrp.bom'].create({
            'product_tmpl_id': cls.table.product_tmpl_id.id,
            'product_qty': 1.0,
            'bom_line_ids': [Command.create({'product_id': cls.board.id, 'product_qty': 2.0})],
            'operation_ids': [Command.create({
                'name': 'Corte', 'workcenter_id': cls.workcenter.id, 'time_cycle_manual': 60.0,
            })],
        })
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Juan Pérez', 'identification_id': '45678912', 'company_id': cls.company.id,
            'hourly_cost': 10.0,
        })
        cls.stock = cls.env['stock.warehouse'].search([('company_id', '=', cls.company.id)], limit=1).lot_stock_id
        cls.env['stock.quant']._update_available_quantity(cls.board, cls.stock, 100.0)
        cls.account_71 = cls._pe_account('71')
        cls.account_63 = cls._pe_account('63')
        cls.company.l10n_pe_mrp_labor_account_id = cls.account_71
        today = fields.Date.context_today(cls.env.user)
        cls.month_start = today.replace(day=1)
        cls.month_end = cls.month_start + relativedelta(months=1, days=-1)

    @classmethod
    def _pe_account(cls, prefix):
        return cls.env['account.account'].search([
            ('company_ids', 'in', cls.company.id), ('code', '=like', f'{prefix}%'),
        ], order='code', limit=1)

    def _produce(self, qty=2.0, hours=2.0):
        mo_form = Form(self.env['mrp.production'])
        mo_form.product_id = self.table
        mo_form.bom_id = self.bom
        mo_form.product_qty = qty
        production = mo_form.save()
        production.action_confirm()
        workorder = production.workorder_ids
        start = datetime.now() - timedelta(hours=hours + 1)
        self.env['mrp.workcenter.productivity'].create({
            'workorder_id': workorder.id,
            'workcenter_id': workorder.workcenter_id.id,
            'employee_id': self.employee.id,
            'loss_id': self.env.ref('mrp.block_reason7').id,
            'date_start': start,
            'date_end': start + timedelta(hours=hours),
        })
        production.qty_producing = qty
        production.move_raw_ids.picked = True
        production.button_mark_done()
        self.assertEqual(production.state, 'done')
        return production

    def _applied_rate(self, hourly_cost):
        return self.env['l10n_pe.mrp.labor.rate'].create({
            'date_from': self.month_start,
            'date_to': self.month_end,
            'state': 'applied',
            'line_ids': [Command.create({
                'employee_id': self.employee.id, 'payroll_cost': hourly_cost * 100, 'hours': 100.0,
            })],
        })

    def _overhead(self, amount=300.0, basis='hours'):
        pool = self.env['l10n_pe.mrp.cost.pool'].create({
            'name': 'Gastos de planta', 'account_prefixes': '63', 'split_basis': basis,
            'counterpart_account_id': self.account_71.id,
        })
        entry = self.env['account.move'].create({
            'move_type': 'entry',
            'date': self.month_start,
            'line_ids': [
                Command.create({'account_id': self.account_63.id, 'debit': amount}),
                Command.create({'account_id': self.company_data['default_account_payable'].id, 'credit': amount}),
            ],
        })
        entry.action_post()
        return pool

    def _close(self):
        close = self.env['l10n_pe.mrp.cost.close'].create({
            'date_from': self.month_start, 'date_to': self.month_end,
        })
        close.action_compute()
        return close

    # ------------------------------------------------------------------
    def test_close_labor_and_overhead(self):
        production = self._produce()
        self._applied_rate(15.0)
        self._overhead(300.0)
        finished = production.move_finished_ids.filtered(lambda m: m.product_id == self.table)
        value_before = finished.value
        close = self._close()
        labor = close.line_ids.filtered(lambda l: l.element == 'labor')
        overhead = close.line_ids.filtered(lambda l: l.element == 'overhead')
        self.assertAlmostEqual(labor.amount, 10.0)
        self.assertAlmostEqual(overhead.amount, 300.0)
        close.action_validate()
        self.assertEqual(close.state, 'done')
        self.assertEqual(close.landed_cost_id.state, 'done')
        self.assertAlmostEqual(finished.value, value_before + 310.0, places=2)
        credit_71 = close.landed_cost_id.account_move_id.line_ids.filtered(
            lambda l: l.account_id == self.account_71)
        self.assertAlmostEqual(sum(credit_71.mapped('credit')), 310.0, places=2)

    def test_overhead_split_by_quantity(self):
        first = self._produce(qty=1.0)
        second = self._produce(qty=3.0)
        self._overhead(400.0, basis='quantity')
        close = self._close()
        overhead = {l.production_id: l.amount for l in close.line_ids if l.element == 'overhead'}
        self.assertAlmostEqual(overhead[first], 100.0)
        self.assertAlmostEqual(overhead[second], 300.0)

    def test_missing_rate_warns(self):
        self._produce()
        close = self._close()
        self.assertFalse(close.line_ids.filtered(lambda l: l.element == 'labor'))
        self.assertIn('Juan Pérez', close.warning)

    def test_analysis_by_element(self):
        production = self._produce()
        self._applied_rate(15.0)
        self._overhead(300.0)
        self._close().action_validate()
        rows = self.env['l10n_pe.mrp.cost.analysis'].search([('production_id', '=', production.id)])
        by_element = {}
        for row in rows:
            by_element[row.element] = by_element.get(row.element, 0.0) + row.amount
        self.assertAlmostEqual(by_element['material'], 40.0, places=2)
        self.assertAlmostEqual(by_element['labor'], 20.0, places=2)
        self.assertAlmostEqual(by_element['labor_adjustment'], 10.0, places=2)
        self.assertAlmostEqual(by_element['overhead'], 300.0, places=2)
        self.assertGreater(by_element['machine'], 0.0)

    def test_timesheet_import(self):
        mo_form = Form(self.env['mrp.production'])
        mo_form.product_id = self.table
        mo_form.bom_id = self.bom
        production = mo_form.save()
        production.action_confirm()
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(['Orden', 'Operación', 'Empleado', 'Fecha', 'Inicio', 'Horas'])
        sheet.append([production.name, 'Corte', '45678912', '15/01/2026', '07:30', 1.5])
        buffer = io.BytesIO()
        workbook.save(buffer)
        wizard = self.env['l10n_pe.mrp.timesheet.import'].create({
            'file': BinaryBytes(buffer.getvalue()),
        })
        wizard.action_import()
        log = production.workorder_ids.time_ids
        self.assertEqual(log.employee_id, self.employee)
        self.assertAlmostEqual(log.duration, 90.0)
        # 07:30 en Lima = 12:30 UTC.
        self.assertEqual(log.date_start, datetime(2026, 1, 15, 12, 30))

        sheet.append(['NO-EXISTE', '', '45678912', '15/01/2026', '', 1])
        buffer = io.BytesIO()
        workbook.save(buffer)
        wizard.file = BinaryBytes(buffer.getvalue())
        with self.assertRaisesRegex(UserError, 'Fila 3'):
            wizard.action_import()

    def test_labor_rate_from_payslip(self):
        structure = self.env.ref('al_hr_pe.base_structure')
        self.env['hr.main.parameter'].get_main_parameter(self.company).rmv = 1130.0
        employee = self.env['hr.employee'].create({
            'names': 'Rosa', 'last_name': 'Quispe', 'm_last_name': 'Mamani',
            'company_id': self.company.id,
            'date_version': date(2025, 1, 1),
            'contract_date_start': date(2025, 1, 1),
            'wage': 3000.0,
            'structure_type_id': structure.type_id.id,
        })
        slip = self.env['hr.payslip'].create({
            'name': 'Boleta marzo', 'employee_id': employee.id, 'struct_id': structure.id,
            'date_from': date(2026, 3, 1), 'date_to': date(2026, 3, 31),
        })
        slip.compute_sheet()
        slip.state = 'validated'
        worked = slip.worked_days_line_ids.filtered(lambda wd: wd.number_of_hours and not wd.work_entry_type_id.is_leave)
        self.assertTrue(worked)
        self.env['hr.main.parameter'].get_main_parameter(self.company).wd_dlab = worked.work_entry_type_id
        expected = sum(
            line.total * {'ING': 1, 'DES_AFE': -1, 'APOR_EMP': 1}[line.category_id.code]
            for line in slip.line_ids if line.category_id.code in ('ING', 'DES_AFE', 'APOR_EMP'))
        self.assertGreater(expected, 3000.0)
        rate = self.env['l10n_pe.mrp.labor.rate'].create({
            'date_from': date(2026, 3, 1), 'date_to': date(2026, 3, 31),
        })
        rate.action_compute()
        line = rate.line_ids.filtered(lambda l: l.employee_id == employee)
        self.assertAlmostEqual(line.payroll_cost, expected, places=2)
        self.assertGreater(line.hours, 0.0)
        rate.action_apply()
        self.assertEqual(rate.state, 'applied')
        self.assertAlmostEqual(employee.hourly_cost, line.hourly_cost, places=2)
