# -*- coding: utf-8 -*-
"""Detalle de bienes y peso bruto de la guía de remisión (GRE).

El detalle de la guía se agrupa por producto y unidad de medida —dos
movimientos del mismo producto salen en una sola línea— y arrastra las
series/lotes movidos. El peso bruto es campo obligatorio del XML de la
GRE: si se enviara en 0 SUNAT rechaza el comprobante, de ahí el respaldo
al peso de envío.
"""
from datetime import date

from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestGuideGrouping(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({
            'vat': '20512528458',
            'country_id': cls.env.ref('base.pe').id,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente Guía Agrupada SAC',
            'vat': '20557912879',
            'l10n_latam_identification_type_id': cls.env.ref('l10n_pe.it_RUC').id,
            'l10n_pe_district': cls.env.ref('l10n_pe.district_pe_030101').id,
            'street': 'Av. Prueba 456',
        })
        cls.operator = cls.env['res.partner'].create({
            'name': 'Conductor Agrupación',
            'vat': '70025426',
            'l10n_latam_identification_type_id': cls.env.ref('l10n_pe.it_DNI').id,
        })
        cls.vehicle = cls.env['l10n_pe_edi.vehicle'].create({
            'name': 'Camión agrupación',
            'license_plate': 'XYZ-987',
            'operator_id': cls.operator.id,
        })
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.company.id)], limit=1)
        cls.uom_unit = cls.env.ref('uom.product_uom_unit')
        cls.uom_dozen = cls.env.ref('uom.product_uom_dozen')
        cls.product = cls.env['product.product'].create({
            'name': 'Producto agrupable', 'is_storable': True, 'weight': 2.0,
        })
        cls.product_lot = cls.env['product.product'].create({
            'name': 'Producto con lote', 'is_storable': True,
            'weight': 1.0, 'tracking': 'lot',
        })

    # ------------------------------------------------------------------
    def _picking(self, lines):
        """``lines`` = [(producto, cantidad, uom|None)].

        Se crea por ORM y no con ``Form``: ``product_uom`` no está en la
        vista de movimientos del albarán, así que el formulario no deja
        fijar la unidad de medida por línea.
        """
        picking_type = self.warehouse.out_type_id
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'partner_id': self.partner.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': picking_type.default_location_dest_id.id,
            'l10n_pe_edi_transport_type': '02',
            'l10n_pe_edi_operator_id': self.operator.id,
            'l10n_pe_edi_vehicle_id': self.vehicle.id,
            'l10n_pe_edi_reason_for_transfer': '01',
            'l10n_pe_edi_departure_start_date': date.today(),
            'move_ids': [Command.create({
                # v19: stock.move ya no tiene campo `name`.
                'product_id': product.id,
                'product_uom_qty': qty,
                'product_uom': (uom or product.uom_id).id,
                'location_id': picking_type.default_location_src_id.id,
                'location_dest_id': picking_type.default_location_dest_id.id,
            }) for product, qty, uom in lines],
        })
        picking.action_confirm()
        return picking

    # ------------------------------------------------------------------
    # Agrupación del detalle
    # ------------------------------------------------------------------
    def test_same_product_same_uom_is_one_line(self):
        """Dos movimientos del mismo producto y UdM salen como una línea.

        El segundo movimiento se añade después de confirmar: al crearlos
        juntos, Odoo los fusiona y no habría nada que agrupar.
        """
        picking = self._picking([(self.product, 3.0, self.uom_unit)])
        picking_type = self.warehouse.out_type_id
        self.env['stock.move'].create({
            'picking_id': picking.id,
            'product_id': self.product.id,
            'product_uom_qty': 2.0,
            'product_uom': self.uom_unit.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': picking_type.default_location_dest_id.id,
        })._action_confirm(merge=False)
        self.assertEqual(len(picking.move_ids), 2, 'deben quedar dos movimientos')
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        grouped = picking._get_grouped_move_lines()
        self.assertEqual(len(grouped), 1, 'debe consolidarse en una línea')
        self.assertEqual(grouped[0]['quantity'], 5.0)
        self.assertEqual(grouped[0]['uom'], self.uom_unit)

    def test_different_uom_are_separate_lines(self):
        """Mismo producto con UdM distinta no se puede sumar: dos líneas."""
        picking = self._picking([(self.product, 3.0, self.uom_unit),
                                 (self.product, 1.0, self.uom_dozen)])
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        grouped = picking._get_grouped_move_lines()
        self.assertEqual(len(grouped), 2)
        self.assertEqual({g['uom'] for g in grouped},
                         {self.uom_unit, self.uom_dozen})

    def test_moves_without_quantity_are_skipped(self):
        """Un movimiento sin cantidad hecha no entra en el detalle."""
        picking = self._picking([(self.product, 4.0, self.uom_unit)])
        picking.move_ids.quantity = 0.0
        self.assertFalse(picking._get_grouped_move_lines())

    def test_lots_are_collected(self):
        """Las series/lotes movidos se listan en su línea del detalle."""
        picking = self._picking([(self.product_lot, 2.0, self.uom_unit)])
        lot = self.env['stock.lot'].create({
            'name': 'LOTE-GRE-001', 'product_id': self.product_lot.id})
        move = picking.move_ids
        move.move_line_ids.unlink()
        self.env['stock.move.line'].create({
            'move_id': move.id,
            'picking_id': picking.id,
            'product_id': self.product_lot.id,
            'lot_id': lot.id,
            'quantity': 2.0,
            'location_id': move.location_id.id,
            'location_dest_id': move.location_dest_id.id,
        })
        grouped = picking._get_grouped_move_lines()
        self.assertEqual(len(grouped), 1)
        self.assertIn('LOTE-GRE-001', grouped[0]['lots'])

    # ------------------------------------------------------------------
    # Peso bruto
    # ------------------------------------------------------------------
    def test_weight_from_lines_is_kept(self):
        """Con peso en las líneas no se pisa con el peso de envío."""
        picking = self._picking([(self.product, 3.0, self.uom_unit)])
        picking.move_ids.quantity = 3.0
        picking.shipping_weight = 999.0
        picking._cal_weight()
        self.assertAlmostEqual(picking.weight, 6.0, 2,
                               '3 unidades × 2 kg')

    def test_delivery_guide_values_recompute_weight(self):
        """El XML de la GRE se arma con el peso ya recalculado, nunca 0."""
        self.product.weight = 0.0
        picking = self._picking([(self.product, 3.0, self.uom_unit)])
        picking.move_ids.quantity = 3.0
        picking.shipping_weight = 15.0
        picking.weight = 0.0
        values = picking._l10n_pe_edi_get_delivery_guide_values()
        self.assertTrue(values)
        self.assertGreater(picking.weight, 0.0,
                           'SUNAT rechaza la GRE con peso bruto 0')
        self.product.weight = 2.0

    # ------------------------------------------------------------------
    # Acción de impresión
    # ------------------------------------------------------------------
    def test_print_action_targets_own_report(self):
        """El botón imprime el reporte propio de guía de remisión."""
        picking = self._picking([(self.product, 1.0, self.uom_unit)])
        action = picking.action_print_guia_remision()
        expected = self.env.ref(
            'al_l10n_pe_delivery_guide_report.action_report_guia_remision')
        self.assertEqual(action['report_name'], expected.report_name)

    def test_report_shows_plate_and_partner(self):
        """La guía impresa lleva placa del vehículo y datos del destinatario."""
        picking = self._picking([(self.product, 2.0, self.uom_unit)])
        picking.move_ids.quantity = 2.0
        report = self.env.ref(
            'al_l10n_pe_delivery_guide_report.action_report_guia_remision')
        html, _ = report._render_qweb_html(report.report_name, picking.ids)
        self.assertIn(b'XYZ-987', html, 'falta la placa del vehículo')
        self.assertIn('20557912879'.encode(), html, 'falta el RUC del destinatario')
