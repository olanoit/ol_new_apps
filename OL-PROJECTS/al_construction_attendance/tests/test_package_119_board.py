# -*- coding: utf-8 -*-
"""Tablero de control semanal de instalación (paquete 1.19, M119-05).

* Un piso con dos cocinas programadas para terminar la instalación en la
  semana 1: con una cocina validada va «Atrasado» al 50 %; con las dos,
  «Terminado» en la semana de su último avance.
* Indicadores: pisos del período, atrasados y terminados.
* Sin «Ve montos», la mano de obra va en persona-días; un usuario sin los
  grupos del planificador no ve el tablero."""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo import Command
from odoo.tests import HttpCase, new_test_user, tagged

from odoo.addons.al_construction_planner_suite.tests.common import PlannerCommon


def _board_data(cls):
    """Dos cocinas del piso 05 con su instalación programada en la semana 1."""
    grp = 'al_construction_planner.group_planner_'
    cls.env.user.group_ids |= cls.env.ref(grp + 'user') | cls.env.ref(
        grp + 'feature_control')
    today = fields.Date.context_today(cls.env.user)
    cls.origin = today - timedelta(days=today.weekday() + 21)
    cls.lines = cls.env['construction.resource.plan.line']
    for space in (cls.space_501, cls.space_502):
        cls.lines |= cls.env['construction.resource.plan.line'].create({
            'plan_id': cls.plan.id, 'task_id': space.id, 'resource_type': 'contract',
            'activity_id': cls.act_inst_low.id, 'stage': 'installation',
            'partner_id': cls.contractor.id, 'qty_planned': 2.0,
            'price_unit_planned': 16.0, 'product_uom_id': cls.act_inst_low.uom_id.id})
        cls.env['construction.space.stage'].create({
            'space_task_id': space.id, 'stage': 'installation',
            'date_start': cls.origin, 'date_end': cls.origin + timedelta(days=4)})
    cls.plan.action_request_approval()
    cls.Board = cls.env['construction.installation.board']


@tagged('post_install', '-at_install')
class TestInstallationBoard(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _board_data(cls)

    def _validate(self, line, day):
        photo = self.env['ir.attachment'].create({'name': 'f.png', 'datas': b'eA=='})
        progress = self.env['construction.task.progress'].create({
            'task_id': line.task_id.id, 'activity_id': line.activity_id.id,
            'plan_line_id': line.id, 'date': day, 'qty': 2.0,
            'attachment_ids': [(6, 0, photo.ids)]})
        progress.sudo().write({'state': 'validated'})

    def _cell(self, data):
        floor = next(f for f in data['floors'] if f['id'] == self.floor.id)
        return next(c for c in floor['cells'] if c['stage'] == 'installation')

    def test_late_then_done(self):
        self._validate(self.lines[0], self.origin + timedelta(days=2))
        data = self.Board.get_data(self.project.id)
        self.assertFalse(data['empty'])
        self.assertEqual(data['week_to'], data['current_week'] - 1)
        cell = self._cell(data)
        self.assertEqual(cell['sched_week'], 1)
        self.assertEqual(cell['pct'], 50)
        self.assertEqual(cell['status'], 'late')
        self.assertEqual(cell['spaces_done'], 1)
        self.assertEqual(data['indicators']['late']['count'], 1)
        self.assertEqual(data['indicators']['finished'], dict(
            data['indicators']['finished'], done=0, total=1))
        # La segunda cocina se valida en la semana 2: terminado con +1 semana.
        self._validate(self.lines[1], self.origin + timedelta(days=8))
        cell = self._cell(self.Board.get_data(self.project.id))
        self.assertEqual(cell['status'], 'done')
        self.assertEqual(cell['finish_week'], 2)
        self.assertEqual(cell['delay_weeks'], 1)
        # Período «Desde el inicio»: el piso programado en él terminó.
        data = self.Board.get_data(self.project.id, 1, 3)
        self.assertEqual(data['indicators']['period'], {'done': 1, 'total': 1})
        self.assertIn('Semanas 1 a 3', data['period_label'])
        # Desde mayor que hasta: hasta se mueve a la misma semana.
        data = self.Board.get_data(self.project.id, 3, 2)
        self.assertEqual((data['week_from'], data['week_to']), (3, 3))

    def test_curves_and_stage_switches(self):
        data = self.Board.get_data(self.project.id, None, None, False, False)
        # Siempre queda una etapa prendida: sin ninguna, la instalación.
        self.assertTrue(data['installation'])
        self.assertTrue(all(stage['installation'] for stage in data['stages']))
        curve = next(c for c in data['curves'] if 'Instalación' in c['stage'])
        self.assertEqual(curve['points'][0]['planned'], 1)

    def test_access(self):
        outsider = new_test_user(self.env, 'board_outsider', groups='base.group_user')
        with self.assertRaises(AccessError):
            self.Board.with_user(outsider).get_data(self.project.id)
        supervisor = new_test_user(
            self.env, 'board_supervisor',
            groups='al_construction_planner.group_planner_user,'
                   'al_construction_planner.group_planner_feature_control')
        data = self.Board.with_user(supervisor).get_data(self.project.id)
        self.assertFalse(data['show_amounts'])

    def _production_board(self):
        floor_04 = self.task('Piso 04', 'floor')
        apt = self.task('Dpto 401', 'apartment', floor_04)
        space_401 = self.task('Cocina', 'space', apt)
        for space in (space_401, self.space_501):
            self.env['construction.space.stage'].create({
                'space_task_id': space.id, 'stage': 'assembly',
                'date_start': self.origin, 'date_end': self.origin + timedelta(days=4)})
        product = self.env['product.product'].create({'name': 'Cocina armada (test 1.19)',
                                                      'type': 'consu'})
        production = self.env['mrp.production'].create({
            'product_id': product.id, 'product_qty': 132.0,
            'product_uom_id': product.uom_id.id, 'construction_plan_id': self.plan.id,
            'construction_space_task_ids': [(6, 0, (space_401 | self.space_501).ids)]})
        return floor_04, production

    def test_production_from_manufacturing_orders(self):
        """Corrección 3 del 1.19: una orden que junta dos pisos con 132
        unidades y 100 producidas deja el primero de la orden en 100 % y el
        segundo en 52 % (34 de 66). Aquí el piso 05 va primero (se creó antes y
        «Producir» ordena por piso)."""
        if 'construction_space_task_ids' not in self.env['mrp.production']._fields:
            self.skipTest('Sin el puente de Fabricación')
        floor_04, production = self._production_board()
        self.assertIn('assembly', production._construction_order_stages())
        move = production.move_finished_ids.filtered(
            lambda m: m.product_id == production.product_id)[:1]
        self.assertTrue(move)
        move.sudo().write({'quantity': 100.0, 'state': 'done',
                           'date': fields.Datetime.now() - timedelta(days=12)})
        data = self.Board.get_data(self.project.id, None, None, True, True)
        cells = {(f['name'], c['stage']): c for f in data['floors'] for c in f['cells']}
        self.assertEqual(cells[('Piso 05', 'assembly')]['pct'], 100)
        self.assertEqual(cells[('Piso 05', 'assembly')]['status'], 'done')
        self.assertEqual(cells[('Piso 04', 'assembly')]['pct'], 52)
        self.assertNotEqual(cells[('Piso 04', 'assembly')]['status'], 'done')
        self.assertEqual(cells[('Piso 05', 'assembly')]['productions'][0]['id'], production.id)
        # Sin orden en 1.1 Producción de piezas, si la orden no la fabrica: el
        # piso 05 en «Producción» depende de las etapas de la orden.
        production_cell = cells.get(('Piso 05', 'production'))
        if production_cell and not production_cell['productions']:
            self.assertEqual(production_cell['status'], 'no_order')
        late = [(item['floor'], item['stage']) for item in data['indicators']['late']['items']]
        self.assertNotIn(('Piso 05', production_cell and production_cell['stage_label']), late)

    def test_floor_without_order_is_not_late(self):
        if 'construction_space_task_ids' not in self.env['mrp.production']._fields:
            self.skipTest('Sin el puente de Fabricación')
        self.env['construction.space.stage'].create({
            'space_task_id': self.space_501.id, 'stage': 'assembly',
            'date_start': self.origin, 'date_end': self.origin + timedelta(days=4)})
        data = self.Board.get_data(self.project.id, None, None, True, True)
        cell = next(c for f in data['floors'] for c in f['cells']
                    if f['id'] == self.floor.id and c['stage'] == 'assembly')
        self.assertEqual(cell['status'], 'no_order')
        self.assertNotIn(cell['stage_label'], [item['stage'] for item in
                                               data['indicators']['late']['items']])

    def test_order_title_and_previous_stage(self):
        """Correcciones del tablero: CT-02, los pisos en el orden del árbol, del
        más alto al más bajo, no por creación; CT-03, el título dice las etapas
        prendidas; CT-06, la etapa anterior del catálogo llega aunque esté
        oculta."""
        self.task('Piso 01', 'floor')  # creado después del 05, misma secuencia
        data = self.Board.get_data(self.project.id)
        names = [floor['name'] for floor in data['floors']]
        self.assertLess(names.index('Piso 05'), names.index('Piso 01'))
        self.assertEqual(data['title'], 'Control semanal de instalación')
        both = self.Board.get_data(self.project.id, None, None, True, True)
        self.assertEqual(both['title'], 'Control semanal de producción e instalación')
        self.assertTrue(both['production'])
        self.assertEqual(self.Board._title(True, False), 'Control semanal de producción')
        # Armado, programado en la semana 1, termina en la 2: la instalación lo
        # dice con solo «Instalación» prendida.
        assembly = self.env['construction.resource.plan.line'].with_context(
            construction_plan_force=True).create({
                'plan_id': self.plan.id, 'task_id': self.space_501.id,
                'resource_type': 'contract', 'activity_id': self.act_screw.id,
                'stage': 'assembly', 'partner_id': self.contractor.id, 'qty_planned': 2.0,
                'price_unit_planned': 6.0, 'product_uom_id': self.act_screw.uom_id.id})
        self.env['construction.space.stage'].create({
            'space_task_id': self.space_501.id, 'stage': 'assembly',
            'date_start': self.origin, 'date_end': self.origin + timedelta(days=4)})
        self._validate(assembly, self.origin + timedelta(days=8))
        cell = self._cell(self.Board.get_data(self.project.id))
        previous = cell['previous']
        self.assertEqual(previous['stage_label'],
                         self.env.ref('al_construction_planner.stage_assembly')._label())
        if 'construction_space_task_ids' in self.env['mrp.production']._fields:
            # Con Fabricación, armado avanza con las órdenes: sin orden, «Sin
            # orden», pero la celda igual dice su etapa anterior.
            self.assertEqual(previous['status'], 'no_order')
        else:
            self.assertEqual((previous['status'], previous['finish_week'],
                              previous['delay_weeks']), ('done', 2, 1))


@tagged('post_install', '-at_install')
class TestInstallationBoardTour(HttpCase, PlannerCommon):
    """Correcciones del tablero: la prueba de pantalla recorre la obra, una
    celda, el número de un piso, Producción, el período, los atajos y el
    indicador de mano de obra; falla si aparece un error."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _board_data(cls)
        cls.project.name = 'Obra tablero (test)'
        cls.task('Piso 01', 'floor')

    def setUp(self):
        super().setUp()
        # Los datos son de la compañía del entorno; la base puede tener al
        # administrador en otra.
        grp = 'al_construction_planner.group_planner_'
        self.env.ref('base.user_admin').write({
            'company_ids': [Command.link(self.env.company.id)],
            'company_id': self.env.company.id,
            'group_ids': [Command.link(self.env.ref(grp + 'user').id),
                          Command.link(self.env.ref(grp + 'feature_control').id)]})

    def test_board_tour(self):
        self.start_tour('/odoo', 'al_construction_installation_board', login='admin')



@tagged('post_install', '-at_install')
class TestInstallationBoardBudget(PlannerCommon):
    """Correcciones del tablero: CT-16 (lo real de la contrata se reparte por
    lo que cada piso avanzó dentro del período), CT-15 (presupuesto de las sub
    etapas de producción en soles) y CT-14 (el indicador abre el control
    semanal de la obra en el período)."""

    _validate = TestInstallationBoard._validate

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _board_data(cls)

    def test_real_split_by_period_progress(self):
        floor_04 = self.task('Piso 04', 'floor')
        apt = self.task('Dpto 401', 'apartment', floor_04)
        space_401 = self.task('Cocina', 'space', apt, construction_typology_id=self.typology.id)
        line_04 = self.env['construction.resource.plan.line'].with_context(
            construction_plan_force=True).create({
                'plan_id': self.plan.id, 'task_id': space_401.id, 'resource_type': 'contract',
                'activity_id': self.act_inst_low.id, 'stage': 'installation',
                'partner_id': self.contractor.id, 'qty_planned': 2.0,
                'price_unit_planned': 16.0, 'product_uom_id': self.act_inst_low.uom_id.id})
        # El piso 05 termina en la semana 1; el 04 avanza en la semana 3.
        for line in self.lines:
            self._validate(line, self.origin + timedelta(days=2))
        self._validate(line_04, self.origin + timedelta(days=15))
        budget = self.env['construction.labor.budget'].create({
            'project_id': self.project.id, 'mode': 'contract',
            'stage_id': self.env.ref('al_construction_planner.stage_installation').id})
        self.env['construction.labor.weekly.control'].create({
            'project_id': self.project.id, 'budget_id': budget.id,
            'partner_id': self.contractor.id,
            'week_start': self.origin + timedelta(days=14),
            'progress': 2.0, 'person_days_real': 4.0, 'progress_person_days': 3.0})
        data = self.Board.get_data(self.project.id, 2, 3)
        cells = {f['name']: f['cells'][0] for f in data['floors']}
        self.assertEqual(cells['Piso 05']['budget'].get('real_pd', 0.0), 0.0)
        self.assertEqual(cells['Piso 04']['budget']['real_pd'], 4.0)
        self.assertEqual(cells['Piso 04']['budget']['advance_pd'], 3.0)
        self.assertEqual(cells['Piso 04']['budget']['state'], 'outside')
        self.assertIn('por', cells['Piso 04']['budget']['basis'])
        # CT-14: el control semanal de la obra, en las semanas del período.
        action = self.Board.action_labor_control(
            self.project.id, data['period_start'], data['period_last_monday'])
        self.assertIn(('project_id', '=', self.project.id), action['domain'])
        self.assertIn(('week_start', '>=', data['period_start']), action['domain'])

    def test_production_budget_in_soles(self):
        product = self.env['product.product'].create({'name': 'Tablero (test tablero)',
                                                      'type': 'consu'})
        material = self.env['construction.resource.plan.line'].with_context(
            construction_plan_force=True).create({
                'plan_id': self.plan.id, 'task_id': self.space_501.id,
                'resource_type': 'material', 'product_id': product.id, 'stage': 'production',
                'qty_planned': 10.0, 'price_unit_planned': 10.0,
                'product_uom_id': product.uom_id.id})
        stages = self.env.ref('al_construction_planner.stage_production')
        key = (self.floor.id, 'production')
        cells = {key: {'status': 'current', 'pct': 50, 'consumed': 60.0}}
        # 100 de materiales, la mitad avanzada (50) y 60 consumidos: +20 %.
        self.Board._production_budget(cells, stages, material, {}, True, 10.0)
        self.assertEqual(cells[key]['budget']['state'], 'outside')
        self.assertEqual(cells[key]['budget']['deviation'], 20.0)
        self.assertEqual(cells[key]['budget']['advance_amount'], 50.0)
        # Sin «Ve montos», solo el semáforo.
        cells = {key: {'status': 'current', 'pct': 50, 'consumed': 52.0}}
        self.Board._production_budget(cells, stages, material, {}, False, 10.0)
        self.assertEqual(cells[key]['budget']['state'], 'band')
        self.assertNotIn('advance_amount', cells[key]['budget'])
