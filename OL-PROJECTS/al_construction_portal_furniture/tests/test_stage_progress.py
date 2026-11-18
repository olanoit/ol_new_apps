# -*- coding: utf-8 -*-
"""M122-08 (avance por sub etapa del departamento) y M122-09 (avance de la
contrata por departamento) con usuarios de portal. Datos ficticios."""
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.al_construction_planner.models.common import PLAN_FORCE

from .common import PHOTOS, FurniturePortalCommon


@tagged('post_install', '-at_install')
class TestStageProgress(FurniturePortalCommon):

    def _values(self, uuid, cells, **extra):
        return dict({'uuid': uuid, 'project_id': self.project.id, 'date': self._today(),
                     'photos': PHOTOS,
                     'cells': [{'space_id': space.id, 'stage': stage, 'pct': pct}
                               for space, stage, pct in cells]}, **extra)

    def _set_policy(self, policy):
        vals = {'exceed_policy': policy, 'exceed_tolerance': 0.0}
        for name in ('exceed_policy_contract', 'exceed_policy_labor'):
            if name in self.plan._fields:
                vals[name] = False
        self.plan.write(vals)

    def test_whole_department_in_one_submission(self):
        service = self._service(self.office_user)
        spaces = self.kitchen_502 | self.closet_502
        # La línea del ambiente y las de sus módulos en esa sub etapa.
        install = self._stage_lines(spaces)
        finish = self._line(self.kitchen_502, self.act_finish) \
            | self._line(self.closet_502, self.act_finish)
        self.assertGreaterEqual(len(install), 2)
        cells = [(space, 'installation', 100) for space in spaces]
        # La foto es obligatoria.
        with self.assertRaises(UserError):
            service.stage_progress(self._values('p122f-sp-0', cells, photos=[]))
        values = self._values('p122f-sp-1', cells)
        result = service.stage_progress(values)
        self.assertEqual((result['count'], result['skipped']), (len(install), 0))
        progress = self._progress(install)
        self.assertEqual(len(progress), len(install))
        for record in progress:
            self.assertEqual(record.qty, record.plan_line_id.qty_planned)
        self.assertEqual(set(progress.mapped('state')), {'draft'})
        self.assertEqual(set(progress.mapped('source')), {'portal'})
        self.assertEqual(progress.reported_by_id, self.office_user)
        # Una sola foto del celular: cada avance tiene la suya.
        for record in progress:
            self.assertEqual(len(record.attachment_ids), 1)
            self.assertEqual(record.attachment_ids.res_id, record.id)
        # Ni el acabado ni el armado de planta reciben avance.
        self.assertFalse(self._progress(finish))
        self.assertFalse(self._progress(self.plan.line_ids - install))
        # Envío repetido sin señal: no duplica.
        again = service.stage_progress(values)
        self.assertTrue(again.get('duplicate'))
        self.assertEqual(len(self._progress(install)), len(install))
        # Otro envío igual: ya no queda saldo en esas líneas.
        with self.assertRaisesRegex(UserError, 'no queda saldo'):
            service.stage_progress(self._values('p122f-sp-2', cells))
        # El residente lo valida como cualquier avance.
        self._validate(progress)
        for line in install:
            self.assertEqual(line.qty_executed, line.qty_planned)

    def test_line_already_complete_registers_nothing(self):
        service = self._service(self.office_user)
        kitchen = self._stage_lines(self.kitchen_502)
        closet = self._stage_lines(self.closet_502)
        service.stage_progress(self._values(
            'p122f-sp-k', [(self.kitchen_502, 'installation', 100)]))
        self._validate(self._progress(kitchen))
        result = service.stage_progress(self._values('p122f-sp-all', [
            (self.kitchen_502, 'installation', 100), (self.closet_502, 'installation', 100)]))
        self.assertEqual((result['count'], result['skipped']), (len(closet), len(kitchen)))
        self.assertEqual(len(self._progress(kitchen)), len(kitchen))
        self.assertEqual(sum(self._progress(closet).mapped('qty')),
                         sum(closet.mapped('qty_planned')))

    def test_percentage_registers_the_balance_to_reach_it(self):
        service = self._service(self.office_user)
        line = self._line(self.kitchen_502, self.act_install)
        service.stage_progress(self._values(
            'p122f-sp-50', [(self.kitchen_502, 'installation', 50)]))
        self.assertEqual(self._progress(line).qty, 2.0)
        service.stage_progress(self._values(
            'p122f-sp-75', [(self.kitchen_502, 'installation', 75)]))
        self.assertEqual(sorted(self._progress(line).mapped('qty')), [1.0, 2.0])

    def test_eighty_lines_in_one_submission(self):
        Activity = self.env['construction.labor.activity']
        Line = self.env['construction.resource.plan.line']
        activities = Activity.create([{
            'code': 'P122F-M%02d' % index, 'name': 'Instalación %02d (p122f)' % index,
            'stage': 'installation', 'default_price': 1.0, 'uom_id': self.unit.id}
            for index in range(80)])
        # El plan ya está aprobado: las líneas entran como las del sistema.
        many = Line.with_context(construction_plan_force=PLAN_FORCE).create([{
            'plan_id': self.plan.id, 'task_id': self.closet_502.id, 'resource_type': 'labor',
            'activity_id': activity.id, 'stage': 'installation', 'qty_planned': 3.0,
            'price_unit_planned': 1.0, 'product_uom_id': self.unit.id}
            for activity in activities])
        service = self._service(self.foreman_user)
        values = self._values('p122f-sp-80', [(self.closet_502, 'installation', 100)])
        result = service.stage_progress(values)
        # Las 80 más la línea de instalación del ambiente.
        self.assertEqual(result['count'], 81)
        progress = self._progress(many)
        self.assertEqual(len(progress), 80)
        self.assertEqual(set(progress.mapped('qty')), {3.0})
        self.assertEqual(len(progress.attachment_ids), 80)
        self.assertEqual(len(result['ids'].split(',')), 81)
        self.assertTrue(service.stage_progress(values).get('duplicate'))
        self.assertEqual(len(self._progress(many)), 80)

    def test_same_rules_as_a_single_progress(self):
        service = self._service(self.office_user)
        line = self._line(self.kitchen_502, self.act_install)
        cells = [(self.kitchen_502, 'installation', 150)]
        # Política «bloquear»: sobre el saldo y la tolerancia no entra.
        self._set_policy('block')
        with self.assertRaises(ValidationError):
            service.stage_progress(self._values('p122f-sp-b', cells))
        self.assertFalse(self._progress(line))
        # Política «aprobación»: entra como exceso para la jefatura.
        self._set_policy('approval')
        result = service.stage_progress(self._values('p122f-sp-a', cells))
        self.assertEqual(result['exceeded'], len(self._stage_lines(self.kitchen_502)))
        self.assertEqual(self._progress(line).exceed_state, 'exceeded')
        # Una sub etapa que no es de instalación (el armado) no se reporta aquí.
        with self.assertRaisesRegex(UserError, 'no es de instalación'):
            service.stage_progress(self._values(
                'p122f-sp-arm', [(self.kitchen_502, 'assembly', 100)]))
        # La fecha sigue la regla del avance: no puede ser futura.
        with self.assertRaises(UserError):
            service.stage_progress(self._values(
                'p122f-sp-f', [(self.closet_502, 'installation', 100)], date='2999-01-01'))

    # ------------------------------------------------------------------
    # M122-09
    # ------------------------------------------------------------------
    def test_contractor_reports_only_its_activities(self):
        service = self._service(self.contractor_user)
        own = self._line(self.kitchen_501, self.act_install)
        data = service.sync(self.project.id)
        self.assertEqual({row['task_id'] for row in data['partidas']}, {self.kitchen_501.id})
        self.assertEqual({row['kind'] for row in data['partidas']}, {'contract'})
        # Un ambiente que no es de su contrata: no alcanza sus líneas.
        with self.assertRaises(AccessError):
            service.stage_progress(self._values(
                'p122f-sp-c0', [(self.kitchen_502, 'installation', 100)]))
        self.assertFalse(self._progress(self._line(self.kitchen_502, self.act_install)))
        result = service.stage_progress(self._values('p122f-sp-c1', [
            (self.kitchen_501, 'installation', 100), (self.kitchen_502, 'installation', 100)]))
        self.assertEqual(result['count'], 1)
        progress = self._progress(own)
        self.assertEqual(progress.qty, 4.0)
        self.assertEqual(progress.partner_id, self.contractor)
        # «Esta semana»: lo reportado y lo validado en la unidad del driver.
        week = service.sync(self.project.id)['furniture']['week']
        self.assertEqual([(row['uom'], row['reported'], row['validated'])
                          for row in week['rows']], [(self.unit.name, 4.0, 0.0)])
        self._validate(progress)
        furniture = service.sync(self.project.id)['furniture']
        self.assertEqual([(row['reported'], row['validated'])
                          for row in furniture['week']['rows']], [(4.0, 4.0)])
        self.assertEqual(furniture['settled'], {})
        # El capataz no ve «Esta semana» de la contrata.
        self.assertFalse(
            self._service(self.foreman_user).sync(self.project.id)['furniture']['week'])
