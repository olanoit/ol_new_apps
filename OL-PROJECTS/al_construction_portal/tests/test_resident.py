# -*- coding: utf-8 -*-
"""Residente en el portal de obra (paquete 6, entrega 1: CR-48, CR-49 y
CR-50), con la obra de demostración de las contratas. Datos ficticios."""
from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import new_test_user, tagged

from .test_portal_service import PHOTOS
from odoo.addons.al_construction_planner_subcontract.tests.test_contract_terms_creval import (
    ContractTermsCommon,
)


@tagged('post_install', '-at_install')
class TestResident(ContractTermsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Member = env['construction.portal.member']
        cls.contractor_user = new_test_user(env, 'p6_contrata', groups='base.group_portal',
                                            name='Supervisor de contrata (p6)')
        cls.contractor_user.partner_id.parent_id = cls.contractor
        cls.foreman_user = new_test_user(env, 'p6_capataz', groups='base.group_portal',
                                         name='Capataz (p6)')
        cls.resident_user = new_test_user(env, 'p6_residente', groups='base.group_portal',
                                          name='Residente locador (p6)')
        Member.create({'project_id': cls.project.id, 'user_id': cls.contractor_user.id,
                       'role': 'contractor', 'partner_id': cls.contractor.id})
        Member.create({'project_id': cls.project.id, 'user_id': cls.foreman_user.id,
                       'role': 'foreman'})
        # Locador: sin ficha de empleado.
        cls.resident_member = Member.create({
            'project_id': cls.project.id, 'user_id': cls.resident_user.id, 'role': 'resident',
            'is_default_approver': True})
        _wizard, cls.order = cls._assign(cls)
        cls.order.button_confirm()
        cls.wall = cls.plan.line_ids.filtered(lambda l: l.activity_id == cls.act_wall)

    def _service(self, user, login='password'):
        return self.env['construction.portal.service'].with_user(user).with_context(
            construction_portal_login=login)

    def _report(self, qty, uuid, **extra):
        values = dict({
            'uuid': uuid, 'project_id': self.project.id, 'plan_line_id': self.wall.id,
            'date': fields.Date.to_string(fields.Date.context_today(
                self._service(self.contractor_user))),
            'qty': qty, 'photos': PHOTOS, 'latitude': -12.1, 'longitude': -77.0}, **extra)
        result = self._service(self.contractor_user).progress(values)
        return self.env['construction.task.progress'].browse(int(result['ids']))

    # CR-48 ------------------------------------------------------------
    def test_role_and_scope(self):
        """El residente ve lo del capataz y la oficina técnica y sus bandejas;
        con el QR y el PIN no tiene el papel Residente; otra obra, rechazada."""
        self.assertEqual(self.project.construction_portal_resident_id, self.resident_user)
        data = self._service(self.resident_user).sync(self.project.id)
        self.assertEqual(data['roles'], ['foreman', 'office', 'resident'])
        self.assertIn('resident', data)
        self.assertIn('inbox_progress', data['counters'])
        me = self._service(self.resident_user).me()
        self.assertIn('resident', me['projects'][0]['roles'])
        qr = self._service(self.resident_user, login='qr').sync(self.project.id)
        self.assertNotIn('resident', qr['roles'])
        self.assertNotIn('resident', qr)
        with self.assertRaises(AccessError):
            self._service(self.resident_user, login='qr').resident_progress({
                'uuid': 'qr-1', 'project_id': self.project.id, 'action': 'validate',
                'items': [{'id': 1, 'seen_qty': 1}]})
        other = self.project.copy({'name': 'Otra obra (p6)'})
        with self.assertRaises(AccessError):
            self._service(self.resident_user).sync(other.id)
        # Solo un residente puede ser aprobador por defecto.
        with self.assertRaises(ValidationError):
            self.env['construction.portal.member'].search([
                ('user_id', '=', self.foreman_user.id)]).is_default_approver = True

    # CR-49 ------------------------------------------------------------
    def test_validate_reject_rework(self):
        first = self._report(20.0, 'p6-av-1')
        second = self._report(10.0, 'p6-av-2')
        third = self._report(5.0, 'p6-av-3')
        service = self._service(self.resident_user)
        rows = service.sync(self.project.id)['resident']['progress']
        self.assertEqual({r['id'] for r in rows}, {first.id, second.id, third.id})
        row = next(r for r in rows if r['id'] == first.id)
        self.assertEqual(row['reported_by'], self.contractor_user.name)
        self.assertTrue(row['photos'])
        reasons = service.sync(self.project.id)['resident']['reasons']
        correct = reasons['progress_correct'][0][0]
        reject = reasons['progress_reject'][0][0]
        # Validar corrigiendo a la baja: pide motivo; el residente es el autor.
        with self.assertRaisesRegex(UserError, 'motivo'):
            service.resident_progress({
                'uuid': 'p6-val-0', 'project_id': self.project.id, 'action': 'validate',
                'items': [{'id': first.id, 'seen_qty': 20.0}], 'qty': 18.0})
        service.resident_progress({
            'uuid': 'p6-val-1', 'project_id': self.project.id, 'action': 'validate',
            'items': [{'id': first.id, 'seen_qty': 20.0}], 'qty': 18.0,
            'reason_id': correct})
        self.assertEqual((first.state, first.qty, first.validator_id),
                         ('validated', 18.0, self.resident_user))
        self.assertEqual(self.wall.qty_executed, 18.0)
        # Rechazo sin motivo no se guarda.
        with self.assertRaisesRegex(UserError, 'motivo'):
            service.resident_progress({
                'uuid': 'p6-rej-0', 'project_id': self.project.id, 'action': 'reject',
                'items': [{'id': second.id, 'seen_qty': 10.0}]})
        service.resident_progress({
            'uuid': 'p6-rej-1', 'project_id': self.project.id, 'action': 'reject',
            'items': [{'id': second.id, 'seen_qty': 10.0}], 'reason_id': reject,
            'comment': 'Falta empastar'})
        self.assertEqual((second.state, second.validator_id), ('rejected', self.resident_user))
        self.assertIn('Falta empastar', second.reject_reason)
        # Quien reportó recibe el aviso.
        self.assertIn(self.contractor_user.partner_id,
                      second.message_ids[0].partner_ids)
        # Re-trabajo: validado con su motivo.
        service.resident_progress({
            'uuid': 'p6-rw-1', 'project_id': self.project.id, 'action': 'rework',
            'items': [{'id': third.id, 'seen_qty': 5.0}], 'rework_reason': 'bad_assembly'})
        self.assertEqual((third.state, third.is_rework, third.rework_reason),
                         ('validated', True, 'bad_assembly'))
        # Envío repetido: no se aplica dos veces.
        again = service.resident_progress({
            'uuid': 'p6-val-1', 'project_id': self.project.id, 'action': 'validate',
            'items': [{'id': first.id, 'seen_qty': 20.0}]})
        self.assertTrue(again['duplicate'])

    def test_offline_decision_rechecked(self):
        """Validado sin señal y rechazado en el escritorio antes de volver la
        conexión: la cola recibe el rechazo con el motivo (P13)."""
        progress = self._report(12.0, 'p6-off-1')
        progress.with_context(construction_portal_resident_projects=[self.project.id]).with_user(
            self.resident_user).sudo()._action_reject('Rechazado en el escritorio')
        with self.assertRaisesRegex(UserError, 'ya fue rechazado'):
            self._service(self.resident_user).resident_progress({
                'uuid': 'p6-off-2', 'project_id': self.project.id, 'action': 'validate',
                'items': [{'id': progress.id, 'seen_qty': 12.0}]})
        self.assertEqual(progress.state, 'rejected')
        other = self._report(7.0, 'p6-off-3')
        other.write({'qty': 6.0})
        with self.assertRaisesRegex(UserError, 'cambió de cantidad'):
            self._service(self.resident_user).resident_progress({
                'uuid': 'p6-off-4', 'project_id': self.project.id, 'action': 'validate',
                'items': [{'id': other.id, 'seen_qty': 7.0}]})

    def test_batch_only_without_warnings(self):
        clean = self._report(4.0, 'p6-b-1')
        no_gps = self._report(3.0, 'p6-b-2', latitude=0, longitude=0)
        service = self._service(self.resident_user)
        rows = {r['id']: r for r in service.sync(self.project.id)['resident']['progress']}
        self.assertFalse(rows[clean.id]['warnings'])
        self.assertEqual(rows[no_gps.id]['warnings'][0]['code'], 'gps')
        with self.assertRaisesRegex(UserError, 'uno en uno'):
            service.resident_progress({
                'uuid': 'p6-b-3', 'project_id': self.project.id, 'action': 'validate',
                'items': [{'id': clean.id, 'seen_qty': 4.0}, {'id': no_gps.id, 'seen_qty': 3.0}]})
        self.assertEqual(no_gps.state, 'draft')

    def test_photo_scope(self):
        progress = self._report(2.0, 'p6-ph-1')
        service = self._service(self.resident_user)
        data, mimetype = service.progress_photo(self.project.id, progress.attachment_ids[0].id)
        self.assertTrue(data)
        self.assertTrue(mimetype.startswith('image/'))
        foreign = self.env['ir.attachment'].create({'name': 'ajeno.txt', 'raw': b'x'})
        with self.assertRaises(AccessError):
            service.progress_photo(self.project.id, foreign.id)
        with self.assertRaises(AccessError):
            self._service(self.contractor_user).progress_photo(
                self.project.id, progress.attachment_ids[0].id)

    # CR-50 ------------------------------------------------------------
    def _cement_request(self, uuid, qty=4):
        cement = self.env['product.product'].search(
            [('name', '=', 'Cemento (p6)')], limit=1) or self.env['product.product'].create(
            {'name': 'Cemento (p6)', 'is_storable': True})
        if not self.plan.line_ids.filtered(lambda l: l.product_id == cement):
            self.env['construction.resource.plan.line'].with_context(
                construction_plan_force=True).create({
                    'plan_id': self.plan.id, 'task_id': self.partida.id,
                    'resource_type': 'material', 'product_id': cement.id,
                    'stage': 'creval_tab', 'qty_planned': 50, 'price_unit_planned': 30.0,
                    'product_uom_id': cement.uom_id.id})
        result = self._service(self.foreman_user).material_request({
            'uuid': uuid, 'project_id': self.project.id, 'priority': 'urgent', 'lines': [
                {'catalog': 'partida', 'product_id': cement.id, 'task_id': self.partida.id,
                 'qty': qty}]})
        return self.env['construction.material.request'].browse(int(result['ids']))

    def _only_resident_rules(self):
        self.env['tier.definition'].search([
            ('model', '=', 'construction.material.request'),
            ('construction_site_fallback', '=', False)]).active = False
        self.company.construction_site_request_without_rule = 'resident'

    def test_request_approval_by_resident(self):
        """Sin otra regla, con «Pasar al residente de la obra», el pedido del
        capataz queda con el residente; aprobado, pasa a «Aprobado» (P5, P6)."""
        self._only_resident_rules()
        request = self._cement_request('p6-rq-1')
        self.assertEqual(request.state, 'to_approve')
        self.assertEqual(request.construction_site_resident_id, self.resident_user)
        self.assertIn(self.resident_user, request.review_ids.reviewer_ids)
        service = self._service(self.resident_user)
        resident = service.sync(self.project.id)['resident']
        row = next(r for r in resident['requests'] if r['id'] == request.id)
        self.assertTrue(row['urgent'])
        self.assertTrue(any(item['kind'] == 'urgent' for item in resident['agenda']))
        line = row['lines'][0]
        with self.assertRaisesRegex(UserError, 'hasta lo pedido'):
            service.resident_request({
                'uuid': 'p6-ap-0', 'project_id': self.project.id, 'request_id': request.id,
                'action': 'approve', 'seen': row['seen'],
                'lines': [{'id': line['id'], 'qty': 9}]})
        service.resident_request({
            'uuid': 'p6-ap-1', 'project_id': self.project.id, 'request_id': request.id,
            'action': 'approve', 'seen': row['seen'], 'lines': [{'id': line['id'], 'qty': 3}]})
        self.assertNotIn(request.state, ('draft', 'to_approve', 'rejected'))
        self.assertEqual(request.line_ids.product_qty, 3.0)
        self.assertEqual(request.review_ids.done_by, self.resident_user)
        # Aprobado sin señal cuando ya no esperaba su aprobación (P14).
        with self.assertRaisesRegex(UserError, 'ya no espera'):
            service.resident_request({
                'uuid': 'p6-ap-2', 'project_id': self.project.id, 'request_id': request.id,
                'action': 'approve', 'seen': row['seen']})

    def test_request_reject_and_two_levels(self):
        self._only_resident_rules()
        service = self._service(self.resident_user)
        reasons = service.sync(self.project.id)['resident']['reasons']['request_reject']
        request = self._cement_request('p6-rq-2')
        row = next(r for r in service.sync(self.project.id)['resident']['requests']
                   if r['id'] == request.id)
        service.resident_request({
            'uuid': 'p6-rj-1', 'project_id': self.project.id, 'request_id': request.id,
            'action': 'reject', 'seen': row['seen'], 'reason_id': reasons[0][0],
            'comment': 'Hay saldo en obra'})
        self.assertEqual(request.state, 'rejected')
        # Dos niveles: el residente y, después, la jefatura (P5 con dos niveles).
        # En la validación por niveles revisa primero la regla de secuencia
        # más alta.
        head = new_test_user(self.env, 'p6_jefatura', name='Jefatura (p6)',
                             groups='al_construction_planner.group_planner_user')
        field = self.env['ir.model.fields']._get('construction.material.request',
                                                 'construction_site_resident_id')
        model = self.env['ir.model']._get('construction.material.request')
        Definition = self.env['tier.definition']
        Definition.create({'name': 'Residente (p6)', 'model_id': model.id,
                           'review_type': 'field', 'reviewer_field_id': field.id,
                           'definition_domain': "[('request_type', '=', 'site')]",
                           'sequence': 30, 'approve_sequence': True,
                           'company_id': self.company.id})
        Definition.create({'name': 'Jefatura (p6)', 'model_id': model.id,
                           'review_type': 'individual', 'reviewer_id': head.id,
                           'definition_domain': "[('request_type', '=', 'site')]",
                           'sequence': 20, 'approve_sequence': True,
                           'company_id': self.company.id})
        second = self._cement_request('p6-rq-3')
        row = next(r for r in service.sync(self.project.id)['resident']['requests']
                   if r['id'] == second.id)
        service.resident_request({
            'uuid': 'p6-ap-3', 'project_id': self.project.id, 'request_id': second.id,
            'action': 'approve', 'seen': row['seen']})
        self.assertEqual(second.state, 'to_approve')
        pending = second.review_ids.filtered(lambda r: r.status == 'pending')
        self.assertEqual(pending.reviewer_ids, head)
        self.assertFalse(any(r['id'] == second.id for r in service.sync(
            self.project.id)['resident']['requests']))

    def test_request_approval_with_approvals_app(self):
        """La misma bandeja con la aplicación Aprobaciones (los dos motores)."""
        if 'construction_approval_engine' not in self.company._fields:
            self.skipTest('Sin el puente de Aprobaciones.')
        self._only_resident_rules()
        self.company.construction_approval_engine = 'approvals'
        request = self._cement_request('p6-rq-ap-1')
        self.assertEqual(request.state, 'to_approve')
        approval = request.construction_approval_id
        self.assertEqual(approval.approver_ids.user_id, self.resident_user)
        service = self._service(self.resident_user)
        row = next(r for r in service.sync(self.project.id)['resident']['requests']
                   if r['id'] == request.id)
        self.assertTrue(row['seen'].startswith('approval:'))
        service.resident_request({
            'uuid': 'p6-ap-ap-1', 'project_id': self.project.id, 'request_id': request.id,
            'action': 'approve', 'seen': row['seen']})
        self.assertNotIn(request.state, ('draft', 'to_approve', 'rejected'))
        # Rechazo con Aprobaciones.
        other = self._cement_request('p6-rq-ap-2', qty=2)
        reason = service.sync(self.project.id)['resident']['reasons']['request_reject'][0][0]
        row = next(r for r in service.sync(self.project.id)['resident']['requests']
                   if r['id'] == other.id)
        service.resident_request({
            'uuid': 'p6-ap-rj-1', 'project_id': self.project.id, 'request_id': other.id,
            'action': 'reject', 'seen': row['seen'], 'reason_id': reason})
        # Como en el escritorio con Aprobaciones: vuelve a borrador con el motivo.
        self.assertEqual(other.state, 'draft')
        self.assertEqual(other.construction_approval_ids.request_status, 'refused')
