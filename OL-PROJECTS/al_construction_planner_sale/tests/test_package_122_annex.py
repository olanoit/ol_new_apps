# -*- coding: utf-8 -*-
"""Paquete 1.22, anexo: dos decisiones sobre la valorización por hitos.

D1. El último céntimo del descuento: la valorización que lleva una partida a
su 100 % toma el total de la línea de la orden menos lo ya valorizado.

D2. Partida con dos líneas en la orden: cuando un adicional cambia una
tipología que ya existía, cada hito se parte entre la línea original y la del
adicional, y las dos avanzan con el mismo avance físico.

Datos ficticios."""
import base64
from datetime import date

from odoo import Command
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase

PDF = base64.b64encode(b'%PDF-1.4 conformidad')


@tagged('post_install', '-at_install')
class TestPackage122Annex(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.revenue = new_test_user(
            cls.env, 'plan_ingresos_122', name='Ingresos (test 1.22)',
            groups='al_construction_planner.group_planner_revenue,'
                   'al_construction_planner.group_planner_manager,'
                   'sales_team.group_sale_salesman_all_leads')
        cls.customer = cls.env['res.partner'].create({'name': 'Inmobiliaria Los Olmos (test)'})
        cls.product = cls.env['product.product'].create({
            'name': 'Partida de obra (test 1.22)', 'type': 'service',
            'invoice_policy': 'delivery'})
        cls.project = cls.env['project.project'].create({
            'name': 'Edificio Los Olmos (test 1.22)', 'is_construction_site': True})
        cls.typology = cls.env['construction.typology'].create({
            'project_id': cls.project.id, 'code': 'C01', 'name': 'Cocina C01'})
        Task = cls.env['project.task']
        floor = Task.create({'name': 'Piso 01', 'project_id': cls.project.id,
                             'construction_level': 'floor'})
        cls.units = Task.create([{
            'name': 'Dpto 1%02d' % number, 'project_id': cls.project.id,
            'construction_level': 'apartment', 'parent_id': floor.id,
        } for number in range(1, 11)])
        cls.spaces = Task.create([{
            'name': 'Cocina', 'project_id': cls.project.id, 'construction_level': 'space',
            'parent_id': unit.id, 'construction_typology_id': cls.typology.id,
        } for unit in cls.units])
        cls.single = cls.env['construction.milestone.template'].create({
            'name': 'Entrega 100 (test 1.22)', 'line_ids': [
                Command.create({'sequence': 1, 'name': 'Entrega', 'pct': 100,
                                'trigger': 'manual'})]})
        cls.two_steps = cls.env['construction.milestone.template'].create({
            'name': 'Entrega 80/20 (test 1.22)', 'line_ids': [
                Command.create({'sequence': 1, 'name': 'Entrega', 'pct': 80,
                                'trigger': 'manual'}),
                Command.create({'sequence': 2, 'name': 'Conformidad', 'pct': 20,
                                'trigger': 'manual'})]})

    # ------------------------------------------------------------------
    # Ayudas
    # ------------------------------------------------------------------
    def _order(self, price, partida='Cocinas'):
        order = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'order_line': [Command.create({
                'product_id': self.product.id, 'name': partida or 'Cocinas', 'product_uom_qty': 1,
                'price_unit': price, 'tax_ids': [Command.clear()],
                'construction_partida': partida})]})
        order.action_confirm()
        return order

    def _add_line(self, order, name, price, partida='Cocinas'):
        """La línea que «Pasar el resumen» agrega con un adicional: misma
        partida, solo la diferencia."""
        return self.env['sale.order.line'].create({
            'order_id': order.id, 'product_id': self.product.id, 'name': name,
            'product_uom_qty': 1, 'price_unit': price, 'tax_ids': [Command.clear()],
            'construction_partida': partida})

    def _contract(self, order, unit_price, template=None, factor=1.0):
        contract = self.env['construction.contract'].create({
            'name': 'Cocinas (test 1.22)', 'project_id': self.project.id,
            'partner_id': self.customer.id, 'sale_order_id': order.id,
            'milestone_template_id': (template or self.single).id, 'discount_factor': factor,
            'price_line_ids': [Command.create({
                'typology_id': self.typology.id, 'unit_price': unit_price,
                'sale_line_id': order.order_line[:1].id})],
        })
        contract = contract.with_user(self.revenue)
        contract.action_generate_milestones()
        contract.action_activate()
        return contract

    def _deliver(self, contract, units):
        """Avance físico: las unidades entregadas llevan sus hitos al 100 %. Se
        escribe en una sola parte de cada hito, como haría el usuario."""
        milestones = contract.milestone_ids.filtered(lambda m: m.task_id in units)
        seen = set()
        for milestone in milestones.sorted('id'):
            key = milestone._construction_part_key()
            if key not in seen:
                seen.add(key)
                milestone.manual_pct = 100

    def _valuate(self, contract):
        """Prepara la valorización por hitos, la envía y registra la
        conformidad del cliente por todo lo entregado."""
        valuation = self.env['construction.valuation'].with_user(self.revenue).browse(
            contract.action_prepare_valuation()['res_id'])
        # El envío al cliente (PDF incluido) ya se prueba en la suite: aquí el
        # estado lo escribe el sistema, como en la acción.
        valuation.sudo().write({'state': 'sent'})
        valuation._action_confirm({
            'confirm_date': date(2026, 11, 17), 'confirm_name': 'Ing. Marta Salas',
            'confirm_role': 'Residente',
            'confirm_attachment_ids': [Command.create({'name': 'ok.pdf', 'datas': PDF})],
        }, {line: line.amount_delivered for line in valuation.line_ids})
        self.assertEqual(valuation.state, 'confirmed')
        return valuation

    def _line(self, valuation, sale_line):
        return valuation.line_ids.filtered(lambda l: l.sale_line_id == sale_line)

    def _valued(self, contract, sale_line):
        lines = self.env['construction.valuation.line'].search([
            ('valuation_id.contract_id', '=', contract.id),
            ('valuation_id.state', 'in', ('confirmed', 'invoiced')),
            ('sale_line_id', '=', sale_line.id)])
        return sum(lines.mapped('amount_confirmed'))

    # ------------------------------------------------------------------
    # D1: el último céntimo del descuento
    # ------------------------------------------------------------------
    def _check_last_cent(self, factor):
        """10,000 de descuento sobre 245,818.40: la orden lleva 235,818.40 y
        los hitos, con el factor de 6 decimales, unos céntimos de más o de
        menos."""
        order = self._order(235818.40)
        sale_line = order.order_line
        contract = self._contract(order, 24581.84, template=self.two_steps, factor=factor)
        self.assertEqual(len(contract.milestone_ids), 20, '10 unidades × 2 hitos')
        currency = contract.currency_id
        self.assertTrue(
            currency.compare_amounts(contract.amount_total, sale_line.price_subtotal),
            'el caso sirve si los hitos no suman lo mismo que la orden')
        self._deliver(contract, self.units[:5])
        first = self._valuate(contract)
        self.assertAlmostEqual(self._line(first, sale_line).progress_confirmed, 0.5, places=4)
        self._deliver(contract, self.units)
        last = self._valuate(contract)
        self.assertEqual(
            currency.compare_amounts(self._valued(contract, sale_line), sale_line.price_subtotal),
            0, 'las valorizaciones de la partida suman su subtotal con descuento en la orden')
        self.assertAlmostEqual(self._line(last, sale_line).progress_confirmed, 1.0, places=6)
        self.assertEqual(
            currency.compare_amounts(first.amount_confirmed + last.amount_confirmed,
                                     order.amount_untaxed), 0,
            'contrato valorizado y orden de venta dan el mismo total')

    def test_d1_last_cent_factor_rounded_down(self):
        # Los hitos suman menos que la orden: sin D1 la partida no cerraba.
        self._check_last_cent(0.959319)

    def test_d1_last_cent_factor_rounded(self):
        # El factor que da la hoja de venta: los hitos suman de más.
        self._check_last_cent(round(1 - 10000 / 245818.40, 6))

    def test_d1_does_not_close_a_real_difference(self):
        """Unos hitos que no cubren toda la línea no son redondeo: al 100 % la
        partida se queda en lo que suman, como antes."""
        order = self._order(60000.0)
        contract = self._contract(order, 5000.0)
        self._deliver(contract, self.units)
        valuation = self._valuate(contract)
        self.assertEqual(valuation.line_ids.amount_confirmed, 50000.0)

    # ------------------------------------------------------------------
    # D2: partida con dos líneas en la orden
    # ------------------------------------------------------------------
    def _additional(self, contract, order, unit_price, name='Adicional N1 · Cocinas'):
        """El adicional cambia el precio de la tipología que ya existía: una
        línea nueva en la orden con la diferencia y los hitos regenerados,
        como hace el envío de la hoja."""
        old = contract.price_line_ids.unit_price
        line = self._add_line(order, name, (unit_price - old) * len(self.units))
        contract.price_line_ids.unit_price = unit_price
        contract.action_generate_milestones()
        return line

    def test_d2_example_two_lines_advance_together(self):
        order = self._order(50000.0)
        original = order.order_line
        contract = self._contract(order, 5000.0)
        self.assertEqual(contract.milestone_ids.mapped('sale_line_id'), original)
        additional = self._additional(contract, order, 5600.0)
        on_original = contract.milestone_ids.filtered(lambda m: m.sale_line_id == original)
        on_additional = contract.milestone_ids.filtered(lambda m: m.sale_line_id == additional)
        self.assertEqual(len(on_original), 10)
        self.assertEqual(len(on_additional), 10)
        self.assertEqual(set(on_original.mapped('amount')), {5000.0}, 'el monto original')
        self.assertEqual(set(on_additional.mapped('amount')), {600.0}, 'la diferencia')
        self.assertEqual(contract.amount_total, 56000.0)

        # 5 departamentos entregados: 50 % en cada línea.
        self._deliver(contract, self.units[:5])
        delivered = contract.milestone_ids.filtered(lambda m: m.task_id in self.units[:5])
        self.assertEqual(set(delivered.mapped('progress_pct')), {100.0},
                         'las dos partes del hito llevan el mismo avance')
        first = self._valuate(contract)
        self.assertEqual(self._line(first, original).amount_confirmed, 25000.0)
        self.assertEqual(self._line(first, additional).amount_confirmed, 3000.0)
        self.assertAlmostEqual(self._line(first, original).progress_confirmed, 0.5)
        self.assertAlmostEqual(self._line(first, additional).progress_confirmed, 0.5)

        # Los 10: 100 % en cada una, y ninguna pasa de su precio.
        self._deliver(contract, self.units)
        last = self._valuate(contract)
        self.assertAlmostEqual(self._line(last, original).progress_confirmed, 1.0)
        self.assertAlmostEqual(self._line(last, additional).progress_confirmed, 1.0)
        self.assertEqual(self._valued(contract, original), 50000.0)
        self.assertEqual(self._valued(contract, additional), 6000.0)
        self.assertEqual(set(contract.milestone_ids.mapped('billed_pct')), {100.0})

    def test_d2_additional_after_a_valuation(self):
        """El adicional llega con parte de la partida ya valorizada: los hitos
        cobrados no se tocan y su diferencia se valoriza en la siguiente."""
        order = self._order(50000.0)
        original = order.order_line
        contract = self._contract(order, 5000.0)
        self._deliver(contract, self.units[:5])
        self._valuate(contract)
        billed = contract.milestone_ids.filtered('billed_pct')
        self.assertEqual(len(billed), 5)
        additional = self._additional(contract, order, 5600.0)
        self.assertTrue(billed.exists() == billed and set(billed.mapped('amount')) == {5000.0})
        parts = contract.milestone_ids.filtered(lambda m: m.sale_line_id == additional)
        self.assertEqual(len(parts), 10)
        self.assertEqual(set(parts.filtered(
            lambda m: m.task_id in self.units[:5]).mapped('progress_pct')), {100.0},
            'la parte nueva nace con el avance de su hito')
        catch_up = self._valuate(contract)
        self.assertEqual(catch_up.line_ids.sale_line_id, additional)
        self.assertEqual(catch_up.line_ids.amount_confirmed, 3000.0)
        self._deliver(contract, self.units)
        last = self._valuate(contract)
        self.assertEqual(self._line(last, original).amount_confirmed, 25000.0)
        self.assertEqual(self._line(last, additional).amount_confirmed, 3000.0)
        self.assertEqual(self._valued(contract, original), 50000.0)
        self.assertEqual(self._valued(contract, additional), 6000.0)

    def test_d2_deductive_splits_in_negative(self):
        order = self._order(50000.0)
        original = order.order_line
        contract = self._contract(order, 5000.0)
        deductive = self._additional(contract, order, 4500.0, name='Deductivo N1 · Cocinas')
        self.assertEqual(deductive.price_subtotal, -5000.0)
        parts = contract.milestone_ids.filtered(lambda m: m.sale_line_id == deductive)
        self.assertEqual(set(parts.mapped('amount')), {-500.0})
        self.assertEqual(set(contract.milestone_ids.filtered(
            lambda m: m.sale_line_id == original).mapped('amount')), {5000.0})
        self._deliver(contract, self.units[:5])
        first = self._valuate(contract)
        self.assertEqual(self._line(first, original).amount_confirmed, 25000.0)
        self.assertEqual(self._line(first, deductive).amount_confirmed, -2500.0)
        self.assertAlmostEqual(self._line(first, deductive).progress_confirmed, 0.5)
        self._deliver(contract, self.units)
        last = self._valuate(contract)
        self.assertAlmostEqual(self._line(last, original).progress_confirmed, 1.0)
        self.assertAlmostEqual(self._line(last, deductive).progress_confirmed, 1.0)
        self.assertEqual(self._valued(contract, original), 50000.0)
        self.assertEqual(self._valued(contract, deductive), -5000.0)

    def test_d2_deductive_removes_a_unit(self):
        """El deductivo quita la cocina de un departamento: su hito original
        queda y la línea del deductivo lleva el mismo monto en negativo."""
        order = self._order(50000.0)
        original = order.order_line
        contract = self._contract(order, 5000.0)
        deductive = self._add_line(order, 'Deductivo N1 · Cocinas', -5000.0)
        self.spaces[-1].construction_typology_id = False
        contract.action_generate_milestones()
        removed = contract.milestone_ids.filtered(lambda m: m.task_id == self.units[-1])
        self.assertEqual(sorted(removed.mapped('amount')), [-5000.0, 5000.0])
        self.assertEqual(removed.filtered(lambda m: m.amount < 0).sale_line_id, deductive)
        self.assertEqual(len(contract.milestone_ids), 11)
        self.assertEqual(contract.amount_total, 45000.0)
        self._deliver(contract, self.units)
        self._valuate(contract)
        self.assertEqual(self._valued(contract, original), 50000.0)
        self.assertEqual(self._valued(contract, deductive), -5000.0)

    def test_d2_new_typology_goes_whole_to_the_additional(self):
        order = self._order(50000.0)
        original = order.order_line
        contract = self._contract(order, 5000.0)
        additional = self._add_line(order, 'Adicional N1 · Cocinas', 14000.0)
        island = self.env['construction.typology'].create({
            'project_id': self.project.id, 'code': 'C02', 'name': 'Cocina con isla C02'})
        self.env['project.task'].create([{
            'name': 'Isla', 'project_id': self.project.id, 'construction_level': 'space',
            'parent_id': unit.id, 'construction_typology_id': island.id,
        } for unit in self.units[:2]])
        # La tipología nueva del adicional va a la línea más reciente de su
        # partida (así la deja el envío de la hoja).
        contract.price_line_ids = [Command.create({
            'typology_id': island.id, 'unit_price': 7000.0, 'sale_line_id': additional.id})]
        contract.action_generate_milestones()
        new = contract.milestone_ids.filtered(lambda m: m.typology_id == island)
        self.assertEqual(len(new), 2)
        self.assertEqual(new.mapped('sale_line_id'), additional)
        self.assertFalse(new.mapped('part_sale_line_id'), 'entera, no es la parte de otro hito')
        self.assertEqual(set(new.mapped('amount')), {7000.0})
        old = contract.milestone_ids - new
        self.assertEqual(len(old), 10, 'la tipología que no cambió no se parte')
        self.assertEqual(old.mapped('sale_line_id'), original)
        self._deliver(contract, self.units)
        self._valuate(contract)
        self.assertEqual(self._valued(contract, original), 50000.0)
        self.assertEqual(self._valued(contract, additional), 14000.0)

    def test_d2_one_line_regenerates_as_before(self):
        """Sin otra línea de la partida en la orden, cambiar el precio rehace
        los hitos sin cobrar en su línea: nada se parte."""
        order = self._order(56000.0)
        contract = self._contract(order, 5000.0)
        contract.price_line_ids.unit_price = 5600.0
        contract.action_generate_milestones()
        self.assertEqual(len(contract.milestone_ids), 10)
        self.assertEqual(set(contract.milestone_ids.mapped('amount')), {5600.0})
        self.assertFalse(contract.milestone_ids.mapped('part_sale_line_id'))

    def test_d2_line_without_partida_is_not_split(self):
        """Una orden sin la partida escrita en sus líneas (obras que no vienen
        de la hoja de venta) no cambia: otra línea no parte los hitos."""
        order = self._order(50000.0, partida=False)
        contract = self._contract(order, 5000.0)
        self._add_line(order, 'Otros trabajos', 6000.0, partida=False)
        contract.price_line_ids.unit_price = 5600.0
        contract.action_generate_milestones()
        self.assertEqual(len(contract.milestone_ids), 10)
        self.assertEqual(contract.milestone_ids.mapped('sale_line_id'), order.order_line[:1])
