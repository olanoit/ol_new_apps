# -*- coding: utf-8 -*-
from unittest.mock import patch

from lxml import etree

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

NS = {'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
      'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'}


@tagged('post_install', '-at_install')
class TestStockTransfer(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        if not cls.company.vat:
            cls.company.partner_id.vat = '20512528458'
        district = cls.env['l10n_pe.res.city.district'].search([], limit=1)
        Partner = cls.env['res.partner']
        cls.addr_a = Partner.create({'name': 'Almacén Central', 'parent_id': cls.company.partner_id.id,
                                     'type': 'other', 'street': 'Av. Industrial 100',
                                     'l10n_pe_district': district.id, 'l10n_pe_annex_code': '0001'})
        cls.addr_b = Partner.create({'name': 'Almacén Obra', 'parent_id': cls.company.partner_id.id,
                                     'type': 'other', 'street': 'Jr. Las Obras 200',
                                     'l10n_pe_district': district.id, 'l10n_pe_annex_code': '0002'})
        Warehouse = cls.env['stock.warehouse']
        cls.wh_a = Warehouse.create({'name': 'TRF Central', 'code': 'TRA', 'partner_id': cls.addr_a.id,
                                     'company_id': cls.company.id})
        cls.wh_b = Warehouse.create({'name': 'TRF Obra', 'code': 'TRB', 'partner_id': cls.addr_b.id,
                                     'company_id': cls.company.id})
        cls.product = cls.env['product.product'].create({
            'name': 'Andamio', 'type': 'consu', 'is_storable': True, 'weight': 10.0})
        cls.owner = Partner.create({'name': 'Alquileres del Sur S.A.C.', 'vat': '20601234565'})
        Quant = cls.env['stock.quant']
        Quant._update_available_quantity(cls.product, cls.wh_a.lot_stock_id, 10.0)
        Quant._update_available_quantity(cls.product, cls.wh_a.lot_stock_id, 5.0, owner_id=cls.owner)

    def _internal(self, dest, qty=4.0, owner=None):
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.wh_a.int_type_id.id,
            'location_id': self.wh_a.lot_stock_id.id,
            'location_dest_id': dest.id,
            'owner_id': owner.id if owner else False,
            'move_ids': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': qty,
                                 'location_id': self.wh_a.lot_stock_id.id, 'location_dest_id': dest.id})],
        })
        picking.action_confirm()
        picking.action_assign()
        picking.move_ids.write({'quantity': qty, 'picked': True})
        picking.button_validate()
        return picking

    def _send(self, picking):
        sent = {}

        def sign(record, edi_str):
            sent['xml'] = etree.fromstring(edi_str)
            return {'cdr': b'<cdr/>'}

        picking.l10n_pe_edi_transport_type = '01'
        with patch.object(type(picking), '_l10n_pe_edi_sign', sign), \
                patch.object(type(picking), '_l10n_pe_edi_check_required_data', lambda self: None):
            picking.action_send_delivery_guide()
        return sent['xml']

    def _text(self, tree, path):
        return tree.xpath(path, namespaces=NS)[0].text

    def test_internal_transfer_between_establishments(self):
        picking = self._internal(self.wh_b.lot_stock_id)
        self.assertTrue(picking.l10n_pe_edi_guide_allowed)
        self.assertEqual(picking.l10n_pe_edi_origin_address_id, self.addr_a)
        self.assertEqual(picking.l10n_pe_edi_destination_address_id, self.addr_b)
        tree = self._send(picking)
        self.assertEqual(picking.l10n_pe_edi_reason_for_transfer, '04', 'motivo 04 por defecto')
        self.assertEqual(picking.l10n_pe_edi_status, 'sent')
        self.assertEqual(picking.partner_id, self.addr_b, 'punto de llegada: el almacén de destino')
        self.assertEqual(self._text(tree, '//cac:Shipment/cbc:HandlingCode'), '04')
        self.assertEqual(self._text(tree, '//cac:DeliveryCustomerParty//cbc:ID'), self.company.vat,
                         'destinatario = remitente')
        despatch = tree.xpath('//cac:DespatchAddress/cbc:AddressTypeCode', namespaces=NS)[0]
        delivery = tree.xpath('//cac:DeliveryAddress/cbc:AddressTypeCode', namespaces=NS)[0]
        self.assertEqual((despatch.text, despatch.get('listID')), ('0001', self.company.vat))
        self.assertEqual((delivery.text, delivery.get('listID')), ('0002', self.company.vat))
        self.assertIn('Av. Industrial 100', self._text(tree, '//cac:DespatchAddress//cbc:Line'))

    def test_no_guide_inside_the_same_establishment(self):
        shelf = self.env['stock.location'].create({'name': 'Estante', 'location_id': self.wh_a.lot_stock_id.id})
        picking = self._internal(shelf, qty=1.0)
        self.assertFalse(picking.l10n_pe_edi_guide_allowed)
        with self.assertRaises(UserError):
            self._send(picking)

    def test_third_party_goods(self):
        picking = self._internal(self.wh_b.lot_stock_id, qty=3.0, owner=self.owner)
        self.assertTrue(picking.l10n_pe_has_third_party_goods)
        self.assertEqual(picking.l10n_pe_third_party_owner_ids, self.owner)
        tree = self._send(picking)
        self.assertIn('Alquileres del Sur S.A.C.', self._text(tree, '/*/cbc:Note'),
                      'el propietario va en las observaciones del XML')
        html = self.env['ir.actions.report']._render_qweb_html(
            'al_l10n_pe_delivery_guide_report.action_report_guia_remision', picking.ids)[0].decode()
        self.assertIn('Propietario de los bienes', html)
        self.assertIn('Alquileres del Sur S.A.C.', html)

    def test_third_party_filters(self):
        Quant = self.env['stock.quant']
        third = [('owner_id', '!=', False), ('owner_id.l10n_pe_is_company_partner', '=', False)]
        quants = Quant.search(third + [('product_id', '=', self.product.id)])
        self.assertEqual(quants.owner_id, self.owner)
        self.assertTrue(self.company.partner_id.l10n_pe_is_company_partner)
        self.assertFalse(self.owner.l10n_pe_is_company_partner)
        own_picking = self._internal(self.wh_b.lot_stock_id, qty=1.0, owner=self.company.partner_id)
        self.assertFalse(own_picking.l10n_pe_has_third_party_goods, 'la compañía no es un tercero')

    def test_outgoing_guide(self):
        customer = self.env['res.partner'].create({
            'name': 'Cliente', 'vat': '20131312955', 'street': 'Calle 1',
            'l10n_pe_district': self.addr_a.l10n_pe_district.id,
            'l10n_latam_identification_type_id': self.env.ref('l10n_pe.it_RUC').id})
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.wh_a.out_type_id.id, 'partner_id': customer.id,
            'location_id': self.wh_a.lot_stock_id.id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
            'move_ids': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': 1.0,
                                 'location_id': self.wh_a.lot_stock_id.id,
                                 'location_dest_id': self.env.ref('stock.stock_location_customers').id})],
        })
        picking.l10n_pe_edi_transport_type = '01'
        self.assertTrue(picking.l10n_pe_edi_guide_allowed)
        self.assertEqual(picking.l10n_pe_edi_reason_for_transfer, '01', 'una salida sigue con venta')
        tree = etree.fromstring(picking._l10n_pe_edi_create_delivery_guide())
        self.assertEqual(self._text(tree, '//cac:DeliveryCustomerParty//cbc:ID'), '20131312955')
        despatch = tree.xpath('//cac:DespatchAddress/cbc:AddressTypeCode', namespaces=NS)[0]
        self.assertEqual((despatch.text, despatch.get('listID')), ('0001', self.company.vat),
                         'la partida informa el establecimiento anexo con el RUC de la empresa (OBS-4468)')

    # ------------------------------------------------------------------
    # Catálogo 20 completo y propuesta del motivo
    # ------------------------------------------------------------------

    def _supplier(self):
        return self.env['res.partner'].create({
            'name': 'Proveedor Andino S.A.C.', 'vat': '20100070970', 'street': 'Av. Proveedores 50',
            'l10n_pe_district': self.addr_a.l10n_pe_district.id,
            'l10n_latam_identification_type_id': self.env.ref('l10n_pe.it_RUC').id})

    def _receipt(self, partner, qty=2.0):
        supplier_loc = self.env.ref('stock.stock_location_suppliers')
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.wh_a.in_type_id.id, 'partner_id': partner.id,
            'location_id': supplier_loc.id, 'location_dest_id': self.wh_a.lot_stock_id.id,
            'move_ids': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': qty,
                                 'location_id': supplier_loc.id, 'location_dest_id': self.wh_a.lot_stock_id.id})],
        })
        picking.action_confirm()
        picking.move_ids.write({'quantity': qty, 'picked': True})
        picking.button_validate()
        return picking

    def test_catalog_20_reasons(self):
        reasons = dict(self.env['stock.picking']._fields['l10n_pe_edi_reason_for_transfer']
                       ._description_selection(self.env))
        for code in ('01', '02', '03', '04', '05', '06', '07', '08', '09', '13', '14', '17', '18'):
            self.assertIn(code, reasons, 'motivo %s del catálogo 20' % code)

    def test_purchase_picked_up_by_the_company(self):
        supplier = self._supplier()
        picking = self._receipt(supplier)
        picking.l10n_pe_edi_transport_type = '02'
        self.assertEqual(picking.l10n_pe_edi_reason_for_transfer, '02', 'una recepción propone 02 Compra')
        self.assertTrue(picking.l10n_pe_edi_guide_allowed)
        self.assertEqual(picking.l10n_pe_edi_origin_address_id, supplier, 'parte del proveedor')
        self.assertEqual(picking.l10n_pe_edi_destination_address_id, self.addr_a, 'llega al almacén')
        tree = etree.fromstring(picking._l10n_pe_edi_create_delivery_guide())
        self.assertEqual(self._text(tree, '//cac:DeliveryCustomerParty//cbc:ID'), self.company.vat,
                         'en una compra la empresa es destinataria')
        despatch = tree.xpath('//cac:DespatchAddress/cbc:AddressTypeCode', namespaces=NS)[0]
        delivery = tree.xpath('//cac:DeliveryAddress/cbc:AddressTypeCode', namespaces=NS)[0]
        self.assertEqual((despatch.text, despatch.get('listID')), ('0', '20100070970'))
        self.assertEqual((delivery.text, delivery.get('listID')), ('0001', self.company.vat))
        self.assertIn('Av. Proveedores 50', self._text(tree, '//cac:DespatchAddress//cbc:Line'))
        self.assertIn('Av. Industrial 100', self._text(tree, '//cac:DeliveryAddress//cbc:Line'))
        html = self.env['ir.actions.report']._render_qweb_html(
            'al_l10n_pe_delivery_guide_report.action_report_guia_remision', picking.ids)[0].decode()
        self.assertIn('Av. Industrial 100', html, 'la llegada del PDF es el almacén')

    def test_receipt_without_incoming_reason_has_no_guide(self):
        picking = self._receipt(self._supplier())
        picking.write({'l10n_pe_edi_transport_type': '02', 'l10n_pe_edi_reason_for_transfer': '01'})
        self.assertFalse(picking.l10n_pe_edi_guide_allowed)
        with self.assertRaises(UserError, msg='si el proveedor trae los bienes, la guía es suya'):
            picking.action_send_delivery_guide()

    def test_return_to_the_owner_proposes_06(self):
        customers = self.env.ref('stock.stock_location_customers')
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.wh_a.out_type_id.id, 'partner_id': self.owner.id,
            'owner_id': self.owner.id,
            'location_id': self.wh_a.lot_stock_id.id, 'location_dest_id': customers.id,
            'move_ids': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': 2.0,
                                 'location_id': self.wh_a.lot_stock_id.id, 'location_dest_id': customers.id})],
        })
        picking.action_confirm()
        picking.action_assign()
        picking.move_ids.write({'quantity': 2.0, 'picked': True})
        picking.button_validate()
        picking.l10n_pe_edi_transport_type = '01'
        self.assertEqual(picking.l10n_pe_edi_reason_for_transfer, '06',
                         'devolver los bienes a su propietario propone 06 Devolución')

    def test_picking_type_default_reason(self):
        self.wh_a.out_type_id.l10n_pe_edi_default_reason = '05'
        customers = self.env.ref('stock.stock_location_customers')
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.wh_a.out_type_id.id, 'partner_id': self._supplier().id,
            'location_id': self.wh_a.lot_stock_id.id, 'location_dest_id': customers.id,
        })
        picking.l10n_pe_edi_transport_type = '01'
        self.assertEqual(picking.l10n_pe_edi_reason_for_transfer, '05', 'motivo del tipo de operación')

    def test_other_requires_description(self):
        picking = self._internal(self.wh_b.lot_stock_id, qty=1.0)
        picking.write({'l10n_pe_edi_transport_type': '01', 'l10n_pe_edi_reason_for_transfer': '13'})
        self.assertTrue(any('13' in error for error in picking._l10n_pe_edi_generate_missing_data_error_list()))
        picking.l10n_pe_edi_reason_description = 'Exhibición en feria'
        self.assertFalse(any('13' in error for error in picking._l10n_pe_edi_generate_missing_data_error_list()))
        tree = etree.fromstring(picking._l10n_pe_edi_create_delivery_guide())
        self.assertEqual(self._text(tree, '//cac:Shipment/cbc:HandlingInstructions'), 'Exhibición en feria')

    def test_import_requires_customs_declaration(self):
        picking = self._receipt(self._supplier())
        picking.write({'l10n_pe_edi_transport_type': '01', 'l10n_pe_edi_reason_for_transfer': '08'})
        self.assertTrue(picking.l10n_pe_edi_guide_allowed)
        self.assertTrue(any('DAM' in error for error in picking._l10n_pe_edi_generate_missing_data_error_list()))
        picking.write({'l10n_pe_edi_related_document_type': '50', 'l10n_pe_edi_document_number': '118-2026-10-000123'})
        self.assertFalse(any('DAM' in error for error in picking._l10n_pe_edi_generate_missing_data_error_list()))
        tree = etree.fromstring(picking._l10n_pe_edi_create_delivery_guide())
        self.assertEqual(self._text(tree, '//cac:Shipment/cbc:HandlingCode'), '08')
        self.assertEqual(self._text(tree, '//cac:Shipment/cbc:HandlingInstructions'), 'Importación')
