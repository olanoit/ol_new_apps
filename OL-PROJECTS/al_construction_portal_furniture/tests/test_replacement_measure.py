# -*- coding: utf-8 -*-
"""M122-06 (pedir reposición) y M122-07 (marcar medido) con usuarios de
portal sin permisos internos. Datos ficticios."""
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import PHOTOS, FurniturePortalCommon


@tagged('post_install', '-at_install')
class TestReplacementAndMeasure(FurniturePortalCommon):

    # ------------------------------------------------------------------
    # M122-06
    # ------------------------------------------------------------------
    def _replacement_values(self, uuid, **extra):
        module = self._module(self.kitchen_502, 'MA1')
        return dict({'uuid': uuid, 'project_id': self.project.id, 'task_id': module.id,
                     'qty': 1, 'reason_id': self.reason.id,
                     'note': 'Puerta rayada al descargar', 'photos': PHOTOS}, **extra)

    def test_replacement_in_draft_without_duplicates(self):
        Replacement = self.env['construction.replacement.request']
        service = self._service(self.foreman_user)
        self.assertFalse(self.foreman_user.has_group('base.group_user'))
        module = self._module(self.kitchen_502, 'MA1')
        # Sin foto no se puede enviar.
        with self.assertRaises(UserError):
            service.replacement(self._replacement_values('p122f-rep-0', photos=[]))
        with self.assertRaisesRegex(UserError, 'motivo'):
            service.replacement(self._replacement_values('p122f-rep-0', reason_id=False))
        self.assertFalse(Replacement.search([('task_id', '=', module.id)]))
        values = self._replacement_values('p122f-rep-1')
        result = service.replacement(values)
        replacement = Replacement.browse(int(result['ids']))
        self.assertEqual(replacement.state, 'draft')
        self.assertEqual(replacement.project_id, self.project)
        self.assertEqual(replacement.task_id, module)
        self.assertEqual(replacement.product_id, self.typology_p.module_line_ids.filtered(
            lambda m: m.code == 'MA1').product_id)
        self.assertEqual(replacement.product_qty, 1)
        self.assertEqual(replacement.reason_id, self.reason)
        self.assertEqual(replacement.reason_note, 'Puerta rayada al descargar')
        self.assertEqual(replacement.requested_by, self.foreman_user)
        self.assertFalse(replacement.production_id)
        self.assertEqual(self.env['ir.attachment'].search_count([
            ('res_model', '=', 'construction.replacement.request'),
            ('res_id', '=', replacement.id)]), 1)
        # Envío repetido: la misma reposición.
        again = service.replacement(values)
        self.assertTrue(again.get('duplicate'))
        self.assertEqual(again['ids'], result['ids'])
        self.assertEqual(Replacement.search_count([('task_id', '=', module.id)]), 1)
        # La ficha del departamento la muestra abierta, con su estado.
        card = service.sync(self.project.id)['furniture']['apartments'][self.apt_502.id]
        self.assertEqual([(row['name'], row['module'], row['state'])
                          for row in card['replacements']],
                         [(replacement.name, 'MA-1', 'draft')])

    def test_replacement_scope(self):
        with self.assertRaises(AccessError):
            self._service(self.contractor_user).replacement(
                self._replacement_values('p122f-rep-c'))
        with self.assertRaises(AccessError):
            self._service(self.outsider_user).replacement(
                self._replacement_values('p122f-rep-o'))
        # Un ambiente no es un módulo, y el módulo debe ser de la obra.
        with self.assertRaises(AccessError):
            self._service(self.office_user).replacement(
                self._replacement_values('p122f-rep-s', task_id=self.kitchen_502.id))
        with self.assertRaises(UserError):
            self._service(self.outsider_user).replacement(
                self._replacement_values('p122f-rep-p', project_id=self.other_project.id))

    # ------------------------------------------------------------------
    # M122-07
    # ------------------------------------------------------------------
    def _measure_values(self, uuid, spaces, **extra):
        return dict({'uuid': uuid, 'project_id': self.project.id, 'space_ids': spaces.ids,
                     'photos': PHOTOS + PHOTOS, 'note': 'Croquis en la foto 2'}, **extra)

    def test_measure_several_spaces_in_one_submission(self):
        spaces = self.kitchen_502 | self.closet_502
        service = self._service(self.office_user)
        self.assertFalse(self.office_user.has_group(
            'al_construction_planner.group_planner_user'))
        with self.assertRaises(UserError):
            service.measure(self._measure_values('p122f-med-0', spaces, photos=[]))
        self.assertFalse(any(spaces.mapped('construction_measured')))
        values = self._measure_values('p122f-med-1', spaces)
        result = service.measure(values)
        self.assertEqual(result['count'], 2)
        for space in spaces:
            self.assertTrue(space.construction_measured)
            self.assertEqual(str(space.construction_measured_date), self._today())
            self.assertEqual(space.construction_measured_user_id, self.office_user)
            self.assertEqual(len(space.construction_measured_attachment_ids), 2)
            self.assertEqual(set(space.construction_measured_attachment_ids.mapped('res_id')),
                             {space.id})
        self.assertFalse(self.kitchen_501.construction_measured)
        # La ficha ya no los ofrece para medir.
        card = service.sync(self.project.id)['furniture']['apartments'][self.apt_502.id]
        self.assertFalse(any(space['can_measure'] for space in card['spaces']
                             if space['id'] in spaces.ids))
        # Envío repetido: no vuelve a marcar ni a adjuntar.
        again = service.measure(values)
        self.assertTrue(again.get('duplicate'))
        self.assertEqual(len(self.kitchen_502.construction_measured_attachment_ids), 2)
        with self.assertRaisesRegex(UserError, 'ya están medidos'):
            service.measure(self._measure_values('p122f-med-2', spaces))

    def test_measure_rejects_other_people(self):
        spaces = self.kitchen_502
        # Alguien de otra obra, por la obra ajena o por la suya.
        with self.assertRaises(AccessError):
            self._service(self.outsider_user).measure(
                self._measure_values('p122f-med-o1', spaces))
        with self.assertRaises(UserError):
            self._service(self.outsider_user).measure(
                self._measure_values('p122f-med-o2', spaces, project_id=self.other_project.id))
        # La contrata no mide.
        with self.assertRaises(AccessError):
            self._service(self.contractor_user).measure(
                self._measure_values('p122f-med-c', spaces))
        self.assertFalse(spaces.construction_measured)
        # El control del escritorio sigue pidiendo el grupo interno: una
        # marca de contexto enviada por el cliente no vale.
        with self.assertRaises(AccessError):
            spaces.with_user(self.office_user).with_context(
                construction_portal_measure=True)._construction_check_supervisor()
        # El capataz de la obra sí.
        self._service(self.foreman_user).measure(self._measure_values('p122f-med-f', spaces))
        self.assertEqual(spaces.construction_measured_user_id, self.foreman_user)
