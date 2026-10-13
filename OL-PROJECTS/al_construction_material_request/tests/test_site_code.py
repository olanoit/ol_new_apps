# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import ConstructionRequestCommon


@tagged('post_install', '-at_install')
class TestSiteCode(ConstructionRequestCommon):
    """Alta de obra: código de obra, cuenta analítica y ubicación."""

    def test_code_from_name(self):
        self.company.construction_code_from_name = True
        Project = self.env['project.project']
        site = Project.create({'name': 'ROOFG-04-25 ROOF GARDEN', 'is_construction_site': True})
        self.assertEqual(site.construction_code, 'ROOFG-04-25')
        self.assertEqual(site.construction_location_id.name, 'ROOFG-04-25')
        self.assertEqual(site.construction_location_id.location_id,
                         self.company.construction_sites_location_id)
        self.assertEqual((site.account_id.code, site.account_id.name),
                         ('ROOFG-04-25', 'ROOF GARDEN'))
        # Renombrar la obra actualiza la cuenta analítica.
        site.name = 'ROOFG-04-25 ROOF GARDEN II'
        self.assertEqual(site.account_id.name, 'ROOF GARDEN II')
        # Un proyecto que no es obra no recibe cuenta ni ubicación propias.
        office = Project.create({'name': 'OFI-01 Oficina'})
        self.assertFalse(office.construction_location_id)

    def test_existing_location_is_reused(self):
        self.company.construction_code_from_name = True
        parent = self.company.construction_sites_location_id
        existing = self.env['stock.location'].create({
            'name': 'HQ7-02-25', 'usage': 'internal', 'location_id': parent.id})
        project = self.env['project.project'].create({'name': 'HQ7-02-25 HQ7'})
        project.is_construction_site = True
        self.assertEqual(project.construction_location_id, existing)

    def test_without_code_from_name(self):
        """Por defecto el código es manual y la ubicación lleva el nombre."""
        self.assertFalse(self.company.construction_code_from_name)
        self.assertFalse(self.site_a.construction_code)
        self.assertEqual(self.site_a.construction_location_id.name, self.site_a.name)
        self.assertTrue(self.site_a.account_id)
        site = self.env['project.project'].create({
            'name': 'Hospital C (test)', 'construction_code': 'HOSP-C', 'is_construction_site': True})
        self.assertEqual(site.construction_location_id.name, 'HOSP-C')
        self.assertEqual(site.account_id.code, 'HOSP-C')
        site.name = 'Hospital C bis (test)'
        self.assertEqual(site.construction_code, 'HOSP-C', 'el código manual no cambia')
