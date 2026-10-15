# -*- coding: utf-8 -*-
"""Material extra, su aprobación y el descuento a la contrata (v1.6, M16-05 a
M16-08).

El capataz pide desde el portal 3 planchas de melamina por merma: queda un
requerimiento extra en borrador con una actividad a la jefatura, que lo
aprueba (regla propia, esté o no dentro del plan) y decide descontarlo a la
contrata. La siguiente liquidación semanal de esa contrata en la obra lleva
el descuento como línea negativa de la factura.
"""
import re
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import HttpCase, new_test_user, tagged

from .common import PlannerCommon
from .test_contracts import TestContracts
from .test_portal_v15 import PNG


class ExtraCommon:

    @classmethod
    def _only_extra_rule(cls):
        cls.tier_extra = cls.env.ref('al_construction_planner_purchase.tier_material_request_extra')
        cls.env['tier.definition'].search([
            ('model', '=', 'construction.material.request'),
            ('id', '!=', cls.tier_extra.id)]).active = False
        cls.tier_extra.active = True


@tagged('post_install', '-at_install')
class TestExtraMaterial(ExtraCommon, PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._only_extra_rule()
        cls.company._al_construction_ensure_setup()
        cls.manager = new_test_user(
            cls.env, 'extra_jefatura', name='Jefatura (test)',
            groups='al_construction_planner.group_planner_project_head')
        cls.buyer = new_test_user(
            cls.env, 'extra_residente', name='Residente (test)',
            groups='al_construction_planner.group_planner_planner,'
                   'al_construction_material_request.group_construction_requester')
        cls.project.message_subscribe(partner_ids=(cls.buyer | cls.manager).partner_id.ids)

    def _request(self, **vals):
        return self.env['construction.material.request'].with_user(self.buyer).create({
            'project_id': self.project.id,
            'task_id': self.space_501.id,
            'line_ids': [(0, 0, {'product_id': self.p_white.id, 'product_qty': 3})],
            **vals,
        })

    def test_extra_goes_to_project_management(self):
        extra = self._request(is_extra=True, extra_reason='waste')
        extra.action_request_approval()
        self.assertEqual(extra.state, 'to_approve')
        self.assertEqual(extra.review_ids.definition_id, self.tier_extra)
        extra.with_user(self.manager).validate_tier()
        self.assertEqual(extra.state, 'approved')

    def test_regular_request_skips_extra_rule(self):
        request = self._request()
        request.action_request_approval()
        self.assertFalse(request.review_ids)
        self.assertEqual(request.state, 'approved')

    def test_discount_is_decided_by_management(self):
        self.p_white.standard_price = 25.0
        extra = self._request(is_extra=True, extra_reason='measure_error')
        self.assertTrue(extra.amount_estimated)
        with self.assertRaises(UserError):
            extra.write({'construction_discount': True,
                         'construction_discount_partner_id': self.contractor.id})
        with self.assertRaises(UserError):
            self._request(is_extra=True, extra_reason='waste', construction_discount=True,
                          construction_discount_partner_id=self.contractor.id)
        extra.with_user(self.manager).write({
            'construction_discount': True,
            'construction_discount_partner_id': self.contractor.id})
        self.assertAlmostEqual(extra.construction_discount_amount, extra.amount_estimated)
        # El manager decide al aprobar: la revisión pendiente no bloquea el
        # descuento.
        extra.action_request_approval()
        extra.with_user(self.manager).write({'construction_discount_amount': 40.0})
        self.assertEqual(extra.construction_discount_amount, 40.0)


@tagged('post_install', '-at_install')
class TestExtraDiscount(ExtraCommon, TestContracts):
    """Sobre la liquidación del piso 05 del demo (bruto 380.88, retención
    38.09)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._only_extra_rule()
        cls.tier_extra.active = False
        cls.project.message_subscribe(partner_ids=cls.manager.partner_id.ids)
        cls.env.company._al_construction_ensure_setup()
        cls.discount_account = cls.env['account.account'].search([
            ('company_ids', 'in', cls.env.company.id),
            ('account_type', '=', 'expense')], limit=1)
        cls.env.company.construction_discount_account_id = cls.discount_account
        # Con retención en la factura: las dos líneas negativas cuadran el neto.
        cls.env.company.construction_retention_account_id = cls.env['account.account'].search([
            ('company_ids', 'in', cls.env.company.id),
            ('account_type', '=', 'liability_current')], limit=1)
        cls.extra = cls.env['construction.material.request'].create({
            'project_id': cls.project.id,
            'task_id': cls.spaces['Dpto 501'].id,
            'is_extra': True,
            'extra_reason': 'waste',
            'line_ids': [(0, 0, {'product_id': cls.plan.line_ids.filtered(
                lambda l: l.resource_type == 'material' and l.product_id)[:1].product_id.id,
                'product_qty': 2})],
        })
        cls.extra.action_request_approval()
        cls.extra.with_user(cls.manager).write({
            'construction_discount': True,
            'construction_discount_partner_id': cls.leandro.id,
            'construction_discount_amount': 50.0})

    def _settlement(self):
        self._assign_installation()
        self._confirm_order()
        self._report_example().with_user(self.planner).action_validate()
        return self.env['construction.contract.settlement']._prepare_settlements(
            date(2026, 11, 5), self.project)

    def test_discount_in_weekly_settlement(self):
        self.assertEqual(self.extra.state, 'approved')
        settlement = self._settlement()
        self.assertEqual(settlement.discount_request_ids, self.extra)
        self.assertEqual(self.extra.construction_discount_settlement_id, settlement)
        self.assertAlmostEqual(settlement.amount_discount, 50.0)
        self.assertAlmostEqual(settlement.amount_net, 380.88 - 38.09 - 50.0)
        with self.assertRaises(UserError):
            self.extra.with_user(self.manager).construction_discount_amount = 10.0

        settlement.with_user(self.planner).action_submit()
        settlement.with_user(self.planner).action_validate()
        settlement.with_user(self.manager).validate_tier()
        self.assertEqual(settlement.state, 'approved')
        line = settlement.invoice_id.invoice_line_ids.filtered(
            lambda l: l.account_id == self.discount_account and self.extra.name in l.name)
        self.assertAlmostEqual(line.price_subtotal, -50.0)
        self.assertAlmostEqual(settlement.invoice_id.amount_untaxed, 380.88 - 38.09 - 50.0)

    def test_cancelled_settlement_frees_the_discount(self):
        settlement = self._settlement()
        settlement.with_user(self.planner).action_cancel()
        self.assertFalse(self.extra.construction_discount_settlement_id)
        settlement.with_user(self.planner).action_draft()
        self.assertEqual(settlement.discount_request_ids, self.extra)

    def test_discount_needs_account(self):
        self.env.company.construction_discount_account_id = False
        settlement = self._settlement()
        settlement.with_user(self.planner).action_submit()
        with self.assertRaises(UserError):
            settlement.with_user(self.planner).action_validate()
            settlement.with_user(self.manager).validate_tier()

    def test_other_contractor_is_not_discounted(self):
        self.extra.with_user(self.manager).construction_discount_partner_id = self.gonza
        self.assertFalse(self._settlement().discount_request_ids)


# Solo las pruebas propias: las de TestContracts ya corren en su clase.
for _name in dir(TestContracts):
    if _name.startswith('test_') and _name not in vars(TestExtraDiscount):
        setattr(TestExtraDiscount, _name, None)


@tagged('post_install', '-at_install')
class TestPortalExtra(ExtraCommon, HttpCase, PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._only_extra_rule()
        cls.company._al_construction_ensure_setup()
        wizard = cls.env['construction.plan.generate.wizard'].create({'plan_id': cls.plan.id})
        wizard.action_generate()
        cls.plan.line_ids.filtered(lambda l: not l.stage).stage = 'production'
        for line in cls.plan.line_ids.filtered(lambda l: not l.price_unit_planned):
            line.price_unit_planned = 10.0
        cls.plan.line_ids.filtered(
            lambda l: l.resource_type == 'contract' and l.activity_id == cls.act_doors
        ).partner_id = cls.contractor
        cls.plan.action_request_approval()
        cls.project.user_id = new_test_user(
            cls.env, 'extra_jefe_obra', name='Jefe de la obra (test)',
            groups='al_construction_planner.group_planner_manager')
        cls.portal_user = new_test_user(
            cls.env, 'capataz_extra', groups='base.group_portal', name='Capataz extra (test)',
            partner_id=cls.env['res.partner'].create({
                'name': 'Capataz extra (test)', 'parent_id': cls.contractor.id}).id)
        new_test_user(cls.env, 'otra_contrata_extra', groups='base.group_portal',
                      name='Otra contrata extra (test)')

    def _csrf(self, url):
        page = self.url_open(url)
        return re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)

    def test_portal_extra_request(self):
        self.authenticate('capataz_extra', 'capataz_extra')
        self.assertIn('/my/obra/material', self.url_open('/my/obra').text)
        url = '/my/obra/material?project_id=%s' % self.project.id
        page = self.url_open(url)
        self.assertIn(self.p_white.name, page.text)
        response = self.url_open(url, data={
            'csrf_token': self._csrf(url),
            'task_id': str(self.space_501.id), 'product_id': str(self.p_white.id),
            'qty': '3', 'reason': 'waste', 'note': 'Se rompió una plancha al cortar',
        }, files={'photo': ('merma.png', PNG, 'image/png')})
        self.assertEqual(response.status_code, 200)
        self.assertIn('queda en borrador', response.text)
        extra = self.env['construction.material.request'].search([
            ('project_id', '=', self.project.id), ('is_extra', '=', True)])
        self.assertEqual(len(extra), 1)
        self.assertEqual((extra.state, extra.extra_reason, extra.task_id),
                         ('draft', 'waste', self.space_501))
        self.assertEqual(extra.requested_by, self.portal_user)
        self.assertEqual((extra.line_ids.product_id, extra.line_ids.product_qty), (self.p_white, 3))
        self.assertFalse(extra.picking_ids, 'no reserva stock')
        self.assertEqual(self.env['ir.attachment'].search_count([
            ('res_model', '=', extra._name), ('res_id', '=', extra.id)]), 1)
        self.assertEqual(extra.activity_ids.user_id, self.project.user_id)

    def test_portal_extra_rejects_foreign_data(self):
        self.authenticate('capataz_extra', 'capataz_extra')
        url = '/my/obra/material?project_id=%s' % self.project.id
        foreign = self.env['product.product'].create({'name': 'Fuera del plan (test)'})
        response = self.url_open(url, data={
            'csrf_token': self._csrf(url),
            'task_id': str(self.space_501.id), 'product_id': str(foreign.id),
            'qty': '3', 'reason': 'waste'})
        self.assertIn('Elija el material', response.text)
        response = self.url_open(url, data={
            'csrf_token': self._csrf(url),
            'task_id': str(self.space_501.id), 'product_id': str(self.p_white.id),
            'qty': '3', 'reason': 'otro'})
        self.assertIn('Elija el motivo', response.text)
        self.assertFalse(self.env['construction.material.request'].search([
            ('project_id', '=', self.project.id), ('is_extra', '=', True)]))
        # Otra contrata no entra al formulario de esa obra.
        self.authenticate('otra_contrata_extra', 'otra_contrata_extra')
        self.assertNotIn('/my/obra/material', self.url_open(url).url)
