# -*- coding: utf-8 -*-
from datetime import date

from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestDeliveryGuideReport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({
            'vat': '20512528458',
            'country_id': cls.env.ref('base.pe').id,
        })
        cls.district = cls.env.ref('l10n_pe.district_pe_030101')
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente Guía SAC',
            'vat': '20557912879',
            'l10n_latam_identification_type_id': cls.env.ref('l10n_pe.it_RUC').id,
            'l10n_pe_district': cls.district.id,
            'street': 'Av. Prueba 123',
        })
        cls.operator = cls.env['res.partner'].create({
            'name': 'Conductor de Prueba',
            'vat': '70025425',
            'l10n_latam_identification_type_id': cls.env.ref('l10n_pe.it_DNI').id,
        })
        cls.vehicle = cls.env['l10n_pe_edi.vehicle'].create({
            'name': 'Camión de prueba',
            'license_plate': 'ABC-123',
            'operator_id': cls.operator.id,
        })
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.company.id)], limit=1)
        cls.product = cls.env['product.product'].create({
            'name': 'Producto Guía', 'is_storable': True, 'weight': 1.0,
        })

    def _create_picking(self):
        picking_form = Form(self.env['stock.picking'].with_context(
            default_picking_type_id=self.warehouse.out_type_id.id))
        picking_form.partner_id = self.partner
        with picking_form.move_ids.new() as line:
            line.product_id = self.product
            line.product_uom_qty = 5.0
        picking = picking_form.save()
        picking.write({
            'l10n_pe_edi_transport_type': '02',
            'l10n_pe_edi_operator_id': self.operator.id,
            'l10n_pe_edi_vehicle_id': self.vehicle.id,
            'l10n_pe_edi_reason_for_transfer': '01',
            'l10n_pe_edi_departure_start_date': date.today(),
        })
        picking.action_confirm()
        picking.move_ids.write({'quantity': 5.0, 'picked': True})
        picking.button_validate()
        return picking

    def test_grouped_move_lines(self):
        picking = self._create_picking()
        grouped = picking._get_grouped_move_lines()
        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped[0]['product'], self.product)
        self.assertEqual(grouped[0]['quantity'], 5.0)

    def test_weight_fallback_to_shipping_weight(self):
        # producto sin peso: la suma de pesos de línea da 0 y el compute
        # debe caer al shipping_weight
        self.product.weight = 0.0
        picking = self._create_picking()
        picking.shipping_weight = 42.0
        picking._cal_weight()
        self.assertEqual(picking.weight, 42.0)
        self.product.weight = 1.0

    def test_report_renders_without_error(self):
        picking = self._create_picking()
        report = self.env.ref(
            'al_l10n_pe_delivery_guide_report.action_report_guia_remision')
        html, _ = report._render_qweb_html(report.report_name, picking.ids)
        self.assertTrue(html)
