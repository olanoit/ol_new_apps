# -*- coding: utf-8 -*-
"""Fase 5: asientos contables de planilla y BBSS.

Mismo caso de referencia que las fases 3-4 (sueldo 3 000 estable,
régimen general, sin variables): el asiento debe cuadrar por
construcción — cargo del gasto = abono del neto + aportes del
trabajador — sin números mágicos.
"""
from odoo.tests import tagged

from odoo.addons.al_hr_pe_benefits.tests.test_fase3_benefits import \
    BenefitsCaseBase


@tagged('post_install', '-at_install')
class TestFase5Account(BenefitsCaseBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Account = cls.env['account.account']

        def _account(code, name, account_type):
            return Account.create({
                'code': code, 'name': name, 'account_type': account_type})

        cls.acc_gasto = _account('621000', 'Gasto planilla', 'expense')
        cls.acc_neto = _account('411000', 'Remuneraciones por pagar',
                                'liability_current')
        cls.acc_afp = _account('403000', 'AFP por pagar',
                               'liability_current')
        cls.acc_cts_debe = _account('621400', 'Gasto CTS', 'expense')
        cls.acc_cts_haber = _account('415100', 'Provisión CTS',
                                     'liability_current')
        cls.acc_cts_payable = _account('415200', 'CTS por pagar',
                                       'liability_current')
        cls.acc_grati_debe = _account('621500', 'Gasto gratificación',
                                      'expense')
        cls.acc_grati_haber = _account('415300', 'Provisión gratificación',
                                       'liability_current')
        cls.acc_boni_debe = _account('621600', 'Gasto bono', 'expense')
        cls.acc_boni_haber = _account('415400', 'Provisión bono',
                                      'liability_current')
        cls.acc_vaca_debe = _account('621700', 'Gasto vacaciones',
                                     'expense')
        cls.acc_vaca_haber = _account('415500', 'Provisión vacaciones',
                                      'liability_current')
        cls.acc_ajuste = _account('659000', 'Ajuste por redondeo',
                                  'expense')
        cls.journal = cls.env['account.journal'].create({
            'name': 'Planillas', 'code': 'PLAN', 'type': 'general',
            'company_id': cls.company.id})

        Rule = cls.env['hr.salary.rule']
        struct = cls.structure

        def _rule(code):
            return Rule.search([
                ('code', '=', code), ('struct_id', '=', struct.id)],
                limit=1)

        cls.rule_bas = _rule('BAS')
        cls.rule_neto = _rule('NETO')
        cls.afp_rules = Rule.browse()
        for code in ('A_JUB', 'COMFI', 'COMMIX', 'SEGI'):
            cls.afp_rules |= _rule(code)
        # Cuentas company_dependent de las reglas (env.company = PE)
        cls.rule_bas.account_debit = cls.acc_gasto
        cls.rule_neto.account_credit = cls.acc_neto
        # Cuenta de la afiliación AFP (company_dependent en el catálogo
        # global)
        cls.afp.with_company(cls.company).account_id = cls.acc_afp

        cls.param.write({
            'move_journal_id': cls.journal.id,
            'move_partner_id': cls.company.partner_id.id,
            'afp_rule_ids': [(6, 0, cls.afp_rules.ids)],
            # Cuentas de BBSS (company_dependent)
            'cts_debe_account_id': cls.acc_cts_debe.id,
            'cts_haber_account_id': cls.acc_cts_haber.id,
            'cts_payable_account_id': cls.acc_cts_payable.id,
            'grati_debe_account_id': cls.acc_grati_debe.id,
            'grati_haber_account_id': cls.acc_grati_haber.id,
            'boni_debe_account_id': cls.acc_boni_debe.id,
            'boni_haber_account_id': cls.acc_boni_haber.id,
            'vaca_debe_account_id': cls.acc_vaca_debe.id,
            'vaca_haber_account_id': cls.acc_vaca_haber.id,
            'benefits_adjust_account_id': cls.acc_ajuste.id,
        })

    def test_asiento_lote(self):
        """Asiento único del lote: gasto BAS al debe = neto + aportes
        AFP al haber (a la cuenta de la afiliación)."""
        run = self.batch
        run._pe_generate_batch_move(adjust_account=self.acc_ajuste)
        move = run.move_id
        self.assertTrue(move, 'El lote no tiene asiento')
        self.assertEqual(move.state, 'posted')
        self.assertEqual(move.ref, 'PLA042026')
        total_debit = sum(move.line_ids.mapped('debit'))
        total_credit = sum(move.line_ids.mapped('credit'))
        self.assertAlmostEqual(total_debit, total_credit, places=2)
        # El gasto del básico es el sueldo del mes
        bas_lines = move.line_ids.filtered(
            lambda l: l.account_id == self.acc_gasto)
        self.assertAlmostEqual(
            sum(bas_lines.mapped('debit')), self.wage, places=2)
        # Bloque AFP: abono a la cuenta de la afiliación
        afp_lines = move.line_ids.filtered(
            lambda l: l.account_id == self.acc_afp)
        self.assertTrue(afp_lines, 'Sin línea AFP a la cuenta de la '
                                   'afiliación')
        self.assertGreater(sum(afp_lines.mapped('credit')), 0.0)
        # neto + aportes AFP = básico (sin más ingresos/descuentos)
        neto = sum(move.line_ids.filtered(
            lambda l: l.account_id == self.acc_neto).mapped('credit'))
        afp = sum(afp_lines.mapped('credit'))
        self.assertAlmostEqual(neto + afp, self.wage, delta=0.05)
        # Regenerar debe estar bloqueado
        with self.assertRaises(Exception):
            run._pe_generate_batch_move(adjust_account=self.acc_ajuste)

    def test_asiento_cts(self):
        """Asiento del depósito CTS: sin provisión previa, gasto =
        total CTS al debe y CTS por pagar al haber."""
        from datetime import date
        cts = self.env['hr.cts'].create({
            'company_id': self.company.id,
            'year': 2026,
            'type': '05',
            'payslip_run_id': self.batch.id,
            'deposit_date': date(2026, 5, 15),
        })
        cts.get_cts()
        lines = cts._get_move_lines()
        self.assertTrue(lines)
        total_debit = sum(l['debit'] for l in lines)
        total_credit = sum(l['credit'] for l in lines)
        self.assertAlmostEqual(total_debit, total_credit, places=2)
        expected = sum(cts.line_ids.mapped('cts_soles'))
        self.assertAlmostEqual(total_credit, expected, places=2)
        # Flujo completo por el wizard
        action = cts.get_move_wizard()
        ctx = action['context']
        wizard = self.env['hr.benefits.move.wizard'].with_context(
            **ctx).create({
                'debit': ctx['default_debit'],
                'credit': ctx['default_credit'],
            })
        wizard.generate_move()
        self.assertTrue(cts.account_move_id)
        self.assertEqual(cts.account_move_id.state, 'posted')
        payable = sum(cts.account_move_id.line_ids.filtered(
            lambda l: l.account_id == self.acc_cts_payable
        ).mapped('credit'))
        self.assertAlmostEqual(payable, expected, places=2)

    def test_asiento_provision(self):
        """Asiento de provisión mensual: pareja gasto/pasivo por
        concepto, cuadrado (básico/12 CTS y vacaciones, /6 grati)."""
        prov = self.env['hr.provisiones'].create({
            'company_id': self.company.id,
            'payslip_run_id': self.batch.id,
        })
        prov.actualizar()
        lines = prov._get_move_lines()
        self.assertTrue(lines)
        total_debit = sum(l['debit'] for l in lines)
        total_credit = sum(l['credit'] for l in lines)
        self.assertAlmostEqual(total_debit, total_credit, places=2)

        def total(account, side):
            return sum(l[side] for l in lines
                       if l['account_id'] == account.id)

        self.assertAlmostEqual(
            total(self.acc_cts_debe, 'debit'), self.wage / 12, places=2)
        self.assertAlmostEqual(
            total(self.acc_cts_haber, 'credit'), self.wage / 12, places=2)
        self.assertAlmostEqual(
            total(self.acc_grati_debe, 'debit'), self.wage / 6, places=2)
        self.assertAlmostEqual(
            total(self.acc_vaca_debe, 'debit'), self.wage / 12, places=2)
