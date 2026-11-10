# -*- coding: utf-8 -*-
"""Paquete 1.18, entrega 4: «Generar plan» con el PROGRAMA de la hoja
(M118-06) y tableros desde PIEZAS (M118-11). Datos ficticios."""
from collections import defaultdict
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import Form, tagged

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestPackage118Program(PlannerCommon):

    def _program(self):
        self.project.write({
            'construction_program_start': date(2026, 11, 23),
            'construction_program_pace': 2.0, 'construction_program_days': 4,
            'construction_program_order': 'desc', 'construction_program_source': 'Hoja (test)',
            'construction_program_date': '2026-11-10 10:00:00'})

    def test_wizard_proposes_the_program(self):
        self._program()
        form = Form(self.env['construction.plan.generate.wizard'].with_context(
            default_plan_id=self.plan.id))
        self.assertEqual(form.schedule_mode, 'floors_per_week')
        self.assertEqual(form.schedule_pace, 2.0)
        self.assertEqual(form.schedule_date_start, date(2026, 11, 23))
        self.assertEqual(form.schedule_order, 'desc')
        self.assertIn('Hoja (test)', form.program_note)
        wizard = form.save()
        leaves = self.env['construction.stage']._offered_stages(self.project)._leaf_stages()
        self.assertEqual(set(wizard.stage_day_ids.stage_id.ids), set(leaves.ids))
        self.assertEqual(set(wizard.stage_day_ids.mapped('days')), {4})
        self.assertFalse(wizard.program_changed)

    def test_changed_pace_needs_a_reason(self):
        self._program()
        wizard = Form(self.env['construction.plan.generate.wizard'].with_context(
            default_plan_id=self.plan.id)).save()
        wizard.schedule_pace = 1.0
        self.assertTrue(wizard.program_changed)
        with self.assertRaises(UserError):
            wizard.action_generate()
        wizard.schedule_reason = 'Falta de personal (test)'
        wizard.action_generate()
        self.assertTrue(self.plan.line_ids)

    def test_without_program_the_usual_values(self):
        wizard = Form(self.env['construction.plan.generate.wizard'].with_context(
            default_plan_id=self.plan.id)).save()
        self.assertEqual(wizard.schedule_mode, 'none')
        self.assertFalse(wizard.program_note)


@tagged('post_install', '-at_install')
class TestPackage118Boards(PlannerCommon):

    def test_board_from_pieces(self):
        self.p_white.construction_board_m2 = 4.0
        wizard = self.env['construction.master.import.wizard'].create(
            {'project_id': self.project.id})
        code = self.p_white.default_code or 'TEST-WHITE'
        self.p_white.default_code = code
        pieces = {('T1', 'M1'): [
            {'qty': 2, 'length_mm': 1000, 'width_mm': 1000, '_code': code, 'edges': ''},
            {'qty': 1, 'length_mm': 500, 'width_mm': 1000, '_code': code, 'edges': ''}]}
        module_bom, warn = defaultdict(list), defaultdict(list)
        wizard._boards_from_pieces(pieces, module_bom, warn)
        line = module_bom[('T1', 'M1')][0]
        self.assertEqual(line['code'], code)
        self.assertAlmostEqual(line['qty'], 2.5 / 4.0, places=4)
        # Escrito en BOM: vale el escrito y se avisa.
        module_bom = defaultdict(list, {('T1', 'M1'): [{'code': code, 'qty': 1, 'stage': False}]})
        warn = defaultdict(list)
        wizard._boards_from_pieces(pieces, module_bom, warn)
        self.assertEqual(len(module_bom[('T1', 'M1')]), 1)
        self.assertTrue(warn['board_written'])
        # Sin m² útiles, no entra y avisa.
        self.p_white.construction_board_m2 = 0.0
        module_bom, warn = defaultdict(list), defaultdict(list)
        wizard._boards_from_pieces(pieces, module_bom, warn)
        self.assertFalse(module_bom[('T1', 'M1')])
        self.assertIn(code, warn['board_no_m2'])
