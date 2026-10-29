# -*- coding: utf-8 -*-
"""Obra desde la venta con código de obra y foto de evidencia por etapa
(lo que hacían las automatizaciones manuales «Alta de obra» y «Tareo de obra»)."""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSiteFromSaleCode(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.construction_code_from_name = True
        cls.partner = cls.env['res.partner'].create({'name': 'Inmobiliaria (test)'})
        cls.service = cls.env['product.product'].create({
            'name': 'Muebles de melamina (test)', 'type': 'service',
            'service_tracking': 'project_only', 'construction_creates_site': True})

    def _confirm(self, **vals):
        order = self.env['sale.order'].create(dict({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {'product_id': self.service.id, 'price_unit': 1000.0})]},
            **vals))
        order.action_confirm()
        return order.order_line.project_id

    def test_site_named_with_code_and_site_name(self):
        project = self._confirm(client_order_ref='ROOFG-04-25', construction_site_name='ROOF GARDEN')
        self.assertEqual(project.name, 'ROOFG-04-25 ROOF GARDEN')
        self.assertEqual(project.construction_code, 'ROOFG-04-25')
        self.assertEqual((project.account_id.code, project.account_id.name),
                         ('ROOFG-04-25', 'ROOF GARDEN'))
        self.assertEqual(project.construction_location_id.name, 'ROOFG-04-25')

    def test_site_without_site_name_uses_code(self):
        project = self._confirm(client_order_ref='HQ9-01-26')
        self.assertEqual(project.name, 'HQ9-01-26 HQ9-01-26')
        self.assertEqual(project.construction_code, 'HQ9-01-26')

    def test_stage_requires_evidence_photo(self):
        project = self.env['project.project'].create({'name': 'Tareo (test)'})
        done = self.env['project.task.type'].create({
            'name': 'Hecha', 'project_ids': [(6, 0, project.ids)],
            'construction_requires_photo': True})
        todo = self.env['project.task.type'].create({
            'name': 'Por hacer', 'project_ids': [(6, 0, project.ids)]})
        task = self.env['project.task'].create({
            'name': 'Mueble MB01 (test)', 'project_id': project.id, 'stage_id': todo.id})
        with self.assertRaises(UserError):
            task.stage_id = done
        self.env['ir.attachment'].create({
            'name': 'mb01.jpg', 'raw': b'foto',
            'res_model': 'project.task', 'res_id': task.id})
        task.invalidate_recordset(['message_attachment_count'])
        task.stage_id = done
        self.assertEqual(task.stage_id, done)
        # Otra etapa sin la marca no exige nada.
        other = self.env['project.task'].create({
            'name': 'Mueble MA01 (test)', 'project_id': project.id, 'stage_id': todo.id})
        other.stage_id = self.env['project.task.type'].create({
            'name': 'Revisión', 'project_ids': [(6, 0, project.ids)]})
