# -*- coding: utf-8 -*-
"""Paquete 1.12, M112-03: «Pedir reposición a planta» crea la orden en la
planta de la lista del producto.

Dos plantas de prueba: la de corte, con el tipo de reposición de la
compañía, y la de armado, donde el plan deja la lista del módulo. Pide el
«Solicitante»; confirma y termina «Fabricación: usuario»."""
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged

from odoo.addons.al_construction_material_request.tests.common import ConstructionRequestCommon


@tagged('post_install', '-at_install')
class TestPackage112Request(ConstructionRequestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.wh_cut = cls.warehouse
        cls.wh_asm = cls.env['stock.warehouse'].create({
            'name': 'Planta de armado (test 112)', 'code': 'T12A', 'company_id': cls.company.id})
        cls.replacement_type = cls.wh_cut.manu_type_id.copy({
            'name': 'Producción de piezas · reposición (test 112)', 'sequence_code': 'RP12',
            'construction_reason_required': True})
        cls.after_sales = cls.wh_asm.manu_type_id.copy({
            'name': 'Producción de piezas · posventa (test 112)', 'sequence_code': 'PV12',
            'construction_reason_required': True, 'sequence': 50})
        cls.head = new_test_user(
            cls.env, 'm11203_planta', groups='mrp.group_mrp_user,stock.group_stock_user',
            name='Jefe de planta (test 112)')
        cls.company.write({'construction_replacement_type_id': cls.replacement_type.id,
                           'construction_production_head_id': cls.head.id})
        cls.reason = cls.env['construction.production.reason'].create(
            {'name': 'Daño en el transporte (test 112)'})
        Product = cls.env['product.product']
        cls.module = Product.create({'name': 'MB01 cocina (test 112)', 'is_storable': True})
        cls.door = Product.create({'name': 'Puerta de alto (test 112)', 'is_storable': True})
        cls.loose = Product.create({'name': 'Pieza sin lista (test 112)', 'is_storable': True})

        def bom(product, picking_type):
            return cls.env['mrp.bom'].create({
                'product_tmpl_id': product.product_tmpl_id.id, 'product_qty': 1.0,
                'consumption': 'flexible', 'picking_type_id': picking_type.id,
                'bom_line_ids': [Command.create({'product_id': cls.cement.id, 'product_qty': 2})]})

        # La lista del módulo queda en la planta de la última etapa.
        cls.module_bom = bom(cls.module, cls.wh_asm.manu_type_id)
        cls.door_bom = bom(cls.door, cls.wh_cut.manu_type_id)

    def _replacement(self, product):
        replacement = self.env['construction.replacement.request'].with_user(
            self.requester).create({
                'project_id': self.site_a.id, 'product_id': product.id, 'product_qty': 1,
                'reason_id': self.reason.id})
        self.assertFalse(self.requester.has_group('mrp.group_mrp_user'))
        return replacement

    def test_module_goes_to_plant_of_its_bom(self):
        replacement = self._replacement(self.module)
        replacement.action_submit()
        production = replacement.sudo().production_id
        self.assertEqual(production.bom_id, self.module_bom)
        self.assertEqual(production.picking_type_id, self.after_sales,
                         'el tipo que pide motivo del almacén de la lista')
        self.assertEqual(replacement.picking_type_id, self.after_sales)
        self.assertEqual(production.move_raw_ids.product_id, self.cement)
        self.assertEqual(production.construction_reason_id, self.reason)
        self.assertEqual(production.user_id, self.head)
        self.assertIn(self.head, production.activity_ids.user_id)
        # La planta de armado fabrica con su usuario de Fabricación.
        self._set_stock(self.cement, self.wh_asm.lot_stock_id, 10)
        production = production.with_user(self.head).sudo(False)
        production.action_confirm()
        self.assertEqual(replacement.state, 'in_production')
        production.qty_producing = 1
        production.move_raw_ids.picked = True
        production.button_mark_done()
        self.assertEqual(replacement.state, 'produced')
        self.assertEqual(replacement.sudo().picking_id.location_id.warehouse_id, self.wh_asm)

    def test_first_reason_type_by_sequence(self):
        first = self.after_sales.copy({
            'name': 'Producción de piezas · garantía (test 112)', 'sequence_code': 'GA12',
            'sequence': 5})
        replacement = self._replacement(self.module)
        replacement.action_submit()
        self.assertEqual(replacement.sudo().production_id.picking_type_id, first)

    def test_bom_in_configured_plant_unchanged(self):
        replacement = self._replacement(self.door)
        replacement.action_submit()
        production = replacement.sudo().production_id
        self.assertEqual(production.picking_type_id, self.replacement_type)
        self.assertEqual(production.bom_id, self.door_bom)

    def test_without_bom_no_order(self):
        replacement = self._replacement(self.loose)
        with self.assertRaisesRegex(UserError, 'no tiene lista de materiales'):
            replacement.action_submit()
        self.assertFalse(self.env['mrp.production'].search(
            [('product_id', '=', self.loose.id)]))
        self.assertEqual(replacement.state, 'draft')

    def test_plant_without_reason_type_no_order(self):
        self.after_sales.construction_reason_required = False
        replacement = self._replacement(self.module)
        with self.assertRaisesRegex(UserError, 'no tiene una operación'):
            replacement.action_submit()
        self.assertFalse(self.env['mrp.production'].search(
            [('product_id', '=', self.module.id)]))
