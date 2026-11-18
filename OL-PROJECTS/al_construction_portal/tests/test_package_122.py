# -*- coding: utf-8 -*-
"""Paquete 1.22, etapa 1: el portal de obra sigue el perfil de vertical de la
obra (M122-01), nombra los niveles con su plantilla (M122-02), toma el motivo
del re-trabajo del catálogo de la compañía (M122-03), agrupa «Avance» por los
niveles superiores (M122-04) y se configura desde la ficha de la obra
(M122-10). Los servicios corren con usuarios de portal sin permisos internos.
Datos ficticios."""
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged

from odoo.addons.al_construction_planner_subcontract.tests.test_contract_terms_creval import (
    PHOTO, ContractTermsCommon,
)

PHOTOS = [{'name': 'avance.jpg', 'mimetype': 'image/png', 'data': PHOTO.decode()}]


@tagged('post_install', '-at_install')
class TestPackage122(ContractTermsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.contractor_user = new_test_user(env, 'p122_contrata', groups='base.group_portal',
                                            name='Supervisor de contrata (p122)')
        cls.contractor_user.partner_id.parent_id = cls.contractor
        cls.foreman_user = new_test_user(env, 'p122_capataz', groups='base.group_portal',
                                         name='Capataz (p122)')
        cls.resident_user = new_test_user(env, 'p122_residente', groups='base.group_portal',
                                          name='Residente (p122)')
        Member = env['construction.portal.member']
        Member.create({'project_id': cls.project.id, 'user_id': cls.contractor_user.id,
                       'role': 'contractor', 'partner_id': cls.contractor.id})
        Member.create({'project_id': cls.project.id, 'user_id': cls.foreman_user.id,
                       'role': 'foreman'})
        Member.create({'project_id': cls.project.id, 'user_id': cls.resident_user.id,
                       'role': 'resident', 'is_default_approver': True})
        _wizard, cls.order = cls._assign(cls)
        cls.order.button_confirm()
        cls.wall = cls.plan.line_ids.filtered(lambda l: l.activity_id == cls.act_wall)
        base = env.ref('al_construction_planner.profile_construction')
        # Perfil de una vertical sin parte diario ni deductivos.
        cls.profile_off = base.copy({
            'name': 'Sin parte diario (p122)', 'code': 'p122_off',
            'feature_daily_report': False, 'feature_deductions': False})
        cls.profile_on = base.copy({
            'name': 'Con todo (p122)', 'code': 'p122_on', 'feature_daily_report': True,
            'feature_deductions': True, 'feature_progress': True})
        cls.Reason = env['construction.portal.reason']
        cls.reason = cls.Reason.create({
            'name': 'Defecto de ejecución (p122)', 'kind': 'rework',
            'company_id': cls.company.id})

    def _service(self, user, login='password'):
        return self.env['construction.portal.service'].with_user(user).with_context(
            construction_portal_login=login)

    def _today(self):
        return fields.Date.to_string(
            fields.Date.context_today(self._service(self.contractor_user)))

    def _progress(self, uuid, **extra):
        return dict({'uuid': uuid, 'project_id': self.project.id,
                     'plan_line_id': self.wall.id, 'date': self._today(), 'qty': 5.0,
                     'photos': PHOTOS}, **extra)

    # ------------------------------------------------------------------
    # M122-01
    # ------------------------------------------------------------------
    def test_features_without_profile_show_everything(self):
        self.project.construction_profile_id = False
        self.company.construction_profile_id = False
        data = self._service(self.foreman_user).sync(self.project.id)
        self.assertEqual(set(data['features']),
                         {'progress', 'daily_report', 'deductions', 'valuation'}
                         & set(data['features']))
        self.assertIn('daily_report', data['features'])
        self.assertIn('daily', data)
        self.assertIn('crew', data)

    def test_features_follow_the_project_profile(self):
        self.project.construction_profile_id = self.profile_off
        service = self._service(self.foreman_user)
        data = service.sync(self.project.id)
        self.assertNotIn('daily_report', data['features'])
        self.assertIn('progress', data['features'])
        self.assertNotIn('daily', data)
        self.assertNotIn('crew', data)
        # Transversales: no dependen del perfil.
        self.assertIn('catalog', data)
        self.assertIn('deliveries', data)
        # Una llamada directa, o un registro que estaba en la cola del celular.
        with self.assertRaisesRegex(UserError, 'no usa el parte diario'):
            service.daily_report({'uuid': 'p122-d1', 'project_id': self.project.id,
                                  'date': self._today()})
        with self.assertRaisesRegex(UserError, 'no usa el parte diario'):
            service.crew_day({'uuid': 'p122-c1', 'project_id': self.project.id,
                              'date': self._today()})
        # El perfil de la compañía vale cuando la obra no tiene el suyo.
        self.project.construction_profile_id = False
        self.company.construction_profile_id = self.profile_off
        self.assertNotIn('daily', service.sync(self.project.id))
        self.project.construction_profile_id = self.profile_on
        self.assertIn('daily', service.sync(self.project.id))

    def test_progress_feature_off(self):
        self.profile_off.feature_progress = False
        self.project.construction_profile_id = self.profile_off
        service = self._service(self.contractor_user)
        data = service.sync(self.project.id)
        self.assertNotIn('progress', data['features'])
        self.assertEqual(data['counters']['progress_to_validate'], 0)
        with self.assertRaisesRegex(UserError, 'no usa el avance'):
            service.progress(self._progress('p122-p0'))
        resident = self._service(self.resident_user)
        self.assertEqual(resident.sync(self.project.id)['resident']['progress'], [])
        with self.assertRaisesRegex(UserError, 'no usa el avance'):
            resident.resident_progress({'uuid': 'p122-r0', 'project_id': self.project.id,
                                        'action': 'validate', 'items': [{'id': 1}]})

    def test_deductions_feature_off_hides_guarantee(self):
        self.project.construction_profile_id = self.profile_off
        service = self._service(self.contractor_user)
        result = service.valuations(self.project.id)
        self.assertTrue(result['orders'])
        for order in result['orders']:
            self.assertFalse(order['show_deductions'])
            self.assertEqual((order['guarantee'], order['deductions']), (0.0, 0.0))
        resident = self._service(self.resident_user)
        self.assertFalse(resident.sync(self.project.id)['resident']['features']['deduction'])
        with self.assertRaisesRegex(UserError, 'no usa deductivos'):
            resident.deduction({'uuid': 'p122-x1', 'project_id': self.project.id})
        self.project.construction_profile_id = self.profile_on
        self.assertTrue(service.valuations(self.project.id)['orders'][0]['show_deductions'])

    # ------------------------------------------------------------------
    # M122-02 y M122-04
    # ------------------------------------------------------------------
    def test_level_names_and_groups(self):
        data = self._service(self.contractor_user).sync(self.project.id)
        self.assertEqual(data['levels']['space'], 'Partida')
        self.assertEqual(data['levels']['level_1'], 'Especialidad')
        wall = next(p for p in data['partidas'] if p['id'] == self.wall.id)
        self.assertEqual(wall['level_name'], 'Partida')
        # Niveles superiores de la línea: sub-especialidad dentro de especialidad.
        group = data['groups'][wall['group_id']]
        self.assertEqual((group['name'], group['level']),
                         (self.subdiscipline.name, 'Sub-especialidad'))
        parent = data['groups'][group['parent']]
        self.assertEqual((parent['name'], parent['level'], parent['parent']),
                         (self.discipline.name, 'Especialidad', False))
        self.assertEqual(wall['stage'], 'creval_tab')
        self.assertIn('Tabiquería', wall['stage_label'])
        self.assertFalse(wall['late'])

    def test_level_number_mark_is_not_shown(self):
        line = self.partida.construction_level_line_id
        line.name = 'Partida (N3)'
        data = self._service(self.contractor_user).sync(self.project.id)
        wall = next(p for p in data['partidas'] if p['id'] == self.wall.id)
        self.assertEqual((wall['level_name'], data['levels']['space']), ('Partida', 'Partida'))

    def test_late_line_by_plan_dates(self):
        today = fields.Date.context_today(self._service(self.contractor_user))
        self.env['construction.space.stage'].search(
            [('space_task_id', '=', self.partida.id)]).unlink()
        self.env['construction.space.stage'].create({
            'space_task_id': self.partida.id, 'stage': 'creval_tab',
            'date_start': fields.Date.add(today, days=-10),
            'date_end': fields.Date.add(today, days=-3)})
        data = self._service(self.contractor_user).sync(self.project.id)
        wall = next(p for p in data['partidas'] if p['id'] == self.wall.id)
        self.assertTrue(wall['late'])

    # ------------------------------------------------------------------
    # M122-03
    # ------------------------------------------------------------------
    def test_rework_reason_from_catalog(self):
        service = self._service(self.contractor_user)
        data = service.sync(self.project.id)
        self.assertIn([self.reason.id, self.reason.name], data['rework_reasons'])
        result = service.progress(self._progress(
            'p122-rw1', is_rework=True, rework_reason_id=self.reason.id))
        progress = self.env['construction.task.progress'].browse(int(result['ids']))
        self.assertEqual((progress.is_rework, progress.rework_reason_id),
                         (True, self.reason))
        with self.assertRaisesRegex(UserError, 'pide su motivo'):
            service.progress(self._progress('p122-rw2', is_rework=True))

    def test_rework_reason_of_another_company_is_rejected(self):
        other = self.env['res.company'].create({'name': 'Otra compañía (p122)'})
        foreign = self.Reason.create({'name': 'De otra compañía (p122)', 'kind': 'rework',
                                      'company_id': other.id})
        not_rework = self.Reason.search([('kind', '=', 'progress_reject')], limit=1)
        service = self._service(self.contractor_user)
        for index, reason in enumerate(foreign | not_rework):
            with self.assertRaisesRegex(UserError, 'no es de la compañía'):
                service.progress(self._progress(
                    'p122-rw3-%s' % index, is_rework=True, rework_reason_id=reason.id))

    def test_archived_reason_is_not_offered_but_is_kept(self):
        service = self._service(self.contractor_user)
        result = service.progress(self._progress(
            'p122-rw4', is_rework=True, rework_reason_id=self.reason.id))
        progress = self.env['construction.task.progress'].browse(int(result['ids']))
        self.reason.active = False
        data = service.sync(self.project.id)
        self.assertNotIn(self.reason.id, [row[0] for row in data['rework_reasons']])
        self.assertEqual(progress.rework_reason_id, self.reason)

    def test_legacy_code_takes_the_catalog_reason(self):
        """Un celular sin actualizar envía el valor de la lista anterior."""
        service = self._service(self.contractor_user)
        result = service.progress(self._progress(
            'p122-rw5', is_rework=True, rework_reason='bad_assembly'))
        progress = self.env['construction.task.progress'].browse(int(result['ids']))
        self.assertEqual(progress.rework_reason_id.name, 'Mal armado')
        self.assertEqual(progress.rework_reason_id.kind, 'rework')
        # Y otro módulo que escribe la selección anterior.
        other = self.env['construction.task.progress'].create({
            'task_id': self.wall.task_id.id, 'activity_id': self.wall.activity_id.id,
            'plan_line_id': self.wall.id, 'date': self._today(), 'qty': 1.0,
            'is_rework': True, 'rework_reason': 'missing',
            'attachment_ids': progress.attachment_ids.copy().ids})
        self.assertEqual(other.rework_reason_id.name, 'Faltante')
        self.assertEqual(self.Reason.with_context(active_test=False).search_count(
            [('name', '=', 'Faltante'), ('kind', '=', 'rework')]), 1)

    def test_profile_seeds_rework_reasons_once(self):
        company = self.env['res.company'].create({'name': 'Compañía nueva (p122)'})
        self.profile_on.rework_reason_names = 'Motivo uno (p122)\nMotivo dos (p122)\n'
        self.profile_on._apply_configuration(company)
        names = self.Reason.search([('company_id', '=', company.id)]).mapped('name')
        self.assertEqual(names, ['Motivo uno (p122)', 'Motivo dos (p122)'])
        # Con motivos propios, aplicar el perfil otra vez no agrega nada.
        self.profile_on.rework_reason_names = 'Motivo tres (p122)'
        self.profile_on._apply_configuration(company)
        self.assertEqual(self.Reason.search_count([('company_id', '=', company.id)]), 2)

    # ------------------------------------------------------------------
    # M122-10
    # ------------------------------------------------------------------
    def test_portal_staff_from_the_site_form(self):
        self.assertEqual(self.project.construction_portal_member_count, 3)
        action = self.project.action_construction_open_portal()
        view = self.env.ref(
            'al_construction_portal.project_project_view_form_construction_portal_staff')
        self.assertEqual((action['res_id'], action['views']), (self.project.id,
                                                               [(view.id, 'form')]))
        board = self.env['project.project'].get_view(self.env.ref(
            'al_construction_planner.project_project_view_form_construction_board').id, 'form')
        self.assertIn('action_construction_open_portal', board['arch'])
