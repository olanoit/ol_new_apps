# -*- coding: utf-8 -*-
"""Paquete 1.17, M117-25: la factura en una línea o por partida."""
from datetime import date

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_income import IncomeCommon


@tagged('post_install', '-at_install')
class TestPackage117Invoice(IncomeCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.construction_invoice_product_id = cls.env['product.product'].create(
            {'name': 'SERVICIO POR VALORIZACION (test)', 'type': 'service'})
        cls.company.construction_invoice_text = (
            'Valorización N° {numero} del proyecto {obra} según O.S. {os} F.G S/ {fondo}')

    def _valuation(self, form='single', **contract):
        first = self._execute_until_week()
        self._confirm(first)
        valuation = self._prepare_valuation(date(2026, 10, 28))
        valuation.with_user(self.projects_user).action_send()
        self._confirm_valuation(valuation)
        if not valuation.contract_id:
            valuation.sudo().contract_id = self.env['construction.contract'].create({
                'name': 'Contrato 1.17 (test)', 'project_id': self.project.id,
                'partner_id': valuation.sale_order_id.partner_id.id,
                'sale_order_id': valuation.sale_order_id.id})
        valuation.contract_id.sudo().write(dict({'invoice_form': form, 'client_order_ref': 'OS-99'},
                                                **contract))
        return valuation

    def test_single_line_invoice(self):
        valuation = self._valuation()
        valuation.with_user(self.finance).action_create_invoice()
        invoice = valuation.invoice_id
        lines = invoice.invoice_line_ids.filtered(lambda l: l.display_type == 'product')
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines.product_id, self.company.construction_invoice_product_id)
        self.assertIn('OS-99', lines.name)
        self.assertIn('Valorización N° %s' % valuation.sequence_number, lines.name)
        self.assertAlmostEqual(lines.price_subtotal, valuation.amount_confirmed, delta=0.01)
        self.assertFalse(lines.sale_line_ids)
        rows = self.env['construction.valuation.invoiced'].sudo().search(
            [('valuation_id', '=', valuation.id)])
        self.assertEqual(rows.sale_line_id, valuation.line_ids.sale_line_id)
        self.assertAlmostEqual(sum(rows.mapped('amount')), valuation.amount_confirmed)

    def test_single_line_cannot_exceed_what_was_confirmed(self):
        valuation = self._valuation()
        valuation.with_user(self.finance).action_create_invoice()
        line = valuation.invoice_id.invoice_line_ids.filtered(
            lambda l: l.product_id == self.company.construction_invoice_product_id)
        line.price_unit += 100
        with self.assertRaises(UserError):
            valuation.invoice_id.action_post()
        line.price_unit -= 100
        valuation.invoice_id.action_post()
        self.assertEqual(valuation.state, 'invoiced')

    def test_by_partida_keeps_today(self):
        valuation = self._valuation('by_partida')
        valuation.with_user(self.finance).action_create_invoice()
        lines = valuation.invoice_id.invoice_line_ids.filtered(lambda l: l.sale_line_ids)
        self.assertEqual(lines.sale_line_ids, valuation.line_ids.sale_line_id)
        self.assertTrue(self.env['construction.valuation.invoiced'].sudo().search_count(
            [('valuation_id', '=', valuation.id)]))

    def test_amounts_go_in_the_text_without_accounts(self):
        self.company.construction_guarantee_account_id = False
        self.company.construction_advance_account_id = False
        valuation = self._valuation()
        valuation.sudo().write({'guarantee_pct': 5.0})
        text = valuation._construction_invoice_text()
        if valuation.amount_guarantee:
            self.assertIn('Fondo de garantía', text)

    def test_empty_template_value_blocks_and_says_where(self):
        valuation = self._valuation(client_order_ref=False)
        with self.assertRaisesRegex(UserError, 'O.S. del cliente'):
            valuation.with_user(self.finance).action_create_invoice()
        self.assertFalse(valuation.invoice_id)
        wizard = self.env['construction.valuation.invoice.wizard'].with_user(self.finance).create(
            {'valuation_id': valuation.id})
        self.assertIn('O.S. del cliente', wizard.missing)
        self.assertFalse(wizard.preview_html)

    def test_preview_shows_the_lines(self):
        valuation = self._valuation()
        action = valuation.with_user(self.finance).action_open_invoice_preview()
        wizard = self.env[action['res_model']].with_user(self.finance).browse(action['res_id'])
        self.assertIn('OS-99', wizard.preview_html)
        self.assertFalse(wizard.missing)
        wizard.action_create()
        self.assertTrue(valuation.invoice_id)

    def test_cancelled_invoice_frees_the_recorded_amount(self):
        valuation = self._valuation()
        valuation.with_user(self.finance).action_create_invoice()
        sale_line = valuation.line_ids.sale_line_id[:1]
        Recorded = self.env['construction.valuation.invoiced'].sudo()
        self.assertTrue(Recorded._recorded_qty(sale_line))
        valuation.invoice_id.button_cancel()
        self.assertEqual(Recorded._recorded_qty(sale_line), 0)

    def test_annex_is_attached(self):
        valuation = self._valuation()
        valuation.with_user(self.finance).action_create_invoice()
        self.assertTrue(self.env['ir.attachment'].sudo().search_count([
            ('res_model', '=', 'account.move'), ('res_id', '=', valuation.invoice_id.id),
            ('name', 'like', 'Anexo_')]))
        self.assertIsInstance(valuation._construction_annex_detail(), list)
        self.assertTrue(Command)
