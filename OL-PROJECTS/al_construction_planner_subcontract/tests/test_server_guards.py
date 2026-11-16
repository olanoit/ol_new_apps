# -*- coding: utf-8 -*-
"""Controles del servidor de la valorización y del deductivo (auditoría del
16-nov-2026): quien prepara tiene permiso de escritura, así que el estado, la
tarifa y lo aplicado no pueden depender de la vista. Datos ficticios."""
from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged

from .test_contract_terms_creval import ContractTermsCommon


@tagged('post_install', '-at_install')
class TestServerGuards(ContractTermsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group = 'al_construction_planner.group_planner_'
        cls.preparer = new_test_user(
            cls.env, 'guard_prepara', groups=group + 'user,purchase.group_purchase_user',
            name='Quien prepara (test)')
        cls.validator = new_test_user(
            cls.env, 'guard_valida',
            groups=group + 'user,' + group + 'exec_validator,purchase.group_purchase_user',
            name='Quien valida (test)')

    def _settlement(self):
        _order, _advance, settlement = self._scenario()
        self.assertEqual(settlement.state, 'draft')
        return settlement

    def test_state_only_through_the_flow(self):
        settlement = self._settlement()
        as_preparer = settlement.with_user(self.preparer)
        for state in ('validated', 'approved', 'paid', 'cancel'):
            with self.assertRaises(UserError):
                as_preparer.write({'state': state})
        self.assertEqual(settlement.state, 'draft')
        as_preparer.action_submit()
        self.assertEqual(settlement.state, 'submitted')
        for state in ('draft', 'validated', 'approved', 'paid'):
            with self.assertRaises(UserError):
                as_preparer.write({'state': state})
        self.assertEqual(settlement.state, 'submitted')
        # Ni quien valida escribe «Aprobada» o «Pagada» a mano: son del flujo.
        for state in ('approved', 'paid'):
            with self.assertRaises(UserError):
                settlement.with_user(self.validator).write({'state': state})
        settlement.with_user(self.validator).action_validate()
        self.assertEqual(settlement.state, 'approved')
        self.assertTrue(settlement.invoice_id)
        for state in ('draft', 'submitted', 'validated', 'paid', 'cancel'):
            with self.assertRaises(UserError):
                as_preparer.write({'state': state})
        self.assertEqual(settlement.state, 'approved')

    def test_lines_are_written_by_the_system(self):
        settlement = self._settlement()
        line = settlement.line_ids[:1]
        price, qty = line.price_unit, line.qty_period
        for context in ({}, {'skip_validation_check': True}):
            as_preparer = line.with_user(self.preparer).with_context(**context)
            for vals in ({'price_unit': price * 2}, {'qty_period': qty + 500},
                         {'retention_pct': 0.0, 'qty_settled_before': -100.0}):
                with self.assertRaises(UserError):
                    as_preparer.write(vals)
            with self.assertRaises(UserError):
                as_preparer.copy()
            with self.assertRaises(UserError):
                as_preparer.unlink()
        self.assertEqual((line.price_unit, line.qty_period), (price, qty))
        total = settlement.amount_to_pay
        settlement.with_user(self.preparer).action_submit()
        settlement.with_user(self.validator).action_validate()
        with self.assertRaises(UserError):
            line.with_user(self.preparer).write({'price_unit': price * 2})
        self.assertEqual(settlement.amount_to_pay, total)

    def test_decisions_stay_with_people(self):
        """Los campos de decisión de la línea (porcentaje manual y su motivo)
        los sigue escribiendo quien prepara, con sus reglas."""
        line = self._settlement().line_ids[:1]
        line.with_user(self.preparer).write({'manual_reason': 'Corte parcial'})
        self.assertEqual(line.manual_reason, 'Corte parcial')

    def test_applied_deduction_is_final(self):
        _order, _advance, settlement = self._scenario()
        deduction = settlement.deduction_ids
        self.assertEqual(deduction.state, 'in_valuation')
        settlement.action_submit()
        settlement.action_validate()
        self.assertEqual(deduction.state, 'applied')
        as_preparer = deduction.with_user(self.preparer)
        with self.assertRaises(UserError):
            as_preparer.write({'state': 'pending'})
        with self.assertRaises(UserError):
            as_preparer.with_context(construction_deduction_sync=True).write({'amount': 1.0})
        with self.assertRaises(UserError):
            deduction.sudo().write({'amount': 1.0})
        with self.assertRaises(UserError):
            as_preparer.write({'settlement_id': False})
        self.assertEqual((deduction.state, deduction.amount), ('applied', 650.0))
        self.assertEqual(deduction.settlement_id, settlement)
        # Lo pendiente sí se anula y se retoma.
        pending = self._deduction(settlement.purchase_order_id, 100.0)
        pending.with_user(self.preparer).action_cancel()
        self.assertEqual(pending.state, 'cancel')
        pending.with_user(self.preparer).action_draft()
        self.assertEqual(pending.state, 'pending')
        with self.assertRaises(UserError):
            pending.with_user(self.preparer).write({'state': 'applied'})
