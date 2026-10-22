"""Bloqueo de ventas por mora."""
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.al_account_base.tests.common import use_pe_company


@tagged('post_install', '-at_install')
class TestSaleHold(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        cls.customer = cls.env['res.partner'].create({'name': 'CLIENTE BLOQUEADO SAC'})
        product = cls.env['product.product'].create({'name': 'Producto', 'list_price': 100})
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.customer.id,
            'order_line': [Command.create({'product_id': product.id, 'product_uom_qty': 1})],
        })

    def test_hold_blocks_confirmation(self):
        self.customer.action_l10n_pe_collection_hold()
        self.assertTrue(self.order.l10n_pe_collection_hold_warning)
        with self.assertRaises(UserError):
            self.order.action_confirm()

    def test_release_allows_confirmation(self):
        self.customer.action_l10n_pe_collection_hold()
        self.customer.action_l10n_pe_collection_release()
        self.order.invalidate_recordset(['l10n_pe_collection_hold_warning'])
        self.assertFalse(self.order.l10n_pe_collection_hold_warning)
        self.order.action_confirm()
        self.assertEqual(self.order.state, 'sale')

    def test_without_hold_confirms(self):
        self.order.action_confirm()
        self.assertEqual(self.order.state, 'sale')
