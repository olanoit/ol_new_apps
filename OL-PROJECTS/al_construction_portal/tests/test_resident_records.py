# -*- coding: utf-8 -*-
"""Residente en el portal de obra, entrega 2 (paquete 6: CR-56, CR-51 y
CR-52), con la obra de demostración de las contratas. Datos ficticios."""
from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged

from .test_portal_service import PHOTOS
from .test_resident import ResidentCommon


@tagged('post_install', '-at_install')
class TestResidentRecords(ResidentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.planner = new_test_user(cls.env, 'p6_planificador', name='Planificador (p6)',
                                    groups='al_construction_planner.group_planner_user')
        cls.project.user_id = cls.planner
        cls.client_contact = cls.env['res.partner'].create({
            'name': 'Representante del cliente (p6)', 'email': 'cliente.p6@example.com'})

    def _day(self):
        return fields.Date.to_string(fields.Date.context_today(
            self._service(self.resident_user)))

    # CR-56 ------------------------------------------------------------
    def test_daily_parts_and_close_day(self):
        base = {'project_id': self.project.id, 'weather': 'sunny',
                'restrictions': ['material'], 'photos': PHOTOS}
        self._service(self.foreman_user).daily_report(dict(
            base, uuid='p6-pd-1', occurrences='Visita de supervisión',
            staff=[{'name': 'Cuadrilla propia', 'source': 'own', 'count': 6}]))
        self._service(self.contractor_user).daily_report(dict(
            base, uuid='p6-pd-2', restrictions=[],
            staff=[{'name': 'Tabiquería', 'source': 'contract', 'count': 4}]))
        service = self._service(self.resident_user)
        data = service.sync(self.project.id)
        parts = data['resident']['parts']
        self.assertEqual(len(parts['reports']), 2)
        self.assertEqual(data['counters']['daily_to_review'], 2)
        self.assertFalse(parts['missing'])
        # Sin contacto del cliente, el PDF queda en la obra.
        result = service.close_day({'uuid': 'p6-cd-1', 'project_id': self.project.id,
                                    'date': self._day(), 'comment': 'Avance normal',
                                    'seen_report_ids': [r['id'] for r in parts['reports']]})
        site = self.env['construction.daily.report'].browse(int(result['ids']))
        self.assertEqual((site.kind, site.state, site.staff_total), ('site', 'closed', 10))
        self.assertTrue(site.restriction_material)
        self.assertEqual(set(site.member_report_ids.mapped('state')), {'reviewed'})
        self.assertTrue(self.project.message_ids.filtered(
            lambda m: m.attachment_ids.filtered(lambda a: a.mimetype == 'application/pdf')))
        with self.assertRaisesRegex(UserError, 'ya se cerró'):
            service.close_day({'uuid': 'p6-cd-2', 'project_id': self.project.id,
                               'date': self._day()})
        # El parte revisado ya no se reescribe desde el portal.
        with self.assertRaisesRegex(UserError, 'ya revisó'):
            self._service(self.foreman_user).daily_report(dict(base, uuid='p6-pd-3'))

    def test_close_day_sends_pdf_to_client(self):
        self.project.construction_client_contact_id = self.client_contact
        self._service(self.foreman_user).daily_report({
            'uuid': 'p6-pd-4', 'project_id': self.project.id,
            'staff': [{'name': 'Propio', 'count': 3}]})
        result = self._service(self.resident_user).close_day({
            'uuid': 'p6-cd-3', 'project_id': self.project.id, 'date': self._day()})
        site = self.env['construction.daily.report'].browse(int(result['ids']))
        self.assertEqual(site.sent_to_id, self.client_contact)
        message = site.message_ids.filtered(lambda m: self.client_contact in m.partner_ids)
        self.assertTrue(message.attachment_ids)
        # Solo el residente cierra el día.
        with self.assertRaises(AccessError):
            self._service(self.foreman_user).close_day({
                'uuid': 'p6-cd-4', 'project_id': self.project.id, 'date': self._day()})

    # CR-51 ------------------------------------------------------------
    def test_deduction_with_photo(self):
        service = self._service(self.resident_user)
        resident = service.sync(self.project.id)['resident']
        order = next(o for o in resident['orders'] if o['id'] == self.order.id)
        line = order['lines'][0]
        values = {'uuid': 'p6-dd-1', 'project_id': self.project.id,
                  'purchase_order_id': self.order.id, 'order_line_id': line['id'],
                  'type_id': resident['deduction_types'][0][0],
                  'description': 'Limpieza no realizada', 'qty': 2.0, 'photos': PHOTOS}
        with self.assertRaisesRegex(UserError, 'foto'):
            service.deduction(dict(values, photos=[]))
        result = service.deduction(values)
        deduction = self.env['construction.contract.deduction'].browse(int(result['ids']))
        self.assertEqual((deduction.state, deduction.purchase_order_id),
                         ('pending', self.order))
        self.assertAlmostEqual(deduction.amount, 2.0 * line['price_unit'], places=2)
        self.assertTrue(deduction.attachment_ids)
        self.assertEqual(deduction.create_uid, self.resident_user)
        # La contrata lo ve en su pantalla Valorización.
        orders = self._service(self.contractor_user).valuations(self.project.id)['orders']
        self.assertTrue(orders)
        other = self.env['purchase.order'].create({'partner_id': self.contractor.id})
        with self.assertRaises(AccessError):
            service.deduction(dict(values, uuid='p6-dd-2', purchase_order_id=other.id))

    # CR-52 ------------------------------------------------------------
    def test_crew_request_states(self):
        service = self._service(self.resident_user)
        task = self.wall.task_id
        result = service.crew_request({
            'uuid': 'p6-sc-1', 'project_id': self.project.id, 'kind': 'crew',
            'task_ids': [task.id], 'date_needed': self._day(),
            'people': [{'role': 'operario', 'count': 2}, {'role': 'peón', 'count': 1}],
            'comment': 'Para recuperar el atraso'})
        self.assertTrue(result['name'])
        activity = task.activity_ids.filtered(lambda a: a.user_id == self.planner)
        self.assertEqual(len(activity), 1)
        self.assertIn('2 operario', activity.summary)
        rows = service.sync(self.project.id)['resident']['crew_requests']
        self.assertEqual(rows[0]['state'], 'requested')
        # El planificador la cierra sin asignar: queda cancelada.
        activity.unlink()
        rows = service.sync(self.project.id)['resident']['crew_requests']
        self.assertEqual(rows[0]['state'], 'cancelled')
        # Contrata: la partida ya tiene contrata en el plan → asignada.
        service.crew_request({
            'uuid': 'p6-sc-2', 'project_id': self.project.id, 'kind': 'contract',
            'task_ids': [task.id], 'date_needed': self._day(), 'scope': '120 m²'})
        rows = service.sync(self.project.id)['resident']['crew_requests']
        self.assertEqual(rows[0]['state'], 'assigned')
        with self.assertRaisesRegex(UserError, 'partidas'):
            service.crew_request({'uuid': 'p6-sc-3', 'project_id': self.project.id,
                                  'kind': 'crew', 'task_ids': [], 'date_needed': self._day(),
                                  'people': [{'role': 'operario', 'count': 1}]})
