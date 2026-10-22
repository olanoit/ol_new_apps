# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import Command, fields
from odoo.addons.point_of_sale.tests.common import TestPoSCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestPosProductInfo(TestPoSCommon):
    """Ficha farmacéutica, principios activos y filtro de la caja."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.basic_config
        Ingredient = cls.env['pharmacy.ingredient']
        cls.paracetamol = Ingredient.create({'name': 'Paracetamol (prueba caja)', 'synonyms': 'Acetaminofén'})
        cls.generic = cls._pharmacy_product('Paracetamol 500 mg (prueba caja)', 0.20, 'generic_dci')
        cls.brand = cls._pharmacy_product('Marca 500 mg (prueba caja)', 0.60, 'innovator')
        cls.env['pharmacy.presentation'].create({
            'product_tmpl_id': cls.generic.id, 'name': 'Blíster', 'factor': 10, 'price': 1.50})

    @classmethod
    def _pharmacy_product(cls, name, price, kind):
        return cls.env['product.template'].create({
            'name': name, 'list_price': price, 'type': 'consu', 'is_storable': True, 'tracking': 'lot',
            'available_in_pos': True, 'pharmacy_ok': True, 'pharmacy_product_type': kind,
            'pharmacy_sale_condition': 'otc', 'pharmacy_sanitary_registry': 'EN-99999',
            'pharmacy_indications': 'Dolor y fiebre.',
            'pharmacy_dosage_form_id': cls.env.ref('al_pharmacy_base.dosage_form_tablet').id,
            'pharmacy_ingredient_line_ids': [Command.create({
                'ingredient_id': cls.paracetamol.id, 'strength': 500, 'strength_unit': 'mg'})],
        })

    def test_ingredients_and_info(self):
        self.assertEqual(self.generic.pharmacy_ingredient_ids, self.paracetamol)
        location = self.config.picking_type_id.default_location_src_id
        variant = self.generic.product_variant_id
        for name, days, quantity in (('L-LEJOS', 400, 30), ('L-CERCA', 40, 5)):
            lot = self.env['stock.lot'].create({
                'name': name, 'product_id': variant.id, 'company_id': self.env.company.id,
                'expiration_date': fields.Datetime.now() + timedelta(days=days)})
            self.env['stock.quant']._update_available_quantity(variant, location, quantity, lot_id=lot)
        info = self.generic.get_product_info_pos(0.20, 1, self.config.id)['pharmacy']
        labels = {row['label']: row['value'] for row in info['rows']}
        self.assertIn('500 mg', labels['Principio activo'])
        self.assertEqual(labels['Tipo'], 'Genérico en DCI')
        self.assertIn('EN-99999', labels['Registro sanitario'])
        self.assertEqual([lot['name'] for lot in info['lots']], ['L-CERCA', 'L-LEJOS'], 'FEFO')
        self.assertTrue(info['lots'][0]['near'])
        self.assertEqual(info['presentations'][0]['factor'], 10)
        self.assertEqual([e['id'] for e in info['equivalents']], [self.brand.id])
        self.assertEqual(info['texts'][0]['value'], 'Dolor y fiebre.')
        # Un producto que no es de farmacia no lleva la sección.
        other = self.env['product.template'].create({'name': 'Otro', 'available_in_pos': True})
        self.assertNotIn('pharmacy', other.get_product_info_pos(1, 1, self.config.id))

    def test_pos_loads_ingredients_and_replaces_tag_filter(self):
        self.config.pharmacy_ingredient_filter = True
        self.open_new_session()
        data = self.pos_session.load_data([])
        templates = {t['id']: t for t in data['product.template']}
        self.assertEqual(templates[self.generic.id]['pharmacy_ingredient_ids'], [self.paracetamol.id])
        self.assertIn(self.paracetamol.id, [i['id'] for i in data['pharmacy.ingredient']])
        config = data['pos.config'][0]
        self.assertTrue(config['pharmacy_ingredient_filter'])
        if 'iface_filter_products_by_tag' in config:
            self.assertFalse(config['iface_filter_products_by_tag'])

    def test_server_search_by_ingredient(self):
        """La búsqueda en el servidor encuentra por principio activo y sinónimo."""
        for word in ('paracetamol (prueba', 'acetaminof'):
            found = self.env['product.template'].search(
                [('pharmacy_ingredient_line_ids.ingredient_id', 'ilike', word)])
            self.assertIn(self.generic, found)

    def test_bioequivalents_in_info_and_pos_load(self):
        """Un bioequivalente vinculado a mano aparece en la ficha y se carga en
        la caja aunque no comparta la clave ni entre en la carga normal."""
        other = self.env['product.template'].create({
            'name': 'Paracetamol 500 mg cápsula (prueba caja)', 'list_price': 0.30, 'type': 'consu',
            'available_in_pos': True, 'pharmacy_ok': True, 'pharmacy_product_type': 'generic_brand',
            'pharmacy_bioequivalent': True})
        self.generic.pharmacy_bioequivalent_ids = [Command.link(other.id)]
        info = self.generic.get_product_info_pos(0.20, 1, self.config.id)['pharmacy']
        by_id = {e['id']: e for e in info['equivalents']}
        self.assertTrue(by_id[other.id]['bioequivalent'])
        self.assertFalse(by_id[self.brand.id]['bioequivalent'])
        self.open_new_session()
        data = self.pos_session.with_context(pos_limited_loading=False).load_data([])
        templates = {t['id']: t for t in data['product.template']}
        self.assertEqual(templates[self.generic.id]['pharmacy_bioequivalent_ids'], [other.id])
        self.assertEqual(templates[other.id]['pharmacy_bioequivalent_ids'], [self.generic.id])
