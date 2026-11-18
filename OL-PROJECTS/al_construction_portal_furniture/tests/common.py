# -*- coding: utf-8 -*-
"""Obra de mobiliario para las pruebas del portal (paquete 1.22, etapa 2).

Parte de la obra ficticia de la suite del planificador (``PlannerCommon``:
piso 05 con los Dptos 501 y 502) y le agrega una tipología con dos módulos
con rótulo del ETO, tres ambientes (uno en el 501 y dos en el 502), líneas de
instalación y acabado por ambiente (contrata en el 501, personal propio en el
502) y personas del portal sin permisos internos. Datos ficticios."""
from odoo import Command, fields
from odoo.tests import new_test_user

from odoo.addons.al_construction_planner_suite.tests.common import PlannerCommon

from ..models.vertical_profile import PORTAL_FIELDS

# PNG de 1 × 1 píxel.
PHOTO = ('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAE'
         'hQGAhKmMIQAAAABJRU5ErkJggg==')
PHOTOS = [{'name': 'foto.jpg', 'mimetype': 'image/png', 'data': PHOTO}]


class FurniturePortalCommon(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Activity = env['construction.labor.activity']
        cls.act_install = Activity.create({
            'code': 'P122F-INS', 'name': 'Instalación de módulos (p122f)',
            'stage': 'installation', 'default_price': 10.0, 'uom_id': cls.unit.id})
        cls.act_finish = Activity.create({
            'code': 'P122F-ACA', 'name': 'Acabado (p122f)', 'stage': 'finishing',
            'default_price': 4.0, 'uom_id': cls.unit.id})
        cls.board = env['product.product'].create({
            'name': 'Melamina blanca (p122f)', 'type': 'consu', 'standard_price': 100.0})
        cls.typology_p = env['construction.typology'].create({
            'project_id': cls.project.id, 'code': 'C22', 'name': 'COCINA 22 (p122f)',
            'family': 'kitchen', 'module_line_ids': [
                Command.create({
                    'code': code, 'name': name, 'eto_label': label, 'module_type': kind,
                    'width_mm': 600, 'ml_group': kind,
                    'assembly_activity_id': cls.act_screw.id,
                    'material_ids': [Command.create({
                        'product_id': cls.board.id, 'qty': 1.0, 'stage': 'production'})]})
                for code, name, label, kind in (
                    ('MB1', 'MOD BAJO 600', 'MB-1', 'low'),
                    ('MA1', 'MOD ALTO 600', 'MA-1', 'high'))]})
        cls.kitchen_501 = cls.task('Cocina C22', 'space', cls.apt_501,
                                   construction_typology_id=cls.typology_p.id)
        cls.kitchen_502 = cls.task('Cocina C22', 'space', cls.apt_502,
                                   construction_typology_id=cls.typology_p.id)
        cls.closet_502 = cls.task('Closet C22', 'space', cls.apt_502,
                                  construction_typology_id=cls.typology_p.id)
        cls.spaces = cls.kitchen_501 | cls.kitchen_502 | cls.closet_502
        wizard = env['construction.plan.generate.wizard'].create({
            'plan_id': cls.plan.id, 'space_task_ids': [Command.set(cls.spaces.ids)]})
        wizard.action_generate()
        Line = env['construction.resource.plan.line']
        for space in cls.spaces:
            # El 501 lo instala la contrata; el 502, personal propio.
            own = space != cls.kitchen_501
            common = {'plan_id': cls.plan.id, 'task_id': space.id,
                      'resource_type': 'labor' if own else 'contract',
                      'partner_id': False if own else cls.contractor.id,
                      'product_uom_id': cls.unit.id}
            Line.create([
                dict(common, activity_id=cls.act_install.id, stage='installation',
                     qty_planned=4.0, price_unit_planned=10.0),
                dict(common, activity_id=cls.act_finish.id, stage='finishing',
                     qty_planned=2.0, price_unit_planned=4.0)])
        lines = cls.plan.line_ids
        lines.filtered(lambda l: not l.stage).stage = 'production'
        for line in lines.filtered(lambda l: not l.price_unit_planned):
            line.price_unit_planned = 10.0
        cls.plan.action_request_approval()
        assert cls.plan.state == 'approved', cls.plan.state
        cls.modules = env['project.task'].search([
            ('construction_space_task_id', 'in', cls.spaces.ids),
            ('construction_level', '=', 'module')])

        # Las funciones del puente, como las deja su instalación.
        cls.profile = env.ref('al_construction_planner.profile_furniture')
        cls.profile.write(dict({name: True for name in PORTAL_FIELDS}, feature_progress=True))
        cls.project.construction_profile_id = cls.profile
        cls.profile_off = cls.profile.copy(dict(
            {name: False for name in PORTAL_FIELDS}, name='Sin funciones de campo (p122f)',
            code='p122f_off'))

        cls.project._al_construction_create_locations()
        cls.warehouse = env['stock.warehouse'].search(
            [('company_id', '=', cls.company.id)], limit=1)
        # El envío de planta a obra sale con el tipo interno del almacén.
        cls.company.construction_dispatch_picking_type_id = False
        cls.warehouse.int_type_id.construction_site_dispatch = False

        def portal_user(login, name):
            return new_test_user(env, login, groups='base.group_portal', name=name)

        cls.office_user = portal_user('p122f_oficina', 'Oficina técnica (p122f)')
        cls.foreman_user = portal_user('p122f_capataz', 'Capataz (p122f)')
        cls.contractor_user = portal_user('p122f_contrata', 'Supervisor de contrata (p122f)')
        cls.contractor_user.partner_id.parent_id = cls.contractor
        cls.outsider_user = portal_user('p122f_vecino', 'Capataz de otra obra (p122f)')
        cls.other_project = env['project.project'].create({
            'name': 'Obra vecina (p122f)', 'is_construction_site': True})
        Member = env['construction.portal.member']
        Member.create({'project_id': cls.project.id, 'user_id': cls.office_user.id,
                       'role': 'office'})
        Member.create({'project_id': cls.project.id, 'user_id': cls.foreman_user.id,
                       'role': 'foreman'})
        Member.create({'project_id': cls.project.id, 'user_id': cls.contractor_user.id,
                       'role': 'contractor', 'partner_id': cls.contractor.id})
        Member.create({'project_id': cls.other_project.id, 'user_id': cls.outsider_user.id,
                       'role': 'foreman'})
        cls.validator = new_test_user(
            env, 'p122f_valida', name='Residente interno (p122f)',
            groups='al_construction_planner.group_planner_exec_validator')
        cls.reason = env['construction.production.reason'].create({
            'name': 'Daño en obra (p122f)', 'sequence': 1})

    # ------------------------------------------------------------------
    # Ayudas
    # ------------------------------------------------------------------
    def _service(self, user):
        return self.env['construction.portal.service'].with_user(user).with_context(
            construction_portal_login='password')

    def _today(self):
        return fields.Date.to_string(fields.Date.context_today(self._service(self.office_user)))

    def _module(self, space, code):
        return self.modules.filtered(
            lambda m: m.construction_space_task_id == space
            and m.construction_module_code == code)

    def _line(self, space, activity):
        return self.plan.line_ids.filtered(
            lambda l: l.task_id == space and l.activity_id == activity)

    def _stage_lines(self, spaces, stage='installation'):
        """Líneas de mano de obra del plan de esos ambientes y esa sub etapa:
        la del ambiente y las de sus módulos (lo que alcanza la oficina técnica)."""
        return self.plan.line_ids.filtered(
            lambda l: l.space_task_id in spaces and l.stage == stage and l.activity_id
            and l.resource_type in ('labor', 'contract') and l.line_state != 'cancel')

    def _progress(self, lines):
        return self.env['construction.task.progress'].search(
            [('plan_line_id', 'in', lines.ids)])

    def _validate(self, progress):
        progress.with_user(self.validator).action_validate()

    def _ship(self, apartments):
        """Envío de planta a obra de los módulos de ``apartments``, reservado."""
        Quant = self.env['stock.quant']
        for apartment in apartments:
            for template in self.typology_p.module_line_ids:
                tasks = self.modules.filtered(
                    lambda m: m.construction_apartment_task_id == apartment
                    and m.construction_module_code == template.code)
                lot = self.plan._department_lot(template.product_id, apartment)
                Quant._update_available_quantity(
                    template.product_id, self.warehouse.lot_stock_id, len(tasks), lot_id=lot)
        self.modules.construction_unit_state = 'produced'
        picking = self.plan.action_ship_modules(apartments)
        picking.action_confirm()
        picking.action_assign()
        self.assertEqual(picking.state, 'assigned')
        return picking
