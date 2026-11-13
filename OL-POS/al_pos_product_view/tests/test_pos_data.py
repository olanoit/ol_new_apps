# -*- coding: utf-8 -*-
"""Datos que el módulo envía al TPV."""
from lxml import etree

from odoo.addons.point_of_sale.tests.common import TestPoSCommon
from odoo.tests import tagged
from odoo.tools.misc import file_path


@tagged('post_install', '-at_install')
class TestPosProductViewData(TestPoSCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.basic_config

    def test_stock_del_almacen_del_tpv(self):
        """La vista de lista muestra el stock del almacén del TPV, no la
        suma de todos los almacenes de la compañía."""
        product = self.env['product.product'].create({
            'name': 'Producto stock por almacén',
            'is_storable': True,
            'available_in_pos': True,
        })
        pos_warehouse = self.config.picking_type_id.warehouse_id
        other_warehouse = self.env['stock.warehouse'].create({
            'name': 'Almacén ajeno al TPV',
            'code': 'ALPV2',
            'company_id': self.config.company_id.id,
        })
        Quant = self.env['stock.quant']
        Quant._update_available_quantity(product, pos_warehouse.lot_stock_id, 3)
        Quant._update_available_quantity(product, other_warehouse.lot_stock_id, 7)
        data = self.env['product.template']._load_pos_data_read(
            product.product_tmpl_id, self.config)
        self.assertEqual(data[0]['qty_available'], 3)

    def test_finanzas_ocultas_al_rol_minimo(self):
        """El bloque de finanzas reconstruido respeta la restricción de
        pos_hr para el rol «minimal» (su t-if cae en el marcador vacío)."""
        path = file_path('al_pos_product_view/static/src/switch_view/'
                         'overrides/product_info_popup/product_info_popup.xml')
        arch = etree.parse(path)
        self.assertTrue(arch.xpath("//div[@t-if='alShowFinancials']"))

    # --- Stock en vivo y filtros del catálogo (9.20261027) --------------------
    def _alpv_product(self, name, **vals):
        return self.env['product.product'].create({
            'name': name, 'available_in_pos': True, **vals,
        }).product_tmpl_id

    def test_stock_en_vivo_de_la_caja(self):
        """`get_pos_location_stock` devuelve el stock de la ubicación de la
        caja y su nombre, no la suma de la compañía."""
        template = self._alpv_product('Producto stock en vivo', is_storable=True)
        location = self.config.picking_type_id.default_location_src_id
        other_warehouse = self.env['stock.warehouse'].create({
            'name': 'Almacén ajeno al TPV (vivo)',
            'code': 'ALPV3',
            'company_id': self.config.company_id.id,
        })
        Quant = self.env['stock.quant']
        Quant._update_available_quantity(template.product_variant_id, location, 4)
        Quant._update_available_quantity(
            template.product_variant_id, other_warehouse.lot_stock_id, 9)
        result = self.env['product.template'].get_pos_location_stock(
            template.ids, self.config.id)
        self.assertEqual(result['stock'], {template.id: 4})
        self.assertEqual(result['location_name'], location.display_name)

    def test_filtro_con_stock(self):
        """El filtro «Con stock» solo recibe almacenables de la caja con
        existencias en su ubicación."""
        ProductTemplate = self.env['product.template']
        with_stock = self._alpv_product('Con stock', is_storable=True)
        empty = self._alpv_product('Sin stock', is_storable=True)
        service = self._alpv_product('Servicio', type='service')
        elsewhere = self._alpv_product('Solo en otro almacén', is_storable=True)
        not_in_pos = self._alpv_product(
            'Fuera del TPV', is_storable=True, available_in_pos=False)
        location = self.config.picking_type_id.default_location_src_id
        other_warehouse = self.env['stock.warehouse'].create({
            'name': 'Almacén ajeno al TPV (filtro)',
            'code': 'ALPV4',
            'company_id': self.config.company_id.id,
        })
        Quant = self.env['stock.quant']
        Quant._update_available_quantity(with_stock.product_variant_id, location, 2)
        Quant._update_available_quantity(not_in_pos.product_variant_id, location, 2)
        Quant._update_available_quantity(
            elsewhere.product_variant_id, other_warehouse.lot_stock_id, 6)

        ids = ProductTemplate.get_pos_in_stock_template_ids(self.config.id)

        self.assertIn(with_stock.id, ids)
        for template in (empty, service, elsewhere, not_in_pos):
            self.assertNotIn(template.id, ids, template.name)

    def test_productos_por_etiqueta(self):
        """El filtro por etiquetas trae del servidor los productos de la caja
        con alguna de las etiquetas, aunque el TPV no los haya cargado."""
        Tag = self.env['product.tag']
        tag_a, tag_b, tag_c = Tag.create([
            {'name': 'ALPV etiqueta A'},
            {'name': 'ALPV etiqueta B'},
            {'name': 'ALPV etiqueta C'},
        ])
        in_a = self._alpv_product('Con A', product_tag_ids=[(6, 0, tag_a.ids)])
        in_b = self._alpv_product('Con B', product_tag_ids=[(6, 0, tag_b.ids)])
        in_c = self._alpv_product('Con C', product_tag_ids=[(6, 0, tag_c.ids)])
        out_a = self._alpv_product(
            'Con A fuera del TPV', available_in_pos=False,
            product_tag_ids=[(6, 0, tag_a.ids)])

        ids = self.env['product.template'].get_pos_tag_template_ids(
            (tag_a | tag_b).ids, self.config.id)

        self.assertIn(in_a.id, ids)
        self.assertIn(in_b.id, ids)
        self.assertNotIn(in_c.id, ids)
        self.assertNotIn(out_a.id, ids)

    def test_limpiar_busqueda_por_caja(self):
        """«Limpiar la búsqueda al añadir» viene activado y se edita desde
        los ajustes de la caja."""
        self.assertTrue(self.config.iface_clear_search_on_add)
        settings = self.env['res.config.settings'].create({
            'pos_config_id': self.config.id,
        })
        self.assertTrue(settings.pos_iface_clear_search_on_add)
        settings.pos_iface_clear_search_on_add = False
        settings.execute()
        self.assertFalse(self.config.iface_clear_search_on_add)

    def test_plantillas_de_la_barra_de_filtros(self):
        """La barra del catálogo lleva el filtro, el control segmentado y el
        botón de actualizar stock; las tarjetas, el badge de stock."""
        base = 'al_pos_product_view/static/src/switch_view/'
        screen = etree.parse(file_path(
            base + 'overrides/product_screen/product_screen.xml'))
        self.assertTrue(screen.xpath('//AlpvCatalogFilter'))
        self.assertEqual(
            len(screen.xpath("//button[contains(@class, 'alpv-view-switch__option')]")), 2)
        self.assertTrue(screen.xpath("//button[@t-on-click='refreshStockNow']"))
        self.assertTrue(screen.xpath("//p[@t-elif='pos.alpvHasCatalogFilter']"))
        card = etree.parse(file_path(base + 'overrides/product_card/product_card.xml'))
        self.assertTrue(card.xpath("//span[contains(@t-attf-class, 'alpv-card-stock')]"))
