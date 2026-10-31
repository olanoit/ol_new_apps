# -*- coding: utf-8 -*-
"""Regresiones de la revisión de importación (octubre 2026).

* Reimportar una regla no la saca de las otras estructuras ni le cambia
  el modo de cálculo o la condición si la celda viene vacía.
* «nan» / «inf» no son montos válidos.
* Importe vacacional no numérico: error, no S/ 0.
* Filas repetidas en el archivo: adelantos distintos y saldo único.
* Boletas anuladas fuera del mapa documento → boleta.
* Secuencia inválida y filas vacías al final de la hoja.
* El historial de importaciones de un usuario no lo leen los demás.
"""
from datetime import date
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.al_hr_pe_import.models import import_payroll_mixin
from .test_fase8_import import _xlsx

RULE_HEADER = ['CATEGORÍA', 'COMPAÑÍA', 'CÓDIGO', 'NOMBRE', 'SECUENCIA',
               'CÓDIGO PYTHON', 'CONDICIÓN PYTHON']


@tagged('post_install', '-at_install')
class TestImportReviewFixes(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pen = cls.env.ref('base.PEN')
        pen.active = True
        cls.company = cls.env['res.company'].create({
            'name': 'PE Revisión Import SAC',
            'country_id': cls.env.ref('base.pe').id,
            'currency_id': pen.id,
        })
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=[cls.company.id]))
        cls.env.user.company_ids |= cls.company
        cls.env.user.group_ids |= cls.env.ref(
            'hr_payroll.group_hr_payroll_manager')
        cls.structure = cls.env.ref('al_hr_pe.base_structure')
        cls.employee = cls.env['hr.employee'].with_company(
            cls.company).create({
                'names': 'Elsa', 'last_name': 'Ccori',
                'm_last_name': 'Apaza',
                'company_id': cls.company.id,
                'date_version': date(2025, 1, 1),
                'contract_date_start': date(2025, 1, 1),
                'wage': 2800.0,
                'structure_type_id': cls.structure.type_id.id,
            })
        cls.employee.version_id.identification_id = '71234560'
        Struct = cls.env['hr.payroll.structure']
        cls.struct_general = Struct.create({
            'name': 'Régimen general revisión',
            'type_id': cls.structure.type_id.id})
        cls.struct_constr = Struct.create({
            'name': 'Construcción revisión',
            'type_id': cls.structure.type_id.id})

    @staticmethod
    def _run(wizard):
        rows = wizard._preprocess_rows(wizard._iter_data_rows())
        return wizard._process_all_rows(rows)

    def _wizard(self, model, sheet, rows, **vals):
        wizard = self.env[model].create(dict({
            'file_data': _xlsx({sheet: rows}),
            'file_name': 'archivo.xlsx',
            'company_id': self.company.id,
        }, **vals))
        wizard.action_load_file()
        return wizard

    def _rule_wizard(self, rows, struct):
        return self._wizard('al.import.hr.salary.rule.wizard', 'REGLAS',
                            [RULE_HEADER] + rows, struct_id=struct.id)

    def _shared_rule(self, **vals):
        return self.env['hr.salary.rule'].create(dict({
            'name': 'Horas extra 25 %', 'code': 'REVHEX',
            'category_ids': [(6, 0, self.env.ref('al_hr_pe.ING').ids)],
            'struct_ids': [(6, 0, (self.struct_general
                                   | self.struct_constr).ids)],
        }, **vals))

    # ------------------------------------------------------------------
    # Reglas salariales
    # ------------------------------------------------------------------
    def test_reimport_keeps_other_structures(self):
        """La regla compartida sigue en «Construcción»."""
        rule = self._shared_rule(amount_select='code',
                                 amount_python_compute='result = 1')
        _res, counts, _log, _ids = self._run(self._rule_wizard(
            [['ING', '', 'REVHEX', 'Horas extra', 10, 'result = 2', '']],
            self.struct_general))
        self.assertEqual(counts['updated'], 1)
        self.assertEqual(rule.struct_ids,
                         self.struct_general | self.struct_constr)
        self.assertEqual(rule.amount_python_compute, 'result = 2')

    def test_reimport_empty_cells_keep_amount_and_condition(self):
        """Sin código ni condición en la fila, la regla de importe fijo
        con condición por dominio no cambia de modo."""
        rule = self._shared_rule(
            amount_select='fix', amount_fix=50.0,
            condition_select='domain',
            condition_domain="[('wage', '<', 5000)]")
        _res, counts, _log, _ids = self._run(self._rule_wizard(
            [['ING', '', 'REVHEX', 'Horas extra renombrada', '', '', '']],
            self.struct_general))
        self.assertEqual(counts['updated'], 1)
        self.assertEqual(rule.name, 'Horas extra renombrada')
        self.assertEqual(rule.amount_select, 'fix')
        self.assertEqual(rule.amount_fix, 50.0)
        self.assertEqual(rule.condition_select, 'domain')

    def test_invalid_sequence_is_an_error(self):
        _res, counts, _log, _ids = self._run(self._rule_wizard(
            [['ING', '', 'REVSEQ', 'Secuencia mala', '1a', 'result = 1',
              '']], self.struct_general))
        self.assertEqual(counts['error'], 1)
        self.assertFalse(self.env['hr.salary.rule'].search(
            [('code', '=', 'REVSEQ')]))

    # ------------------------------------------------------------------
    # Montos no finitos
    # ------------------------------------------------------------------
    def test_nan_and_inf_are_not_amounts(self):
        Mixin = self.env['al.import.payroll.mixin']
        for value in ('nan', 'NaN', 'inf', '-inf', float('nan')):
            self.assertIsNone(Mixin._to_float(value), value)
        self.assertEqual(Mixin._to_float('12,5'), 12.5)

    def test_nan_advance_is_rejected(self):
        adv_type = self.env['hr.advance.type'].create({
            'name': 'Adelanto revisión', 'company_id': self.company.id})
        _res, counts, _log, _ids = self._run(self._wizard(
            'al.import.hr.advance.wizard', 'ADELANTOS', [
                ['DOC', 'TIPO', 'FECHA', 'DESCUENTO', 'MONTO', 'OBS'],
                ['71234560', adv_type.name, '2026-07-05', '2026-07-31',
                 'nan', '']]))
        self.assertEqual(counts['error'], 1)
        self.assertFalse(self.env['hr.advance'].search(
            [('employee_id', '=', self.employee.id)]))

    # ------------------------------------------------------------------
    # Saldo vacacional
    # ------------------------------------------------------------------
    def _rest_wizard(self, rows):
        return self._wizard(
            'al.import.vacation.rest.wizard', 'VACACIONES',
            [['FECHA', 'DOCUMENTO', 'DÍAS', 'IMPORTE']] + rows)

    def _rests(self):
        return self.env['hr.vacation.rest'].search([
            ('employee_id', '=', self.employee.id),
            ('internal_motive', '=', 'rest')])

    def test_vacation_invalid_amount_keeps_previous_balance(self):
        self._run(self._rest_wizard([['2026-01-01', '71234560', 10, 900]]))
        _res, counts, _log, _ids = self._run(self._rest_wizard(
            [['2026-02-01', '71234560', 12, '1.250,00 soles']]))
        self.assertEqual(counts['error'], 1)
        self.assertEqual(self._rests().amount_rest, 900.0,
                         'el saldo válido no debe borrarse')
        # Celda vacía: S/ 0, como antes.
        _res, counts, _log, _ids = self._run(self._rest_wizard(
            [['2026-02-01', '71234560', 12, None]]))
        self.assertEqual(counts['updated'], 1)
        self.assertEqual(self._rests().amount_rest, 0.0)

    def test_vacation_repeated_document_is_an_error(self):
        _res, counts, _log, _ids = self._run(self._rest_wizard([
            ['2026-01-01', '71234560', 10, 900],
            ['2026-01-01', '71234560', 4, 300]]))
        self.assertEqual(counts['created'], 1)
        self.assertEqual(counts['error'], 1)
        self.assertEqual(self._rests().days_rest, 10)

    # ------------------------------------------------------------------
    # Adelantos con la misma clave
    # ------------------------------------------------------------------
    def test_two_advances_same_discount_date(self):
        adv_type = self.env['hr.advance.type'].create({
            'name': 'Adelanto de sueldo rev', 'company_id': self.company.id})
        rows = [['DOC', 'TIPO', 'FECHA', 'DESCUENTO', 'MONTO', 'OBS'],
                ['71234560', adv_type.name, '2026-07-05', '2026-07-31',
                 300, ''],
                ['71234560', adv_type.name, '2026-07-12', '2026-07-31',
                 200, '']]
        _res, counts, _log, _ids = self._run(self._wizard(
            'al.import.hr.advance.wizard', 'ADELANTOS', rows))
        self.assertEqual(counts['created'], 2)
        advances = self.env['hr.advance'].search(
            [('employee_id', '=', self.employee.id)])
        self.assertEqual(sorted(advances.mapped('amount')), [200.0, 300.0])
        # Reimportar el mismo archivo actualiza los dos, no crea otros.
        _res, counts, _log, _ids = self._run(self._wizard(
            'al.import.hr.advance.wizard', 'ADELANTOS', rows))
        self.assertEqual(counts['updated'], 2)
        self.assertEqual(len(self.env['hr.advance'].search(
            [('employee_id', '=', self.employee.id)])), 2)

    # ------------------------------------------------------------------
    # Inputs de boleta: anuladas fuera
    # ------------------------------------------------------------------
    def test_cancelled_slip_is_not_counted(self):
        run = self.env['hr.payslip.run'].create({
            'name': 'Lote revisión', 'company_id': self.company.id,
            'date_start': date(2026, 7, 1), 'date_end': date(2026, 7, 31)})
        slips = self.env['hr.payslip'].create([{
            'name': 'Boleta %s' % idx, 'employee_id': self.employee.id,
            'struct_id': self.structure.id, 'payslip_run_id': run.id,
            'date_from': date(2026, 7, 1), 'date_to': date(2026, 7, 31),
        } for idx in (1, 2)])
        slips[0].state = 'cancel'
        wizard = self.env['al.import.payslip.input.wizard'].new({
            'payslip_run_id': run.id, 'company_id': self.company.id})
        self.assertEqual(wizard._find_slip('71234560', {}), slips[1])

    # ------------------------------------------------------------------
    # Lectura de la hoja
    # ------------------------------------------------------------------
    def test_scanned_rows_limit(self):
        """Las filas vacías también cuentan para el tope de recorrido."""
        rows = [['FECHA', 'DOCUMENTO', 'DÍAS', 'IMPORTE']] + [[None] * 4] * 5
        rows.append(['2026-01-01', '71234560', 10, 900])
        wizard = self._rest_wizard(rows[1:])
        with patch.object(import_payroll_mixin, 'MAX_SCANNED_ROWS', 4):
            with self.assertRaises(UserError):
                wizard._iter_data_rows()
        self.assertEqual(len(wizard._iter_data_rows()), 1)

    # ------------------------------------------------------------------
    # Historial de importaciones
    # ------------------------------------------------------------------
    def test_progress_visible_only_to_its_owner(self):
        def user(login, group):
            return self.env['res.users'].create({
                'name': login, 'login': login,
                'company_id': self.company.id,
                'company_ids': [(6, 0, self.company.ids)],
                'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                      self.env.ref(group).id])],
            })
        owner = user('rev_import_owner', 'hr_payroll.group_hr_payroll_user')
        other = user('rev_import_other', 'hr_payroll.group_hr_payroll_user')
        manager = user('rev_import_mgr',
                       'hr_payroll.group_hr_payroll_manager')
        progress = self.env['al.import.payroll.progress'].with_user(
            owner).create({
                'wizard_model': 'al.import.vacation.rest.wizard',
                'wizard_id': 1, 'company_id': self.company.id})
        progress.with_user(owner).read(['log'])
        progress.with_user(manager).read(['log'])
        with self.assertRaises(AccessError):
            progress.with_user(other).read(['log'])
