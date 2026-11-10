# -*- coding: utf-8 -*-
"""Paquete 1.18, entrega 1 (M118-04): costo de referencia en el plan y
«Aplicar costo» por grupo. Datos ficticios."""
from odoo.exceptions import RedirectWarning
from odoo.tests import Form, tagged

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestPackage118Prices(PlannerCommon):

    def test_reference_cost_on_generate(self):
        """«Generar plan» deja el costo planificado en 0 y el de referencia
        con el costo del producto, en la unidad de la línea."""
        self.p_white.standard_price = 120.0
        self._generate()
        lines = self.plan.line_ids.filtered(lambda l: l.product_id == self.p_white)
        self.assertTrue(lines)
        for line in lines:
            self.assertFalse(line.price_unit_planned)
            expected = self.p_white.uom_id._compute_price(120.0, line.product_uom_id)
            self.assertAlmostEqual(line.price_reference, expected, places=4)
            self.assertTrue(line.price_reference_date)

    def test_group_wizard_marks_and_applies(self):
        self.env.company.construction_price_review_pct = 10.0
        self.p_white.standard_price = 100.0
        self._generate()
        vendor = self.env['res.partner'].create({'name': 'Proveedor melamina (test)'})
        order = self.env['purchase.order'].create({
            'partner_id': vendor.id,
            'order_line': [(0, 0, {'product_id': self.p_white.id, 'product_qty': 10,
                                   'price_unit': 115.0})],
        })
        order.button_confirm()
        action = self.plan.action_open_price_group_wizard()
        wizard = Form(self.env[action['res_model']].with_context(**action['context'])).save()
        rows = {row.product_id: row for row in wizard.row_ids}
        white = rows[self.p_white]
        # 115 frente a 100: +15 % con un umbral de 10 % queda sin marcar.
        self.assertAlmostEqual(white.price_suggested, 115.0)
        self.assertAlmostEqual(white.variation_pct, 15.0, places=1)
        self.assertTrue(white.needs_review)
        self.assertFalse(white.apply)
        # Los demás no tienen compras: sin costo sugerido ni marca.
        others = wizard.row_ids - white
        self.assertTrue(others)
        self.assertFalse(any(others.mapped('apply')))
        # La persona revisa y marca; a otro le pone la referencia.
        white.apply = True
        other = others[0]
        other.price_reference = other.price_reference or 7.5
        other.write({'use_reference': True, 'apply': True})
        wizard.action_apply()
        white_lines = self.plan.line_ids.filtered(lambda l: l.product_id == self.p_white)
        self.assertEqual(set(white_lines.mapped('price_unit_planned')), {115.0})
        self.assertIn('Ponderado de 6 meses', white_lines[0].price_basis)
        other_lines = self.plan.line_ids.filtered(lambda l: l.product_id == other.product_id)
        self.assertTrue(all(other_lines.mapped('price_unit_planned')))
        messages = self.plan.message_ids.filtered(lambda m: 'Costo aplicado a' in (m.body or ''))
        self.assertEqual(len(messages), 1)

    def test_approval_opens_the_group_wizard(self):
        if not self.project.account_id:
            self.project._create_analytic_account()
        self._generate()
        self.plan.line_ids.filtered(lambda l: not l.stage).stage = 'production'
        with self.assertRaises(RedirectWarning) as error:
            self.plan.with_user(self.planner).action_request_approval()
        action = error.exception.args[1]
        self.assertEqual(action['res_model'], 'construction.plan.price.group.wizard')
        self.assertIn('productos', error.exception.args[0])
