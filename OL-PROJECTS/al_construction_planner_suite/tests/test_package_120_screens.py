# -*- coding: utf-8 -*-
"""Paquete 1.20, M120-08 y pruebas de pantalla del paquete.

* La cabecera del plan agrupa sus acciones en «Programar» y «Ejecutar», con
  los grupos y los estados de siempre; cada puente pone las suyas.
* La prueba de pantalla abre cada opción de Ejecución, Abastecimiento,
  Contratas y Configuración, usa los dos grupos del plan y abre la ficha de la
  actividad; falla si un clic da error."""
from odoo import Command
from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user

from .common import PlannerCommon

P = 'al_construction_planner.'


@tagged('post_install', '-at_install')
class TestPlanHeader120(PlannerCommon):

    def _labels(self, user, menu):
        items = self.plan.with_user(user).construction_header_actions or []
        return [item['label'] for item in items if item['menu'] == menu]

    def test_groups_and_states(self):
        executor = new_test_user(self.env, login='m120_hdr_executor',
                                 groups='base.group_user,' + P + 'group_planner_user')
        planner = new_test_user(self.env, login='m120_hdr_planner',
                                groups='base.group_user,' + P + 'group_planner_plan_planner')
        # En borrador no hay acciones de ejecución.
        self.assertFalse(self._labels(executor, 'execute'))
        self._generate_and_approve()
        self.plan.invalidate_recordset(['construction_header_actions'])
        execute = self._labels(executor, 'execute')
        self.assertEqual(execute[0], 'Registrar avance')
        if self.env.ref('al_construction_planner_subcontract.action_plan_contract_wizard',
                        raise_if_not_found=False):
            self.assertIn('Asignar contrata', execute)
        program = self._labels(executor, 'program')
        self.assertIn('Cambiar fechas', program)
        self.assertNotIn('Crear etapas del cronograma', program)
        # «Planificador» implica «Usuario»: ve lo mismo que antes en los botones.
        self.assertEqual(self._labels(planner, 'execute'), execute)
        arch = self.env['construction.resource.plan'].get_views([(False, 'form')])['views']['form']['arch']
        self.assertIn('construction_plan_actions', arch)
        for old in ('action_plan_reschedule_wizard', 'action_sync_space_stages'):
            self.assertNotIn('name="%s"' % old, arch)


@tagged('post_install', '-at_install')
class TestScreens120(HttpCase, PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['construction.plan.generate.wizard'].create({'plan_id': cls.plan.id}).action_generate()
        cls.plan.line_ids.filtered(lambda l: not l.stage).stage = 'production'
        for line in cls.plan.line_ids.filtered(lambda l: not l.price_unit_planned):
            line.price_unit_planned = 10.0
        cls.plan.action_request_approval()
        cls.project.name = 'Obra pantallas 1.20 (test)'

    def setUp(self):
        super().setUp()
        self.env.ref('base.user_admin').write({
            'company_ids': [Command.link(self.env.company.id)],
            'company_id': self.env.company.id,
            'group_ids': [Command.link(self.env.ref(P + 'group_planner_manager').id),
                          Command.link(self.env.ref(P + 'group_planner_user').id)]})
        self.env['res.config.settings'].create({'group_construction_exec_planner': True}).execute()

    def test_screens_tour(self):
        self.start_tour('/odoo', 'al_construction_package_120_screens', login='admin')
