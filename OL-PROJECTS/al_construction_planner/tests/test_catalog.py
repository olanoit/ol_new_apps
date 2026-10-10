# -*- coding: utf-8 -*-
from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestCatalog(PlannerCommon):

    def test_typology_reference_amounts(self):
        """P-12: tipología 01 con 7 módulos, armado S/ 54.00 por ambiente."""
        typology = self.typology
        self.assertEqual(typology.module_count, 7)
        self.assertAlmostEqual(typology.ml_low, 2.12)
        self.assertAlmostEqual(typology.ml_high, 2.10)
        self.assertAlmostEqual(typology.module_assembly_amount, 54.0)
        # 5.79 + 25.50 de armado y 38.16 + 37.80 de instalación a la tarifa de la obra.
        self.assertAlmostEqual(typology.space_contract_amount, 107.25)

    def test_typology_ml_from_widths(self):
        """Con anchos, los ML se calculan de los módulos; sin ellos, se escriben."""
        typology = self.typology.copy({'code': '01-ETO', 'ml_low': 2.12, 'ml_high': 2.10})
        self.assertAlmostEqual(typology.ml_low, 2.12, msg='Sin anchos se conservan a mano')
        typology.module_line_ids[0].write({'width_mm': 600, 'ml_group': 'low'})
        typology.module_line_ids[1].write({'width_mm': 450, 'ml_group': 'low'})
        typology.module_line_ids[2].write({'width_mm': 900, 'ml_group': 'high'})
        self.assertAlmostEqual(typology.ml_low, 1.05)
        self.assertAlmostEqual(typology.ml_high, 0.90)

    def test_rate_priority(self):
        """Obra y contrata › obra › contrata › tarifa base › precio de la actividad."""
        Rate = self.env['construction.labor.rate']
        activity = self.act_dowel
        other_project = self.env['project.project'].create({'name': 'Otra obra (test)'})
        self.assertEqual(activity._get_rate(self.project, self.contractor)[0], 8.0,
                         'Sin tarifas: precio de la actividad')
        Rate.create({'activity_id': activity.id, 'price': 8.5, 'retention_pct': 10.0})
        Rate.create({'activity_id': activity.id, 'partner_id': self.contractor.id, 'price': 9.0})
        Rate.create({'activity_id': activity.id, 'project_id': self.project.id, 'price': 9.5})
        Rate.create({'activity_id': activity.id, 'project_id': self.project.id,
                     'partner_id': self.contractor.id, 'price': 10.0})
        self.assertEqual(activity._get_rate(self.project, self.contractor)[0], 10.0)
        self.assertEqual(activity._get_rate(self.project)[0], 9.5)
        self.assertEqual(activity._get_rate(other_project, self.contractor)[0], 9.0)
        price, retention, rate = activity._get_rate(other_project)
        self.assertEqual((price, retention), (8.5, 10.0))
        self.assertFalse(rate.project_id or rate.partner_id)

    def test_rate_validity(self):
        Rate = self.env['construction.labor.rate']
        activity = self.act_screw
        Rate.create({'activity_id': activity.id, 'price': 6.0, 'date_to': date(2026, 6, 30)})
        Rate.create({'activity_id': activity.id, 'price': 6.5, 'date_from': date(2026, 7, 1)})
        self.assertEqual(activity._get_rate(date=date(2026, 3, 1))[0], 6.0)
        self.assertEqual(activity._get_rate(date=date(2026, 10, 1))[0], 6.5)

    def test_rate_no_overlap(self):
        Rate = self.env['construction.labor.rate']
        Rate.create({'activity_id': self.act_hood.id, 'price': 7.0,
                     'date_from': date(2026, 1, 1), 'date_to': date(2026, 12, 31)})
        with self.assertRaises(ValidationError):
            Rate.create({'activity_id': self.act_hood.id, 'price': 7.5,
                         'date_from': date(2026, 6, 1)})
        # Otra combinación de obra no se superpone.
        Rate.create({'activity_id': self.act_hood.id, 'project_id': self.project.id,
                     'price': 7.5, 'date_from': date(2026, 6, 1)})
        with self.assertRaises(ValidationError):
            Rate.create({'activity_id': self.act_hood.id, 'price': 7.0,
                         'date_from': date(2026, 3, 1), 'date_to': date(2026, 2, 1)})

    def test_activity_single_measure(self):
        with self.assertRaises(ValidationError):
            self.act_doors.write({'module_level': True, 'ml_based': True})
