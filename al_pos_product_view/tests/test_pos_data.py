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
