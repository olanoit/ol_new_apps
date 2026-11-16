# -*- coding: utf-8 -*-
"""Reglas de compañía de la meta de valorización y de lo facturado por partida
(auditoría del 16-nov-2026): tenían ``company_id`` y ninguna regla, así que en
una base con varias compañías se leían entre ellas. Datos ficticios."""
from datetime import date

from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestCompanyRules(TransactionCase):

    def test_models_have_company_rule(self):
        for model in ('construction.valuation.target', 'construction.valuation.invoiced'):
            rules = self.env['ir.rule'].search([('model_id.model', '=', model), ('global', '=', True)])
            self.assertTrue(
                any('company_ids' in (rule.domain_force or '') for rule in rules), model)

    def test_target_of_another_company_is_not_visible(self):
        other = self.env['res.company'].create({'name': 'Otra constructora (test)'})
        own_project, other_project = self.env['project.project'].create([
            {'name': 'Obra propia (test metas)', 'is_construction_site': True,
             'company_id': self.env.company.id},
            {'name': 'Obra ajena (test metas)', 'is_construction_site': True,
             'company_id': other.id}])
        Target = self.env['construction.valuation.target']
        own, foreign = Target.create([
            {'project_id': own_project.id, 'month': date(2026, 11, 1)},
            {'project_id': other_project.id, 'month': date(2026, 11, 1)}])
        self.assertEqual(foreign.company_id, other)
        user = new_test_user(self.env, 'metas_una_compania',
                             groups='al_construction_planner.group_planner_user',
                             company_id=self.env.company.id,
                             company_ids=[(6, 0, self.env.company.ids)])
        visible = Target.with_user(user).search([('id', 'in', (own | foreign).ids)])
        self.assertEqual(visible, own)
