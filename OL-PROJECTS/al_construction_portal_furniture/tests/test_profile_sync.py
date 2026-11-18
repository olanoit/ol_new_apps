# -*- coding: utf-8 -*-
"""Paquete 1.22, etapa 2: las funciones de campo de mobiliario son funciones
del perfil de la obra y la ficha del departamento llega en la
sincronización. Datos ficticios."""
from odoo.exceptions import UserError
from odoo.tests import tagged

from ..models.vertical_profile import PORTAL_FIELDS
from .common import PHOTOS, FurniturePortalCommon

FEATURES = {'module_reception', 'replacement', 'measure', 'stage_progress', 'contractor_units'}


@tagged('post_install', '-at_install')
class TestFurnitureProfileSync(FurniturePortalCommon):

    def test_defaults_only_in_the_furniture_profile(self):
        Profile = self.env['construction.vertical.profile']
        construction = self.env.ref('al_construction_planner.profile_construction')
        self.profile.write({name: False for name in PORTAL_FIELDS})
        new = construction.copy({'name': 'Perfil nuevo (p122f)', 'code': 'p122f_new'})
        Profile._portal_furniture_enable_defaults()
        for name in PORTAL_FIELDS:
            self.assertTrue(self.profile[name], name)
            self.assertFalse(new[name], name)
            self.assertFalse(construction[name], name)

    def test_features_follow_the_profile(self):
        service = self._service(self.office_user)
        data = service.sync(self.project.id)
        self.assertTrue(FEATURES <= set(data['features']))
        self.assertIn('furniture', data)
        self.project.construction_profile_id = self.profile_off
        data = service.sync(self.project.id)
        self.assertFalse(FEATURES & set(data['features']))
        self.assertNotIn('furniture', data)
        # Sin perfil en la obra ni en la compañía: todo activo, como lo demás.
        self.project.construction_profile_id = False
        self.company.construction_profile_id = False
        self.assertTrue(FEATURES <= set(service.sync(self.project.id)['features']))

    def test_feature_off_answers_with_a_message(self):
        self.project.construction_profile_id = self.profile_off
        service = self._service(self.office_user)
        base = {'project_id': self.project.id, 'photos': PHOTOS}
        with self.assertRaisesRegex(UserError, 'no recibe módulos'):
            service.module_reception(dict(base, uuid='p122f-off-1', picking_id=0))
        with self.assertRaisesRegex(UserError, 'no pide reposiciones'):
            service.replacement(dict(base, uuid='p122f-off-2', task_id=self.modules[0].id,
                                     qty=1, reason_id=self.reason.id))
        with self.assertRaisesRegex(UserError, 'no marca ambientes medidos'):
            service.measure(dict(base, uuid='p122f-off-3', space_ids=self.kitchen_502.ids))
        with self.assertRaisesRegex(UserError, 'no usa el avance por sub etapa'):
            service.stage_progress(dict(base, uuid='p122f-off-4', cells=[
                {'space_id': self.kitchen_502.id, 'stage': 'installation', 'pct': 100}]))

    def test_department_card(self):
        """Ficha del departamento: la etapa actual de cada ambiente, sus
        módulos por rótulo del ETO y las sub etapas de instalación de la
        obra (sin el armado de planta)."""
        data = self._service(self.office_user).sync(self.project.id)
        furniture = data['furniture']
        codes = [stage['code'] for stage in furniture['stages']]
        self.assertIn('installation', codes)
        self.assertIn('finishing', codes)
        self.assertNotIn('assembly', codes)
        self.assertNotIn('production', codes)
        self.assertIn(self.apt_501.id, furniture['apartments'])
        card = furniture['apartments'][self.apt_502.id]
        self.assertEqual(card['name'], 'Dpto 502')
        spaces = {space['id']: space for space in card['spaces']}
        self.assertTrue({self.kitchen_502.id, self.closet_502.id} <= set(spaces))
        kitchen = spaces[self.kitchen_502.id]
        self.assertEqual(kitchen['stage'], self.kitchen_502.construction_current_stage or '')
        self.assertFalse(kitchen['measured'])
        modules = [m for m in card['modules'] if m['space_id'] == self.kitchen_502.id]
        self.assertEqual(sorted(m['label'] for m in modules), ['MA-1', 'MB-1'])
        self.assertEqual({m['typology'] for m in modules}, {'C22'})
        self.assertIn([self.reason.id, self.reason.name], furniture['reasons'])
        # La unidad de entrega es el grupo «apartment» de «Avance».
        self.assertEqual(data['groups'][self.apt_502.id]['kind'], 'apartment')

    def test_contractor_sees_only_its_departments(self):
        data = self._service(self.contractor_user).sync(self.project.id)
        furniture = data['furniture']
        self.assertEqual(list(furniture['apartments']), [self.apt_501.id])
        self.assertFalse(furniture['apartments'][self.apt_501.id]['modules'])
        self.assertFalse(furniture['reasons'])
        self.assertEqual({row['task_id'] for row in data['partidas']}, {self.kitchen_501.id})
        self.assertEqual(furniture['week']['rows'], [])
