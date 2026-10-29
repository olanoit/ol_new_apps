# -*- coding: utf-8 -*-
"""Decisiones del validador al actualizar la valorización (CREVAL, CR-15):
«Actualizar avances» actualiza las líneas en vez de rehacerlas y conserva el
pago del re-trabajo, el porcentaje escrito y su autor; si el avance cambia,
la línea avisa. Datos ficticios."""
import base64
from datetime import date

from odoo import Command
from odoo.tests import tagged

from .test_contract_terms_creval import PHOTO, ContractTermsCommon
from .test_corrections_creval import TestCorrectionsCreval


@tagged('post_install', '-at_install')
class TestRefreshDecisions(ContractTermsCommon):

    _order = TestCorrectionsCreval._order
    _prepare = TestCorrectionsCreval._prepare

    def _rework(self, qty, day=date(2026, 11, 4)):
        progress = self.env['construction.task.progress'].create({
            'task_id': self.partida.id, 'activity_id': self.act_wall.id,
            'date': day, 'qty': qty, 'is_rework': True, 'rework_reason': 'bad_assembly',
            'attachment_ids': [Command.create({'name': 'foto.jpg', 'raw': base64.b64decode(PHOTO)})]})
        progress.action_validate()
        return progress

    def _paid_rework(self):
        self._order()
        self._report(self.partida, self.act_wall, 500.0, date(2026, 11, 4))
        rework = self._rework(6.0)
        settlement = self._prepare()
        line = settlement.line_ids.filtered('is_rework')
        line.write({'rework_paid': True,
                    'rework_pay_reason': 'El plano cambió después del armado'})
        return settlement, line, rework

    def test_rework_payment_survives_refresh(self):
        settlement, line, _rework = self._paid_rework()
        settlement.action_refresh()
        settlement.action_refresh()
        self.assertTrue(line.exists())
        self.assertEqual(settlement.line_ids.filtered('is_rework'), line)
        self.assertTrue(line.rework_paid)
        self.assertEqual(line.rework_pay_reason, 'El plano cambió después del armado')
        self.assertEqual(line.rework_paid_by, self.env.user)
        self.assertEqual(line.amount, 229.2)
        self.assertFalse(line.decision_warning)

    def test_manual_pct_survives_refresh(self):
        self._order()
        self._report(self.partida, self.act_wall, 500.0, date(2026, 11, 4))
        settlement = self._prepare()
        line = settlement.line_ids
        line.write({'pct_manual': 10.0, 'manual_reason': 'Acuerdo en obra'})
        qty, author = line.qty_settle, line.manual_user_id
        settlement.action_refresh()
        self.assertEqual(settlement.line_ids, line)
        self.assertEqual(line.pct_manual, 10.0)
        self.assertEqual(line.manual_reason, 'Acuerdo en obra')
        self.assertEqual(line.manual_user_id, author)
        self.assertEqual(line.qty_settle, qty)

    def test_new_progress_keeps_decision_with_warning(self):
        settlement, line, _rework = self._paid_rework()
        new = self._rework(2.0)
        self.assertEqual(new.state, 'validated')
        settlement.action_refresh()
        self.assertEqual(line.qty_period, 8.0)
        self.assertTrue(line.rework_paid)
        self.assertEqual(line.qty_settle, 8.0)
        self.assertIn('El avance cambió', line.decision_warning)
        line.action_confirm_decision()
        self.assertFalse(line.decision_warning)
        self.assertEqual(line.decision_qty, 8.0)

    def test_rejected_progress_keeps_line_at_zero(self):
        settlement, line, rework = self._paid_rework()
        rework.action_reset()
        settlement.action_refresh()
        self.assertTrue(line.exists())
        self.assertTrue(line.no_progress)
        self.assertEqual(line.qty_settle, 0.0)
        self.assertEqual(line.amount, 0.0)
        self.assertTrue(line.rework_paid)
        self.assertIn('Sin avances', line.decision_warning)
        # Al quitar la decisión, la siguiente actualización la borra.
        line.write({'rework_paid': False})
        settlement.action_refresh()
        self.assertFalse(line.exists())

    def test_line_without_decision_is_removed(self):
        self._order()
        progress = self._report(self.partida, self.act_wall, 500.0, date(2026, 11, 4))
        rework = self._rework(6.0)
        settlement = self._prepare()
        self.assertEqual(len(settlement.line_ids), 2)
        rework.action_reset()
        self.assertEqual(settlement.line_ids.progress_ids, progress)
