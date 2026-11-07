# -*- coding: utf-8 -*-
"""Cambio pedido por el cliente en obra (paquete 6, CR-53). Datos
ficticios."""
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.al_construction_portal.tests.test_portal_service import PHOTOS
from odoo.addons.al_construction_portal.tests.test_resident import ResidentCommon

SIGNATURE = 'data:image/png;base64,' + PHOTOS[0]['data']


@tagged('post_install', '-at_install')
class TestPortalChange(ResidentCommon):

    def test_change_with_signature_and_record(self):
        contact = self.env['res.partner'].create({
            'name': 'Supervisor del cliente (p6)', 'email': 'supervisor.p6@example.com'})
        self.project.construction_client_contact_id = contact
        service = self._service(self.resident_user)
        self.assertTrue(service.sync(self.project.id)['resident']['features']['change_order'])
        values = {'uuid': 'p6-cc-1', 'project_id': self.project.id, 'kind': 'additional',
                  'description': 'Agregar un tabique en la sala de reuniones',
                  'task_ids': [self.wall.task_id.id], 'qty_estimate': '12 m²',
                  'rep_name': 'Ana Torres', 'rep_role': 'Supervisora', 'photos': PHOTOS,
                  'signature': SIGNATURE}
        with self.assertRaisesRegex(UserError, 'firma'):
            service.change_order(dict(values, signature=''))
        result = service.change_order(values)
        change = self.env['construction.change.order'].browse(int(result['ids']))
        self.assertEqual((change.state, change.kind, change.requested_by),
                         ('draft', 'additional', 'client'))
        self.assertEqual(change.construction_portal_user_id, self.resident_user)
        self.assertEqual(change.create_uid, self.resident_user)
        self.assertTrue(change.construction_client_signature)
        self.assertEqual(change.construction_portal_task_ids, self.wall.task_id)
        self.assertEqual(change.construction_record_sent_to_id, contact)
        message = change.message_ids.filtered(lambda m: contact in m.partner_ids)
        self.assertEqual(message.attachment_ids.mimetype, 'application/pdf')
        # Envío repetido sin señal: no duplica.
        self.assertTrue(service.change_order(values)['duplicate'])
