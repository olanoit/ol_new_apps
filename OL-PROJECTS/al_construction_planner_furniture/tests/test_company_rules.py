# -*- coding: utf-8 -*-
"""Reglas de compañía de la receta real, las piezas y materiales de la
tipología y las tarifas (auditoría del 16-nov-2026): tenían ``company_id`` y
ninguna regla de registro."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

MODELS = ('construction.real.recipe', 'construction.real.recipe.line',
          'construction.recipe.versus', 'construction.typology.piece',
          'construction.typology.module.material', 'construction.rate.list.line')


@tagged('post_install', '-at_install')
class TestCompanyRules(TransactionCase):

    def test_models_have_company_rule(self):
        for model in MODELS:
            rules = self.env['ir.rule'].search([('model_id.model', '=', model), ('global', '=', True)])
            self.assertTrue(
                any('company_ids' in (rule.domain_force or '') for rule in rules), model)
