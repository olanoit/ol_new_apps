# -*- coding: utf-8 -*-
"""Servicios del portal de obra (requerimiento CREVAL v1.0, 4.11) con la obra
de demostración de las contratas: avance sin duplicar, alcance de la
contrata, PIN, parte diario, requerimientos de obra e internos, recepción con
faltante, devolución, tareo y valorizaciones. Datos ficticios."""
from datetime import date, timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged

from odoo.addons.al_construction_portal.models.portal_service import _initials
from odoo.addons.al_construction_planner_subcontract.tests.test_contract_terms_creval import (
    PHOTO, ContractTermsCommon,
)

PHOTOS = [{'name': 'avance.jpg', 'mimetype': 'image/png', 'data': PHOTO.decode()}]


@tagged('post_install', '-at_install')
class TestPortalService(ContractTermsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.contractor_user = new_test_user(env, 'portal_contrata', groups='base.group_portal',
                                            name='Supervisor de la contrata (test)')
        cls.contractor_user.partner_id.parent_id = cls.contractor
        cls.employee = env['hr.employee'].create({'name': 'Maestro de obra (test)'})
        cls.foreman_user = new_test_user(env, 'portal_capataz', groups='base.group_portal',
                                         name='Maestro de obra (test)')
        Member = env['construction.portal.member']
        cls.contractor_member = Member.create({
            'project_id': cls.project.id, 'user_id': cls.contractor_user.id,
            'role': 'contractor', 'partner_id': cls.contractor.id})
        cls.foreman_member = Member.create({
            'project_id': cls.project.id, 'user_id': cls.foreman_user.id, 'role': 'foreman',
            'employee_id': cls.employee.id})
        _wizard, cls.order = cls._assign(cls)
        cls.order.button_confirm()

    def _service(self, user):
        return self.env['construction.portal.service'].with_user(user)

    def _today(self):
        # «Hoy» del usuario del portal (el que usa el servicio), no el del
        # administrador del test: cerca de medianoche pueden ser días distintos.
        return fields.Date.context_today(self._service(self.contractor_user))

    def _wall_line(self):
        return self.plan.line_ids.filtered(lambda l: l.activity_id == self.act_wall)

    def test_progress_scope_and_duplicates(self):
        service = self._service(self.contractor_user)
        data = service.sync(self.project.id)
        self.assertEqual(data['roles'], ['contractor'])
        wall = next(p for p in data['partidas'] if p['id'] == self._wall_line().id)
        self.assertEqual(wall['planned'], 2000.0)
        payload = {'uuid': 'test-uuid-1', 'project_id': self.project.id,
                   'plan_line_id': self._wall_line().id, 'date': fields.Date.to_string(
                       self._today()), 'qty': 25.0,
                   'photos': PHOTOS, 'latitude': -12.1, 'longitude': -77.0}
        result = service.progress(payload)
        progress = self.env['construction.task.progress'].browse(int(result['ids']))
        self.assertEqual((progress.source, progress.qty, progress.state),
                         ('portal', 25.0, 'draft'))
        self.assertEqual(progress.reported_by_id, self.contractor_user)
        self.assertEqual(len(progress.attachment_ids), 1)
        # Un envío repetido no duplica.
        again = service.progress(payload)
        self.assertTrue(again['duplicate'])
        self.assertEqual(self.env['construction.task.progress'].search_count(
            [('plan_line_id', '=', self._wall_line().id)]), 1)
        # % acumulado: el 5 % de 2 000 m² menos lo ya reportado.
        pct = service.progress(dict(payload, uuid='test-uuid-2', mode='pct', pct=5.0))
        self.assertEqual(self.env['construction.task.progress'].browse(int(pct['ids'])).qty, 75.0)
        with self.assertRaisesRegex(UserError, 'futura'):
            service.progress(dict(payload, uuid='test-uuid-3', date=fields.Date.to_string(
                date.today() + timedelta(days=2))))
        with self.assertRaisesRegex(UserError, 'foto'):
            service.progress(dict(payload, uuid='test-uuid-4', photos=[]))
        # Otra contrata no ve ni reporta esta partida.
        other = self.env['res.partner'].create({'name': 'Otra contrata (test)'})
        intruder = new_test_user(self.env, 'portal_intruso', groups='base.group_portal')
        intruder.partner_id.parent_id = other
        self.env['construction.portal.member'].create({
            'project_id': self.project.id, 'user_id': intruder.id, 'role': 'contractor',
            'partner_id': other.id})
        self.assertFalse(self._service(intruder).sync(self.project.id)['partidas'])
        with self.assertRaises(AccessError):
            self._service(intruder).progress(dict(payload, uuid='test-uuid-5'))
        stranger = new_test_user(self.env, 'portal_ajeno', groups='base.group_portal')
        with self.assertRaises(AccessError):
            self._service(stranger).sync(self.project.id)

    def test_pin_and_token(self):
        member = self.foreman_member
        member.action_set_pin('1234')
        self.assertTrue(member.has_pin)
        self.assertTrue(member._check_pin('1234'))
        for _attempt in range(3):
            self.assertFalse(member._check_pin('0000'))
        self.assertTrue(member.pin_locked)
        self.assertFalse(member._check_pin('1234'))
        member.action_unlock()
        self.assertTrue(member._check_pin('1234'))
        Token = self.env['construction.portal.token']
        token, expiration = Token._issue(self.foreman_user, 'qr')
        self.assertEqual(Token._check(token), self.foreman_user)
        self.assertFalse(Token._check('otro'))
        self.assertGreater(expiration, fields.Datetime.now() + timedelta(days=89))
        self.project.write({'construction_portal_qr_login': True})
        self.project.action_construction_portal_new_code()
        self.assertEqual(self.env['project.project']._construction_portal_by_code(
            self.project.construction_portal_code), self.project)

    def test_daily_report(self):
        service = self._service(self.foreman_user)
        values = {'uuid': 'parte-1', 'project_id': self.project.id, 'weather': 'sunny',
                  'staff': [{'name': 'Cuadrilla propia', 'source': 'own', 'count': 6},
                            {'name': 'Tabiquería Demo', 'source': 'contract', 'count': 4}],
                  'restrictions': ['material'], 'occurrences': 'Falta cemento.'}
        result = service.daily_report(values)
        report = self.env['construction.daily.report'].browse(int(result['ids']))
        self.assertEqual((report.staff_total, report.restriction_material, report.state),
                         (10, True, 'sent'))
        service.daily_report(dict(values, uuid='parte-2', staff=[{'name': 'Propio', 'count': 3}]))
        self.assertEqual(self.env['construction.daily.report'].search_count(
            [('project_id', '=', self.project.id)]), 1)
        self.assertEqual(report.staff_total, 3)
        with self.assertRaises(AccessError):
            self._service(self.contractor_user).daily_report(dict(values, uuid='parte-3'))

    def test_material_requests(self):
        cement = self.env['product.product'].create({
            'name': 'Cemento Portland (test portal)', 'is_storable': True})
        self.env['construction.resource.plan.line'].with_context(
            construction_plan_force=True).create({
                'plan_id': self.plan.id, 'task_id': self.partida.id, 'resource_type': 'material',
                'product_id': cement.id, 'stage': 'creval_tab', 'qty_planned': 50,
                'price_unit_planned': 30.0, 'product_uom_id': cement.uom_id.id})
        category = self.env['product.category'].create({
            'name': 'Útiles y aseo (test portal)', 'construction_portal_catalog': 'office'})
        paper = self.env['product.product'].create({
            'name': 'Papel higiénico (test portal)', 'categ_id': category.id})
        kit = self.env['construction.portal.kit'].create({
            'name': 'Kit semanal de aseo (test)', 'catalog': 'office',
            'line_ids': [Command.create({'product_id': paper.id, 'qty': 2})]})
        plan = self.env['account.analytic.plan'].create({'name': 'Área (test portal)'})
        self.company.construction_area_plan_id = plan
        area = self.env['account.analytic.account'].create({
            'name': 'GG de la obra (test)', 'plan_id': plan.id, 'company_id': self.company.id})
        service = self._service(self.foreman_user)
        catalog = service.sync(self.project.id)['catalog']
        self.assertTrue(any(row['product_id'] == cement.id for row in catalog['partida']))
        self.assertEqual(catalog['office']['kits'][0]['id'], kit.id)
        values = {'uuid': 'req-1', 'project_id': self.project.id, 'lines': [
            {'catalog': 'partida', 'product_id': cement.id, 'task_id': self.partida.id, 'qty': 3},
            {'catalog': 'office', 'product_id': paper.id, 'qty': 2}]}
        with self.assertRaisesRegex(UserError, 'gastos generales'):
            service.material_request(values)
        self.project.construction_portal_overhead_area_id = area
        result = service.material_request(dict(values, uuid='req-2'))
        requests = self.env['construction.material.request'].browse(
            [int(i) for i in result['ids'].split(',')])
        self.assertEqual(sorted(requests.mapped('request_type')), ['internal', 'site'])
        site = requests.filtered(lambda r: r.request_type == 'site')
        self.assertEqual(site.line_ids.task_id, self.partida)
        internal = requests.filtered(lambda r: r.request_type == 'internal')
        self.assertEqual(internal.area_id, area)
        # El interno pedido desde el portal queda en la obra (7.3).
        self.assertEqual(internal.project_id, self.project)
        # El buscador del catálogo usa el código y el nombre de la partida (CR-17).
        row = next(r for r in catalog['partida'] if r['product_id'] == cement.id)
        self.assertEqual((row['task_code'], row['task_name']), ('04.01', 'Tabique drywall (test)'))
        self.assertTrue(all(state != 'draft' for state in requests.mapped('state')))
        with self.assertRaises(AccessError):
            service.material_request(dict(values, uuid='req-3', lines=[
                {'catalog': 'partida', 'product_id': paper.id, 'task_id': self.partida.id,
                 'qty': 1}]))

    def test_reception_with_shortage_and_return(self):
        board = self.env['product.product'].create({
            'name': 'Placa de drywall (test portal)', 'is_storable': True})
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.company.id)], limit=1)
        self.env['stock.quant']._update_available_quantity(board, warehouse.lot_stock_id, 50)
        location = self.project.construction_location_id
        self.assertTrue(location)
        picking = self.env['stock.picking'].create({
            'picking_type_id': warehouse.int_type_id.id, 'location_id': warehouse.lot_stock_id.id,
            'location_dest_id': location.id, 'move_ids': [Command.create({
                'product_id': board.id, 'product_uom_qty': 10, 'product_uom': board.uom_id.id,
                'location_id': warehouse.lot_stock_id.id, 'location_dest_id': location.id})]})
        picking.action_confirm()
        picking.action_assign()
        service = self._service(self.foreman_user)
        deliveries = service.sync(self.project.id)['deliveries']
        self.assertEqual([d['id'] for d in deliveries], picking.ids)
        result = service.reception({
            'uuid': 'rec-1', 'project_id': self.project.id, 'picking_id': picking.id,
            'photos': PHOTOS, 'lines': [{'move_id': picking.move_ids.id, 'qty': 8}]})
        self.assertEqual(picking.state, 'done')
        self.assertTrue(result['backorder'])
        backorder = self.env['stock.picking'].search([('backorder_id', '=', picking.id)])
        self.assertEqual(backorder.move_ids.product_uom_qty, 2.0)
        returnables = service.sync(self.project.id)['returnables']
        self.assertEqual(returnables[0]['qty'], 8.0)
        result = service.return_material({
            'uuid': 'dev-1', 'project_id': self.project.id, 'transport': 'own', 'photos': PHOTOS,
            'lines': [{'product_id': board.id, 'qty': 3, 'state': 'good'},
                      {'product_id': board.id, 'qty': 1, 'state': 'damaged'}]})
        self.assertEqual(len(result['pickings']), 1)
        self.assertEqual(result['scraps'], 1)
        with self.assertRaisesRegex(UserError, 'No hay tanto'):
            service.return_material({
                'uuid': 'dev-2', 'project_id': self.project.id, 'photos': PHOTOS,
                'lines': [{'product_id': board.id, 'qty': 100}]})

    def test_crew_day_tareo(self):
        labor = self.env['construction.labor.activity'].create({
            'code': 'TC-OPE', 'name': 'Operario (test portal)', 'stage': 'creval_tab',
            'uom_id': self.env.ref('uom.product_uom_hour').id, 'default_price': 25.0})
        line = self.env['construction.resource.plan.line'].with_context(
            construction_plan_force=True).create({
                'plan_id': self.plan.id, 'task_id': self.partida.id, 'resource_type': 'labor',
                'activity_id': labor.id, 'stage': 'creval_tab', 'qty_planned': 80,
                'price_unit_planned': 25.0,
                'product_uom_id': self.env.ref('uom.product_uom_hour').id})
        site = self.env['l10n_pe.hr.construction.site'].create({
            'name': 'Sede OBR-01 (test)', 'project_id': self.project.id,
            'company_id': self.company.id})
        service = self._service(self.foreman_user)
        crew = service.sync(self.project.id)['crew']
        self.assertEqual([w['id'] for w in crew], self.employee.ids)
        day = self._today()
        result = service.crew_day({
            'uuid': 'tareo-1', 'project_id': self.project.id, 'date': fields.Date.to_string(day),
            'attendance': [{'employee_id': self.employee.id, 'present': True, 'time': '07:30'}],
            'hours': [{'employee_id': self.employee.id, 'plan_line_id': line.id, 'hours': 8}]})
        self.assertEqual((result['present'], result['tareo']), (1, 1))
        attendance = self.env['hr.attendance'].search([('employee_id', '=', self.employee.id)])
        self.assertEqual(attendance.l10n_pe_construction_site_id, site)
        self.assertAlmostEqual(attendance.worked_hours, 8.0, places=1)
        days = self.env['construction.crew.day'].search([
            ('kind', '=', 'executed'), ('employee_id', '=', self.employee.id)])
        self.assertEqual(days.plan_line_id, line)

    def test_valuations(self):
        action = self.order.action_construction_register_advance()
        self._post(self.env['account.move'].browse(action['res_id']), date(2026, 11, 2))
        self._report(self.partida, self.act_wall, 100.0, date(2026, 11, 4))
        settlement = self.env['construction.contract.settlement']._prepare_terms_settlements(
            today=date(2026, 11, 20))
        service = self._service(self.contractor_user)
        data = service.valuations(self.project.id)
        self.assertEqual(data['orders'][0]['id'], self.order.id)
        self.assertEqual(data['valuations'][0]['id'], settlement.id)
        detail = service.valuation(self.project.id, settlement.id)
        self.assertEqual(detail['id'], settlement.id)
        self.assertTrue(detail['lines'])
        with self.assertRaises(AccessError):
            self._service(self.foreman_user).valuations(self.project.id)
        # Pantalla 13: la tarjeta de la orden y el total con IGV.
        order = data['orders'][0]
        self.assertEqual(order['amount_untaxed'], self.order.amount_untaxed)
        self.assertTrue(order['frequency_label'])
        self.assertEqual(order['valued_pct'], round(100.0 * order['valued'] / order['amount_untaxed']))
        self.assertEqual(data['partner'], self.contractor.name)
        self.assertEqual(data['valuations'][0]['amount_total'], settlement.amount_total)
        sync = service.sync(self.project.id)
        self.assertEqual(sync['orders'][0]['id'], self.order.id)
        self.assertEqual(sync['contract_partner'], self.contractor.name)
        # Pantalla 14: el neto descuenta el adelanto y el fondo (y la detracción
        # con factura), como el total a pagar de la valorización.
        self.assertEqual(detail['net'], settlement.amount_to_pay - detail['detraction'])
        self.assertEqual(detail['advance'], settlement.amount_advance)
        self.assertEqual(detail['tax_pct'], 18)
        self.assertFalse(detail['has_invoice_pdf'])
        pdf, filename = service.valuation_pdf(self.project.id, settlement.id, 'valuation')
        self.assertTrue(pdf)
        self.assertTrue(filename.endswith('.pdf'))
        with self.assertRaisesRegex(UserError, 'factura'):
            service.valuation_pdf(self.project.id, settlement.id, 'invoice')
        with self.assertRaises(AccessError):
            self._service(self.foreman_user).valuation_pdf(
                self.project.id, settlement.id, 'valuation')

    def test_sync_for_the_screens(self):
        """Lo que piden las pantallas del prototipo: la semana de la obra, los
        tres contadores del inicio, la tolerancia y la última validación de la
        partida, y el parte diario ya llenado con las contratas y el avance
        del día."""
        today = self._today()
        self._report(self.partida, self.act_wall, 40.0, today)
        contractor = self._service(self.contractor_user)
        contractor.progress({
            'uuid': 'sync-1', 'project_id': self.project.id, 'plan_line_id': self._wall_line().id,
            'date': fields.Date.to_string(today), 'qty': 10.0, 'photos': PHOTOS})
        data = contractor.sync(self.project.id)
        week_start, week_end = self.project._construction_period(today)
        self.assertEqual(data['project']['week_start'], fields.Date.to_string(week_start))
        self.assertEqual(data['project']['week_end'], fields.Date.to_string(week_end))
        wall = next(p for p in data['partidas'] if p['id'] == self._wall_line().id)
        self.assertEqual(wall['last_validated'], fields.Date.to_string(today))
        self.assertEqual(wall['tolerance'], self._wall_line()._get_tolerance_qty())
        self.assertEqual(wall['exceed_policy'],
                         self._wall_line().plan_id._exceed_policy_for(
                             self._wall_line().resource_type))
        self.assertEqual(data['counters']['progress_to_validate'], 1)
        self.assertEqual(data['members'][0]['partner'], self.contractor.name)
        foreman = self._service(self.foreman_user).sync(self.project.id)
        self.assertEqual(foreman['counters']['requests_to_approve'], 0)
        self.assertEqual(foreman['counters']['deliveries_today'], 0)
        self.assertIn(self.contractor.name, [c['name'] for c in foreman['daily']['contractors']])
        self.assertEqual(sorted(w['qty'] for w in foreman['daily']['work']), [10.0, 40.0])
        # Reportados y validados del día, con su estado (7.1).
        self.assertEqual(sorted(w['state'] for w in foreman['daily']['work']),
                         ['draft', 'validated'])
        self.assertTrue(all(w['state_label'] for w in foreman['daily']['work']))
        # La partida legible, sin la ruta interna (CR-17).
        self.assertEqual((wall['task_code'], wall['task_name'], wall['parent_label']),
                         ('04.01', 'Tabique drywall (test)', 'Tabiquería (test)'))
        self.assertEqual(wall['item'], '04.01')
        self.assertIn('(contrata)', wall['role_label'])
        for row in data['partidas'] + foreman['daily']['work']:
            self.assertNotIn('/', '%s %s' % (row['item'], row.get('path', '')))
        self.assertEqual(foreman['daily']['own_today'], 0)
        self.assertNotIn('orders', foreman)

    def test_site_request_without_rule(self):
        """Sin regla de aprobación, el requerimiento de obra pasa al jefe de
        la obra o se aprueba al enviarlo, según la compañía (7.4)."""
        manager = new_test_user(self.env, 'portal_residente', name='Residente (test)',
                                groups='al_construction_planner.group_planner_user')
        self.project.user_id = manager
        cement = self.env['product.product'].create({
            'name': 'Cemento sin regla (test portal)', 'is_storable': True})
        self.env['construction.resource.plan.line'].with_context(
            construction_plan_force=True).create({
                'plan_id': self.plan.id, 'task_id': self.partida.id, 'resource_type': 'material',
                'product_id': cement.id, 'stage': 'creval_tab', 'qty_planned': 50,
                'price_unit_planned': 30.0, 'product_uom_id': cement.uom_id.id})
        # Sin otras reglas para los requerimientos de obra.
        self.env['tier.definition'].search([
            ('model', '=', 'construction.material.request'),
            ('construction_site_fallback', '=', False)]).active = False
        service = self._service(self.foreman_user)

        def request(uuid):
            result = service.material_request({
                'uuid': uuid, 'project_id': self.project.id, 'lines': [
                    {'catalog': 'partida', 'product_id': cement.id,
                     'task_id': self.partida.id, 'qty': 1}]})
            return self.env['construction.material.request'].browse(int(result['ids']))
        self.company.construction_site_request_without_rule = 'manager'
        first = request('sin-regla-1')
        self.assertEqual(first.state, 'to_approve')
        self.assertIn(manager, first.review_ids.reviewer_ids)
        self.company.construction_site_request_without_rule = 'approve'
        second = request('sin-regla-2')
        self.assertNotIn(second.state, ('draft', 'to_approve'))

    def test_initials(self):
        self.assertEqual(_initials('Creamos Valor S.A.C.'), 'CV')
        self.assertEqual(_initials('Juan Carlos Oyola'), 'JC')
        self.assertEqual(_initials(''), 'OB')
