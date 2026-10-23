# -*- coding: utf-8 -*-
"""Condiciones de contrata, valorización, adelanto, deductivos, fondo de
garantía y periodicidad (requerimiento CREVAL v1.0, 3.4 a 3.10), con el
ejemplo de demostración de 3.5 y 3.6: subtotal costo directo 38,200.00 y
adicionales 1,800.00 dan un total a pagar de 35,532.75 y una factura de
37,901.60. Datos ficticios."""
from datetime import date, timedelta
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase

from odoo.addons.al_construction_planner_subcontract.models.construction_contract_condition import (
    compute_cascade,
)

PHOTO = (b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAE'
         b'hQGAhKmMIQAAAABJRU5ErkJggg==')


class ContractTermsCommon(TransactionCase):
    """Obra de demostración con una partida de tabique (2,000 m² a 38.20) y
    una de sellado (100 unidades a 18.00), IGV de compras 18 % y el producto de
    anticipo."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.company = env.company
        cls.env['tier.definition'].search([('model', 'in', (
            'construction.resource.plan', 'construction.contract.settlement',
            'purchase.order'))]).active = False
        cls.unit = env.ref('uom.product_uom_unit')
        cls.m2 = env.ref('uom.product_uom_square_meter')
        cls.igv = env['account.tax'].create({
            'name': 'IGV compras 18 % (test)', 'amount': 18.0, 'amount_type': 'percent',
            'type_tax_use': 'purchase', 'company_id': cls.company.id})
        expense = env['account.account'].search([
            ('account_type', '=', 'expense'), ('company_ids', 'in', cls.company.id)], limit=1) \
            or env['account.account'].create({
                'name': 'Servicios de contratas (test)', 'code': '639100',
                'account_type': 'expense'})
        advance_account = env['account.account'].create({
            'name': 'Anticipos a contratistas (test)', 'code': '422900',
            'account_type': 'asset_current'})
        cls.advance_product = env['product.product'].create({
            'name': 'Anticipo a contratistas (test)', 'type': 'service',
            'purchase_ok': True, 'supplier_taxes_id': [Command.set(cls.igv.ids)],
            'property_account_expense_id': advance_account.id})
        cls.company.construction_advance_product_id = cls.advance_product
        cls.stage = env['construction.stage'].create({
            'name': 'Tabiquería (test)', 'code': 'creval_tab', 'sequence': 500})
        cls.project = env['project.project'].create({
            'name': 'OBR-01 Edificio de demostración (test)', 'is_construction_site': True})
        if not cls.project.account_id:
            cls.project._create_analytic_account()
        template = env['construction.level.template'].create({
            'name': 'Especialidad, sub-especialidad y partida (test)', 'line_ids': [
                (0, 0, {'sequence': 1, 'name': 'Especialidad', 'role': 'group'}),
                (0, 0, {'sequence': 2, 'name': 'Sub-especialidad', 'role': 'group'}),
                (0, 0, {'sequence': 3, 'name': 'Partida', 'role': 'space'})]})
        cls.project.construction_level_template_id = template
        levels = template.line_ids.sorted('sequence')
        Task = env['project.task']

        def node(name, level, parent=None):
            return Task.create({'name': name, 'project_id': cls.project.id,
                                'construction_level_line_id': levels[level].id,
                                'parent_id': parent.id if parent else False})
        cls.discipline = node('Arquitectura (test)', 0)
        cls.subdiscipline = node('Tabiquería (test)', 1, cls.discipline)
        cls.partida = node('04.01 Tabique drywall (test)', 2, cls.subdiscipline)
        cls.extra_task = node('04.02 Sellado de juntas (test)', 2, cls.subdiscipline)

        def service(name):
            return env['product.product'].create({
                'name': name, 'type': 'service', 'purchase_method': 'receive',
                'supplier_taxes_id': [Command.set(cls.igv.ids)],
                'property_account_expense_id': expense.id})
        Activity = env['construction.labor.activity']
        cls.act_wall = Activity.create({
            'code': 'TC-TAB', 'name': 'Tabique drywall (test)', 'stage': 'creval_tab',
            'default_price': 38.20, 'uom_id': cls.m2.id,
            'product_id': service('Tabique drywall (servicio, test)').id})
        cls.act_seal = Activity.create({
            'code': 'TC-SEL', 'name': 'Sellado de juntas (test)', 'stage': 'creval_tab',
            'default_price': 18.0, 'uom_id': cls.unit.id,
            'product_id': service('Sellado de juntas (servicio, test)').id})
        cls.contractor = env['res.partner'].create({'name': 'Tabiquería Demo SAC (test)'})
        cls.plan = env['construction.resource.plan'].create({'project_id': cls.project.id})
        env['construction.resource.plan.line'].create([
            {'plan_id': cls.plan.id, 'task_id': cls.partida.id, 'resource_type': 'contract',
             'activity_id': cls.act_wall.id, 'stage': 'creval_tab', 'qty_planned': 2000.0,
             'price_unit_planned': 38.20, 'product_uom_id': cls.m2.id},
            {'plan_id': cls.plan.id, 'task_id': cls.extra_task.id, 'resource_type': 'contract',
             'activity_id': cls.act_seal.id, 'stage': 'creval_tab', 'qty_planned': 100.0,
             'price_unit_planned': 18.0, 'product_uom_id': cls.unit.id},
        ])
        cls.plan.action_request_approval()
        assert cls.plan.state == 'approved', cls.plan.state
        cls.condition = env.ref('al_construction_planner_subcontract.contract_condition_construction')
        cls.deduction_type = env.ref(
            'al_construction_planner_subcontract.deduction_type_unfinished')

    # ------------------------------------------------------------------
    # Ayudas
    # ------------------------------------------------------------------
    def _assign(self, condition=None):
        wizard = self.env['construction.plan.contract.wizard'].with_context(
            default_plan_id=self.plan.id, construction_selection_project=True,
        ).create({'stage': 'creval_tab', 'partner_id': self.contractor.id,
                  'condition_id': (condition or self.condition).id,
                  'date_start': date(2026, 11, 2)})
        wizard.action_assign()
        order = self.env['purchase.order'].search([
            ('partner_id', '=', self.contractor.id),
            ('construction_project_id', '=', self.project.id)], order='id desc', limit=1)
        return wizard, order

    def _post(self, move, day):
        """Publica una factura de proveedor; con documentos (localización
        peruana) le pone su número."""
        move.invoice_date = day
        if 'l10n_latam_use_documents' in move._fields and move.l10n_latam_use_documents \
                and not move.l10n_latam_document_number:
            move.l10n_latam_document_number = 'F001-%06d' % move.id
        move.action_post()

    def _report(self, task, activity, qty, day):
        progress = self.env['construction.task.progress'].create({
            'task_id': task.id, 'activity_id': activity.id, 'date': day, 'qty': qty,
            'attachment_ids': [Command.create({'name': 'foto.jpg', 'datas': PHOTO})]})
        progress.action_validate()
        return progress

    def _deduction(self, order, amount, **vals):
        return self.env['construction.contract.deduction'].create(dict({
            'purchase_order_id': order.id, 'type_id': self.deduction_type.id,
            'description': 'Remate de tabique hecho por personal propio', 'amount': amount,
            'date': date(2026, 11, 4),
            'attachment_ids': [Command.create({'name': 'acta.pdf', 'datas': PHOTO})],
        }, **vals))

    def _scenario(self):
        """Orden con el ejemplo de 3.5: adelanto publicado, 1,000 m² de
        tabique, el adicional de 100 sellos y un deductivo de 650.00."""
        _wizard, order = self._assign()
        order.order_line.filtered(
            lambda l: l.construction_activity_id == self.act_seal).construction_is_additional = True
        order.button_confirm()
        action = order.action_construction_register_advance()
        advance = self.env['account.move'].browse(action['res_id'])
        self._post(advance, date(2026, 11, 2))
        self._report(self.partida, self.act_wall, 1000.0, date(2026, 11, 4))
        self._report(self.extra_task, self.act_seal, 100.0, date(2026, 11, 4))
        self._deduction(order, 650.0)
        settlements = self.env['construction.contract.settlement']._prepare_terms_settlements(
            today=date(2026, 11, 20))
        return order, advance, settlements



@tagged('post_install', '-at_install')
class TestContractTerms(ContractTermsCommon):

    # ------------------------------------------------------------------
    # 3.4 · Condiciones
    # ------------------------------------------------------------------
    def test_cascade_example(self):
        rows, totals = compute_cascade(self.condition, self.company.currency_id, 38200.0, 1800.0,
                                       650.0)
        self.assertEqual(totals['adjustments'], 800.0)
        self.assertEqual(totals['subtotal'], 40150.0)
        self.assertEqual(totals['tax'], 7227.0)
        self.assertEqual(totals['total'], 47377.0)
        self.assertEqual(totals['advance'], 9475.40)
        self.assertEqual(totals['retention'], 2368.85)
        self.assertEqual(totals['to_pay'], 35532.75)
        by_name = {line.name: rows[line.id] for line in self.condition.scheme_line_ids}
        self.assertEqual(by_name['Gastos generales y utilidades'], 2000.0)
        self.assertEqual(by_name['Descuento'], -1200.0)
        self.assertEqual(by_name['Deductivos'], -650.0)

    def test_other_conditions_without_code(self):
        """Otros porcentajes, otra base del fondo y otro orden de conceptos:
        la valorización calcula con ellos sin cambiar código (3.16)."""
        condition = self.env['construction.contract.condition'].create({
            'name': 'Sin adelanto, fondo sobre el subtotal (test)', 'advance_pct': 0.0,
            'guarantee_pct': 10.0, 'guarantee_base': 'subtotal',
            'scheme_line_ids': [
                Command.create({'sequence': 5, 'name': 'Descuento sobre costo directo',
                                'kind': 'price_adjustment', 'base': 'direct', 'percent': 7.5,
                                'sign': 'subtract', 'invoice_mode': 'service_line'}),
                Command.create({'sequence': 1, 'name': 'IGV', 'kind': 'tax', 'base': 'subtotal',
                                'percent': 18.0, 'invoice_mode': 'tax'}),
                Command.create({'sequence': 9, 'name': 'Fondo', 'kind': 'retention',
                                'base': 'total', 'sign': 'subtract',
                                'invoice_mode': 'installment'}),
            ]})
        _rows, totals = compute_cascade(condition, self.company.currency_id, 1000.0, 200.0, 0.0)
        self.assertEqual(totals['subtotal'], 1125.0)
        self.assertEqual(totals['total'], 1327.50)
        self.assertEqual(totals['retention'], 112.50)
        self.assertEqual(totals['to_pay'], 1215.0)
        with self.assertRaises(ValidationError):
            condition.scheme_line_ids[0].invoice_mode = 'installment'

    def test_assign_copies_terms(self):
        wizard, order = self._assign()
        # (76,400 + 1,800) × (1 + 5 % − 3 %) × 1.18 con el esquema de ejemplo.
        self.assertEqual(wizard.terms_total, 94121.52)
        self.assertEqual(wizard.terms_advance, 18824.30)
        self.assertEqual(wizard.terms_guarantee, 4706.08)
        terms = order.construction_terms_id
        self.assertTrue(order.construction_uses_terms)
        self.assertEqual(terms.template_id, self.condition)
        self.assertNotEqual(terms, self.condition)
        self.assertEqual(len(terms.scheme_line_ids), 6)
        self.assertEqual(order.construction_requirement_ids.requirement_id,
                         self.condition.requirement_ids)
        # Una línea por actividad y partida, con su partida y sin la retención
        # de la tarifa.
        self.assertEqual(order.order_line.construction_task_id, self.partida | self.extra_task)
        self.assertEqual(set(order.order_line.mapped('construction_retention_pct')), {0.0})
        self.assertEqual(order.order_line.tax_ids, self.igv)
        # Lo pactado se ajusta en la orden; la plantilla no cambia.
        order.construction_advance_pct = 30.0
        self.assertEqual(self.condition.advance_pct, 20.0)
        order.button_confirm()
        self.assertEqual(order.construction_amount_approved, order.amount_total)
        buyer = new_test_user(self.env, 'compras_contrata', groups='purchase.group_purchase_user')
        with self.assertRaises(UserError):
            terms.with_user(buyer).write({'guarantee_pct': 1.0})

    # ------------------------------------------------------------------
    # 3.5 a 3.8 · Valorización, adelanto, deductivo y fondo
    # ------------------------------------------------------------------
    def test_valuation_invoice_and_fund(self):
        order, advance, settlements = self._scenario()
        # Base del adelanto: el subtotal contractual sin IGV (con los ajustes de
        # precio), 79,764.00 × 20 %.
        self.assertEqual(advance.amount_untaxed, 15952.80)
        self.assertEqual(order.construction_advance_granted, 18824.30)
        self.assertEqual(len(settlements), 1)
        settlement = settlements
        self.assertTrue(settlement.uses_terms)
        self.assertEqual(settlement.purchase_order_id, order)
        self.assertEqual(settlement.number, 1)
        self.assertTrue(settlement.title.startswith('Valorizado 01'))
        self.assertEqual(settlement.amount_direct, 38200.0)
        self.assertEqual(settlement.amount_additional, 1800.0)
        self.assertEqual(settlement.amount_subtotal, 40150.0)
        self.assertEqual(settlement.amount_tax, 7227.0)
        self.assertEqual(settlement.amount_total, 47377.0)
        self.assertEqual(settlement.amount_advance, 9475.40)
        self.assertEqual(settlement.amount_retention, 2368.85)
        self.assertEqual(settlement.amount_to_pay, 35532.75)
        self.assertEqual(settlement.amount_net, 35532.75)
        self.assertEqual(settlement.deduction_ids.state, 'in_valuation')
        summary = {row.key: row for row in settlement.summary_ids}
        self.assertEqual(summary['to_pay'].amount_current, 35532.75)
        self.assertEqual(summary['direct'].amount_contract, 76400.0)
        self.assertEqual(summary['direct'].amount_balance, 38200.0)
        self.assertEqual(settlement.summary_ids.sorted('sequence')[0].key, 'direct')
        self.assertEqual(settlement.summary_ids.sorted('sequence')[-1].key, 'to_pay')
        self.assertAlmostEqual(settlement.line_ids.filtered(
            lambda l: l.task_id == self.partida).pct_accumulated, 0.5)
        # Presentar, validar y aprobar (sin reglas de niveles: se aprueba).
        settlement.action_submit()
        self.assertEqual(settlement.submitted_by_id, self.env.user)
        settlement.action_validate()
        self.assertEqual(settlement.state, 'approved')
        self.assertEqual(settlement.deduction_ids.state, 'applied')
        wall_line = order.order_line.filtered(lambda l: l.construction_task_id == self.partida)
        self.assertEqual(wall_line.qty_received, 1000.0)
        invoice = settlement.invoice_id
        self.assertEqual(invoice.amount_untaxed, 32120.0)
        self.assertEqual(invoice.amount_tax, 5781.60)
        self.assertEqual(invoice.amount_total, 37901.60)
        regularization = invoice.invoice_line_ids.filtered(
            lambda l: l.product_id == self.advance_product)
        self.assertEqual(regularization.price_subtotal, -8030.0)
        deduction_line = invoice.invoice_line_ids.filtered(lambda l: 'Deductivo' in (l.name or ''))
        self.assertEqual(deduction_line.price_subtotal, -650.0)
        services = invoice.invoice_line_ids - regularization - deduction_line
        self.assertEqual(sum(services.mapped('price_subtotal')), 40800.0)
        # Cuotas: neto el día de pago y el fondo con su vencimiento.
        terms = invoice.line_ids.filtered(lambda l: l.display_type == 'payment_term')
        self.assertEqual(len(terms), 2)
        fund_line = terms.filtered(lambda l: l.date_maturity == invoice.construction_guarantee_date)
        self.assertEqual(-fund_line.amount_currency, 2368.85)
        self.assertEqual(-(terms - fund_line).amount_currency, 35532.75)
        self.assertEqual((terms - fund_line).date_maturity, settlement.payment_date)
        self._post(invoice, date(2026, 11, 7))
        fund = order.construction_guarantee_fund_ids
        self.assertEqual(fund.amount, 2368.85)
        self.assertEqual(fund.move_line_id, fund_line)
        self.assertEqual(fund.state, 'pending')
        self.assertEqual(order.construction_advance_amortized, 9475.40)
        self.assertAlmostEqual(order.construction_advance_to_amortize, 9348.90)
        self.assertEqual(order.construction_guarantee_retained, 2368.85)
        # Un deductivo aplicado no se edita; se corrige con otro de signo
        # contrario.
        deduction = settlement.deduction_ids
        with self.assertRaises(UserError):
            deduction.amount = 600.0
        reversal = self.env['construction.contract.deduction'].browse(
            deduction.action_reverse()['res_id'])
        self.assertEqual(reversal.signed_amount, -650.0)
        self.assertEqual(reversal.state, 'pending')

    def test_amortization_needs_posted_advance(self):
        _wizard, order = self._assign()
        order.button_confirm()
        self._report(self.partida, self.act_wall, 100.0, date(2026, 11, 4))
        settlement = self.env['construction.contract.settlement']._prepare_terms_settlements(
            today=date(2026, 11, 20))
        # Sin factura de adelanto publicada no se amortiza.
        self.assertEqual(settlement.amount_advance, 0.0)
        self.assertEqual(settlement.amount_direct, 3820.0)

    def test_one_open_valuation_per_order(self):
        order, _advance, settlement = self._scenario()
        with self.assertRaises(ValidationError):
            self.env['construction.contract.settlement'].create({
                'purchase_order_id': order.id, 'period_start': date(2026, 11, 26)})
        # Un deductivo solo entra a una valorización de su misma orden.
        self.assertEqual(settlement.deduction_ids.purchase_order_id, order)

    def test_deduction_needs_support(self):
        _wizard, order = self._assign()
        order.button_confirm()
        with self.assertRaises(ValidationError):
            self.env['construction.contract.deduction'].create({
                'purchase_order_id': order.id, 'type_id': self.deduction_type.id,
                'description': 'Sin sustento', 'amount': 10.0})
        with self.assertRaises(ValidationError):
            self._deduction(order, 0.0)
        deduction = self._deduction(order, 80.0)
        self.assertTrue(deduction.name.endswith('-DED-0001'))

    # ------------------------------------------------------------------
    # 3.16 · Sin condiciones ni porcentajes, igual que la liquidación de hoy
    # ------------------------------------------------------------------
    def test_zero_terms_match_weekly_settlement(self):
        zero = self.env['construction.contract.condition'].create({
            'name': 'Sin adelanto ni fondo (test)', 'line_detail': 'activity',
            'scheme_line_ids': [Command.create({
                'name': 'IGV', 'kind': 'tax', 'base': 'subtotal', 'percent': 18.0,
                'invoice_mode': 'tax'})]})
        _wizard, order = self._assign(zero)
        order.button_confirm()
        self._report(self.partida, self.act_wall, 250.0, date(2026, 11, 4))
        settlement = self.env['construction.contract.settlement']._prepare_terms_settlements(
            today=date(2026, 11, 20))
        settlement.action_submit()
        settlement.action_validate()
        self.assertEqual(settlement.invoice_id.amount_untaxed, 250.0 * 38.20)
        self.assertEqual(settlement.invoice_id.amount_total, 250.0 * 38.20 * 1.18)
        terms = settlement.invoice_id.line_ids.filtered(lambda l: l.display_type == 'payment_term')
        self.assertEqual(len(terms), 1)
        self.assertEqual(order.order_line.filtered(
            lambda l: l.construction_activity_id == self.act_wall).qty_received, 250.0)

    # ------------------------------------------------------------------
    # 3.10 · Periodicidad
    # ------------------------------------------------------------------
    def test_periods(self):
        _wizard, order = self._assign()
        Settlement = self.env['construction.contract.settlement']
        terms = order.construction_terms_id
        terms.frequency = 'biweekly'
        self.assertEqual(Settlement._terms_period_start(order, date(2026, 11, 20)),
                         date(2026, 11, 16))
        self.assertEqual(Settlement._terms_period_end(order, date(2026, 11, 16)),
                         date(2026, 11, 30))
        self.assertEqual(Settlement._terms_period_end(order, date(2026, 11, 1)),
                         date(2026, 11, 15))
        terms.write({'frequency': 'monthly', 'monthly_cutoff': 'day', 'cutoff_day': 25})
        self.assertEqual(Settlement._terms_period_start(order, date(2026, 11, 20)),
                         date(2026, 10, 26))
        self.assertEqual(Settlement._terms_period_end(order, date(2026, 10, 26)),
                         date(2026, 11, 25))
        terms.monthly_cutoff = 'month_end'
        self.assertEqual(Settlement._terms_period_end(order, date(2026, 2, 1)), date(2026, 2, 28))
        terms.write({'frequency': 'weekly', 'cutoff_weekday': '3'})  # jueves
        self.assertEqual(Settlement._terms_period_end(order, date(2026, 11, 6)),
                         date(2026, 11, 12))
        self.assertEqual(Settlement._terms_period_start(order, date(2026, 11, 13)),
                         date(2026, 11, 13))
        # El periodo siguiente empieza al día siguiente del anterior.
        order.button_confirm()
        self._report(self.partida, self.act_wall, 10.0, date(2026, 11, 10))
        first = Settlement._prepare_terms_settlements(today=date(2026, 11, 13))
        self.assertEqual((first.period_start, first.period_end),
                         (date(2026, 11, 6), date(2026, 11, 12)))
        self.assertEqual(first.payment_date.weekday(), int(self.project.construction_payment_day))
        first.action_submit()
        first.action_validate()
        self.assertEqual(Settlement._terms_next_start(order), date(2026, 11, 13))
        # Al término: no hay valorizaciones periódicas.
        terms.frequency = 'end'
        self._report(self.partida, self.act_wall, 10.0, date(2026, 11, 16))
        self.assertFalse(Settlement._prepare_terms_settlements(today=date(2026, 12, 31)))


@tagged('post_install', '-at_install')
class TestContractLiquidation(ContractTermsCommon):
    """3.11: la liquidación amortiza el saldo del adelanto y «Cerrar orden»
    baja cada línea a lo recibido, libera el saldo del plan y bloquea la
    orden."""

    def _approve_and_post(self, settlement, day):
        settlement.action_submit()
        settlement.action_validate()
        self.assertEqual(settlement.state, 'approved')
        self._post(settlement.invoice_id, day)
        return settlement.invoice_id

    def test_liquidation_and_close(self):
        order, _advance, first = self._scenario()
        self._approve_and_post(first, date(2026, 11, 7))
        self._report(self.partida, self.act_wall, 500.0, date(2026, 11, 24))
        liquidation = self.env['construction.contract.settlement'].browse(
            order.action_construction_liquidate()['res_id'])
        self.assertEqual(liquidation.settlement_type, 'settlement')
        self.assertTrue(liquidation.title.startswith('Liquidación'))
        wall = liquidation.line_ids.filtered(lambda l: l.task_id == self.partida)
        self.assertEqual(wall.qty_previous, 1000.0)
        self.assertEqual(wall.qty_final, 1500.0)
        # La cantidad final se reduce con motivo, nunca se aumenta.
        with self.assertRaises(UserError):
            wall.qty_final = 1600.0
        with self.assertRaises(UserError):
            wall.qty_final = 1400.0
        wall.write({'qty_final': 1400.0, 'final_reason': 'Medición final en obra'})
        self.assertEqual(wall.qty_settle, 400.0)
        self.assertEqual(wall.qty_released, 600.0)
        self.assertAlmostEqual(liquidation.amount_direct, 15280.0)
        # Amortiza todo el saldo del adelanto.
        self.assertAlmostEqual(liquidation.amount_advance, 9348.90)
        self._approve_and_post(liquidation, date(2026, 11, 28))
        self.assertFalse(liquidation.can_close_order)  # falta la carta de no deuda
        with self.assertRaises(UserError):
            liquidation.action_close_order()
        liquidation.order_document_ids.attachment_ids = [Command.create(
            {'name': 'no_deuda.pdf', 'datas': PHOTO})]
        self.assertTrue(liquidation.can_close_order)
        liquidation.action_close_order()
        self.assertTrue(order.construction_closed)
        self.assertTrue(order.locked)
        wall_line = order.order_line.filtered(lambda l: l.construction_task_id == self.partida)
        self.assertEqual(wall_line.product_qty, 1400.0)
        plan_line = self.plan.line_ids.filtered(lambda l: l.task_id == self.partida)
        self.assertEqual(plan_line.qty_requested, 1400.0)
        self.assertEqual(order.construction_advance_to_amortize, 0.0)
        # Fondo «desde la liquidación»: vencimiento = liquidación + 365 días.
        due = liquidation.settlement_date + timedelta(days=365)
        self.assertEqual(set(order.construction_guarantee_fund_ids.mapped('date_maturity')),
                         {due})


@tagged('post_install', '-at_install')
class TestContractOpening(ContractTermsCommon):
    """3.14: la carga inicial crea la orden con su valorización de apertura y
    la siguiente valorización parte de ella."""

    def _book(self):
        import base64
        import io

        import openpyxl
        from odoo.addons.al_construction_planner_subcontract.wizards.opening_import_wizard import (
            SHEETS,
        )
        book = openpyxl.Workbook()
        book.remove(book.active)
        rows = {
            'ORDENES': [['OC-ANT-01', self.contractor.name, self.project.name, self.condition.name,
                         'Tabiquería', 20, 5, 0, 0, 0, 10000.0, 3000.0, 4, date(2026, 11, 5)]],
            'LINEAS': [['OC-ANT-01', self.partida.name, 'TC-TAB', 2000, 38.20, 600]],
            'FONDOS': [['OC-ANT-01', 1200.0, date(2027, 6, 30)]],
        }
        for sheet, columns in SHEETS.items():
            ws = book.create_sheet(sheet)
            ws.append([label for _key, label, _required in columns])
            for row in rows[sheet]:
                ws.append(row)
        buffer = io.BytesIO()
        book.save(buffer)
        return base64.b64encode(buffer.getvalue())

    def test_opening_load(self):
        wizard = self.env['construction.contract.opening.wizard'].create({'file': self._book()})
        wizard.action_import()
        self.assertIn('Órdenes creadas', wizard.log)
        self.assertNotIn('errores', wizard.log)
        order = self.env['purchase.order'].search([('partner_ref', '=', 'OC-ANT-01')])
        self.assertEqual(order.state, 'purchase')
        self.assertTrue(order.construction_uses_terms)
        opening = order.construction_settlement_ids
        self.assertEqual(opening.settlement_type, 'opening')
        self.assertEqual(opening.state, 'approved')
        self.assertFalse(opening.invoice_id)
        self.assertEqual(opening.amount_direct, 600 * 38.20)
        self.assertEqual(order.construction_advance_to_amortize, 7000.0)
        self.assertEqual(order.construction_guarantee_retained, 1200.0)
        self.assertEqual(order.order_line.qty_received, 600.0)
        # La siguiente valorización empieza el día siguiente al corte y su
        # anterior es lo de la apertura.
        Settlement = self.env['construction.contract.settlement']
        self.assertEqual(Settlement._terms_next_start(order), date(2026, 11, 6))
        self._report(self.partida, self.act_wall, 100.0, date(2026, 11, 10))
        settlement = Settlement._prepare_terms_settlements(today=date(2026, 12, 31))
        self.assertEqual(settlement.number, 5)
        self.assertEqual(settlement.line_ids.qty_previous, 600.0)
        self.assertEqual(settlement.line_ids.qty_accumulated, 700.0)


@tagged('post_install', '-at_install')
class TestContractReports(ContractTermsCommon):
    """3.12 y 3.13: el valorizado impreso con sus casillas de firma, el resumen
    de valorizaciones y el despacho semanal."""

    def test_printed_valuation_and_summary(self):
        order, _advance, settlement = self._scenario()
        order.construction_specialty = 'Tabiquería'
        settlement.action_submit()
        settlement.action_validate()
        boxes = settlement._construction_sign_boxes()
        self.assertEqual([box['role'] for box in boxes][:2], ['Elaboró', 'Validó'])
        self.assertEqual(boxes[0]['name'], self.env.user.name)
        self.assertEqual(boxes[-1]['role'], 'Conformidad del contratista')
        self.assertEqual(boxes[-1]['name'], self.contractor.name)
        html = self.env['ir.actions.report']._render_qweb_html(
            'al_construction_planner_subcontract.report_contract_valuation',
            settlement.ids)[0].decode()
        self.assertIn('Valorizado 01 - Tabiquería', html)
        self.assertIn('pe-doc-sign-box', html)
        self.assertIn('Conformidad del contratista', html)
        self.assertIn('Adicionales', html)
        self.assertIn('35,532.75', html)
        # Resumen de valorizaciones (con IGV).
        row = self.env['construction.contract.summary.report'].search(
            [('order_id', '=', order.id)])
        self.assertAlmostEqual(row.amount_valued, 47377.0)
        self.assertAlmostEqual(row.amount_contract, order.amount_total)
        self.assertAlmostEqual(row.amount_deductions, 650.0)
        self.assertAlmostEqual(row.amount_to_pay, 35532.75)
        self.assertAlmostEqual(row.progress_pct, 38200.0 / 76400.0)
        self.assertEqual(row.next_payment_date, settlement.payment_date)
        html = self.env['ir.actions.report']._render_qweb_html(
            'al_construction_planner_subcontract.report_contract_summary', row.ids)[0].decode()
        self.assertIn('Resumen de valorizaciones de contratas', html)
        # Despacho semanal: aprobadas con pago en la semana en curso.
        Settlement = self.env['construction.contract.settlement']
        Summary = type(self.env['construction.contract.summary.report'])
        day = settlement.payment_date
        with patch.object(Summary, '_week_bounds', lambda self: (day, day)):
            self.assertIn(settlement, Settlement.search([('payment_this_week', '=', True)]))
            self.assertNotIn(settlement, Settlement.search([('payment_this_week', '=', False)]))
            self.assertIn(row, row.search([('payment_this_week', '=', True)]))
