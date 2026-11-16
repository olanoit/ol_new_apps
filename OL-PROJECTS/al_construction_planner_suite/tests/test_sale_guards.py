# -*- coding: utf-8 -*-
"""Controles del servidor de la ruta del ingreso (auditoría del 16-nov-2026):
la entrega semanal, la valorización con el cliente y el cambio de obra solo
cambian de estado por sus acciones; quien ejecuta tiene permiso de escritura y
el estado solo es de lectura en la vista. Datos ficticios."""
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged

from .test_change_v15 import TestChangeV15
from .test_income import IncomeCommon


@tagged('post_install', '-at_install')
class TestIncomeGuards(IncomeCommon):

    def test_delivery_and_valuation_states(self):
        first = self._execute_until_week()
        second = self.env['construction.weekly.delivery']._prepare_deliveries(
            today=date(2026, 11, 5), projects=self.project)
        # Confirmar la entrega es de la jefatura.
        with self.assertRaises(UserError):
            first.with_user(self.planner).write({'state': 'confirmed'})
        self.assertEqual(first.state, 'draft')
        self._confirm(first | second)
        valuation = self._prepare_valuation(date(2026, 11, 11))
        as_projects = valuation.with_user(self.projects_user)
        for state in ('confirmed', 'invoiced', 'cancel'):
            with self.assertRaises(UserError):
                as_projects.write({'state': state})
        self.assertEqual(valuation.state, 'draft')
        as_projects.action_send()
        self.assertEqual(valuation.state, 'sent')
        with self.assertRaises(UserError):
            as_projects.write({'state': 'confirmed'})
        self._confirm_valuation(valuation)
        self.assertEqual(valuation.state, 'confirmed')
        # Lo que el cliente confirmó no se cambia después.
        line = valuation.line_ids[:1]
        confirmed = line.amount_confirmed
        with self.assertRaises(UserError):
            line.with_user(self.projects_user).write({'amount_confirmed': confirmed / 2})
        self.assertEqual(line.amount_confirmed, confirmed)
        with self.assertRaises(UserError):
            as_projects.write({'state': 'draft'})


@tagged('post_install', '-at_install')
class TestChangeGuards(TestChangeV15):

    def test_change_approval_is_for_the_head(self):
        self._generate()
        executor = new_test_user(
            self.env, 'cambios_ejecuta', name='Quien ejecuta (test cambios)',
            groups='al_construction_planner.group_planner_user')
        change = self._change()
        self.assertEqual(change.state, 'draft')
        with self.assertRaises(UserError):
            change.with_user(executor).write({'state': 'approved'})
        self.assertEqual(change.state, 'draft')
