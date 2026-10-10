# -*- coding: utf-8 -*-
from datetime import date, datetime, timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import Form, HttpCase, new_test_user, tagged

from .common import PlannerCommon
from ..models.construction_purchase_price_report import week_start
from ..wizards.product_create_wizard import similarity


@tagged('post_install', '-at_install')
class TestPricesSupply(PlannerCommon):
    """Fase 9: precios de compra (P-16), aplicar costo con media móvil
    (W-12), crear producto desde el plan (W-11, P-17) y abastecimiento de la
    obra (P-18)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.soles = cls.company.currency_id
        cls.usd = cls.env.ref('base.USD') if cls.soles != cls.env.ref('base.USD') \
            else cls.env.ref('base.EUR')
        cls.usd.active = True
        cls.dozen = cls.env.ref('uom.product_uom_dozen')
        Partner = cls.env['res.partner']
        cls.novopan = Partner.create({'name': 'Novopan Perú (test)'})
        cls.mavicch = Partner.create({'name': 'Mavicch (test)'})
        cls.carpicentro = Partner.create({'name': 'Carpicentro (test)'})
        cls.week_day = cls.company.construction_week_start_day or '3'

    # ------------------------------------------------------------------
    # Ayudas
    # ------------------------------------------------------------------
    def _rate(self, day, value, currency=None, company=None):
        """Tipo de cambio de Odoo: soles por unidad de la moneda extranjera."""
        return self.env['res.currency.rate'].create({
            'name': day, 'currency_id': (currency or self.usd).id,
            'company_id': (company or self.company).root_id.id,
            'inverse_company_rate': value})

    def _purchase(self, partner, product, qty, price, day, currency=None, uom=None,
                  discount=0.0, analytic=None, company=None):
        company = company or self.company
        order = self.env['purchase.order'].with_company(company).create({
            'partner_id': partner.id,
            'company_id': company.id,
            'currency_id': (currency or company.currency_id).id,
            'order_line': [Command.create({
                'product_id': product.id, 'product_qty': qty, 'price_unit': price,
                'discount': discount, 'product_uom_id': (uom or product.uom_id).id,
                'analytic_distribution': analytic or False,
            })],
        })
        order.button_confirm()
        self.assertEqual(order.state, 'purchase')
        order.date_approve = datetime.combine(day, datetime.min.time()) + timedelta(hours=15)
        return order

    def _report(self):
        return self.env['construction.purchase.price.report']

    def _small_history(self):
        """Cinco compras con resultado calculado a mano:

        ====================  =====  ==========================  =======
        Fecha                 Cant.  Precio en soles             Monto
        ====================  =====  ==========================  =======
        10/02/2031 (S/)       10     100.00                      1000.00
        03/03/2031 (US$)      10     30.00 × 3.70 = 111.00       1110.00
        10/03/2031 (US$)      24     372/docena = 31 × 3.80      2827.20
        12/03/2031 (S/)       5      150.00 (atípica)             750.00
        20/03/2031 (S/)       30     125 − 4 % = 120.00          3600.00
        ====================  =====  ==========================  =======

        Ponderado 9287.20 / 79 = 117.5595; media móvil de 4 semanas al 20/03
        (semanas desde el jueves 27/02) 8287.20 / 69 = 120.1043."""
        self._rate(date(2031, 3, 3), 3.70)
        self._rate(date(2031, 3, 10), 3.80)
        p = self.p_white
        self._purchase(self.mavicch, p, 10, 100.0, date(2031, 2, 10))
        self._purchase(self.novopan, p, 10, 30.0, date(2031, 3, 3), currency=self.usd)
        self._purchase(self.novopan, p, 2, 372.0, date(2031, 3, 10), currency=self.usd,
                       uom=self.dozen)
        self._purchase(self.carpicentro, p, 5, 150.0, date(2031, 3, 12))
        self._purchase(self.mavicch, p, 30, 125.0, date(2031, 3, 20), discount=4.0)

    # ------------------------------------------------------------------
    # Precios de compra (P-16)
    # ------------------------------------------------------------------
    def test_report_converts_currency_and_uom(self):
        self._small_history()
        rows = self._report()._get_rows(self.p_white, self.company)
        self.assertEqual(len(rows), 5)
        by_date = {row['date']: row for row in rows}
        usd_dozen = by_date[date(2031, 3, 10)]
        self.assertAlmostEqual(usd_dozen['qty'], 24.0)
        self.assertAlmostEqual(usd_dozen['price_currency'], 31.0)
        self.assertAlmostEqual(usd_dozen['rate'], 3.80, places=6)
        self.assertAlmostEqual(usd_dozen['price'], 117.80, places=6)
        self.assertAlmostEqual(by_date[date(2031, 3, 3)]['price'], 111.00, places=6)
        self.assertAlmostEqual(by_date[date(2031, 3, 20)]['price'], 120.00, places=6)
        self.assertEqual(by_date[date(2031, 3, 20)]['currency'], self.soles)
        record = self._report().search([('order_id', '=', usd_dozen['order'].id)])
        self.assertEqual(record.week_start, week_start(date(2031, 3, 10), self.week_day))
        self.assertEqual(record.month, date(2031, 3, 1))
        self.assertAlmostEqual(record.amount, 2827.20, places=4)

    def test_stats_exact(self):
        """Ponderado, mediana, desviación, medias móviles y atípicas exactas."""
        self._small_history()
        stats = self._report()._get_price_stats(
            self.p_white, self.company, date(2031, 1, 1), date(2031, 3, 20), '3')
        self.assertEqual(stats['count'], 5)
        self.assertAlmostEqual(stats['qty'], 79.0)
        self.assertAlmostEqual(stats['weighted'], 9287.2 / 79, places=6)
        self.assertAlmostEqual(stats['mean'], 119.76, places=6)
        self.assertAlmostEqual(stats['median'], 117.80, places=6)
        self.assertAlmostEqual(stats['min'], 100.0)
        self.assertAlmostEqual(stats['max'], 150.0)
        self.assertAlmostEqual(stats['stdev'], 18.6115018, places=6)
        self.assertAlmostEqual(stats['last'], 120.0)
        self.assertEqual(stats['last_date'], date(2031, 3, 20))
        self.assertAlmostEqual(stats['moving_4w'], 8287.2 / 69, places=6)
        self.assertAlmostEqual(stats['moving_3m'], 9287.2 / 79, places=6)
        months = {m['month']: m for m in stats['months']}
        self.assertAlmostEqual(months[date(2031, 2, 1)]['weighted'], 100.0)
        self.assertAlmostEqual(months[date(2031, 3, 1)]['weighted'], 8287.2 / 69, places=6)
        self.assertAlmostEqual(months[date(2031, 3, 1)]['moving_3m'], 9287.2 / 79, places=6)
        # Semanas que empiezan el jueves: 06/02, 27/02, 06/03 y 20/03.
        weeks = {w['week']: w for w in stats['weeks']}
        self.assertEqual(sorted(weeks), [date(2031, 2, 6), date(2031, 2, 27),
                                         date(2031, 3, 6), date(2031, 3, 20)])
        self.assertEqual(weeks[date(2031, 3, 6)]['count'], 2)
        self.assertAlmostEqual(weeks[date(2031, 3, 6)]['weighted'], 3577.2 / 29, places=6)
        # La media móvil de la semana del 06/03 no llega a la del 06/02.
        self.assertAlmostEqual(weeks[date(2031, 3, 6)]['moving_4w'], 4687.2 / 39, places=6)
        partners = {p['partner']: p for p in stats['partners']}
        self.assertEqual(partners[self.novopan]['count'], 2)
        self.assertAlmostEqual(partners[self.novopan]['weighted'], 3937.2 / 34, places=6)
        self.assertIn(self.usd.symbol, partners[self.novopan]['currencies'])
        outliers = [row for row in stats['rows'] if row['id'] in stats['outlier_ids']]
        self.assertEqual([row['price'] for row in outliers], [150.0])
        # Con semanas que empiezan el lunes cambia la agrupación, no el ponderado.
        monday = self._report()._get_price_stats(
            self.p_white, self.company, date(2031, 1, 1), date(2031, 3, 20), '0')
        self.assertIn(date(2031, 3, 10), [w['week'] for w in monday['weeks']])
        self.assertAlmostEqual(monday['weighted'], stats['weighted'], places=6)

    def test_criterion_27_purchases(self):
        """Criterio 13 adaptado: 27 compras (24 en dólares a un proveedor y 3
        en soles a otros) en seis meses; ponderado y media móvil de 4 semanas
        verificados con un cálculo independiente (tolerancia S/ 0.01)."""
        expected = []
        start = date(2031, 4, 14)
        for i in range(24):
            day = start + timedelta(days=7 * i)
            rate = 3.70 + (i % 5) * 0.02
            price = 42.37 if i == 10 else 34.20 + (i % 6) * 0.30
            qty = 320 + (i % 4) * 64
            self._rate(day, rate)
            self._purchase(self.novopan, self.p_white, qty, price, day, currency=self.usd)
            expected.append((day, qty, price * rate))
        for partner, qty, price, day in (
                (self.mavicch, 7, 174.50, date(2031, 5, 28)),
                (self.carpicentro, 64, 162.00, date(2031, 6, 11)),
                (self.carpicentro, 96, 165.00, date(2031, 6, 12))):
            self._purchase(partner, self.p_white, qty, price, day)
            expected.append((day, qty, price))
        date_to = date(2031, 10, 10)
        stats = self._report()._get_price_stats(
            self.p_white, self.company, date(2031, 4, 10), date_to, '3')
        self.assertEqual(stats['count'], 27)

        def weighted(items):
            return sum(q * p for _d, q, p in items) / sum(q for _d, q, _p in items)

        # Semana del 10/10/2031 (viernes) desde el jueves 09/10 y las 3 anteriores.
        since = date(2031, 10, 9) - timedelta(weeks=3)
        self.assertAlmostEqual(stats['weighted'], weighted(expected), delta=0.01)
        self.assertAlmostEqual(stats['moving_4w'],
                               weighted([e for e in expected if e[0] >= since]), delta=0.01)
        self.assertAlmostEqual(stats['last'], expected[23][2], delta=0.01)
        # Las tres compras chicas en soles son las atípicas, con la de US$ 42.37.
        outliers = sorted(row['price'] for row in stats['rows']
                          if row['id'] in stats['outlier_ids'])
        self.assertEqual(len(outliers), 4)
        self.assertEqual(outliers[1:], [162.0, 165.0, 174.5])
        self.assertEqual(stats['partners'][0]['partner'], self.novopan)

        # W-12 con las bases nuevas: la media móvil es la misma cifra de P-16.
        self.env['construction.resource.plan.line'].create({
            'plan_id': self.plan.id, 'task_id': self.space_501.id, 'resource_type': 'material',
            'stage': 'production', 'product_id': self.p_white.id,
            'product_uom_id': self.unit.id, 'qty_planned': 10})
        form = Form(self.env['construction.plan.price.wizard'].with_context(
            default_plan_id=self.plan.id))
        form.product_id = self.p_white
        form.basis_date = date_to
        form.basis = 'moving_4w'
        self.assertAlmostEqual(form.price_moving_4w, stats['moving_4w'], places=2)
        self.assertAlmostEqual(form.price_unit, stats['moving_4w'], places=2)
        self.assertEqual(form.purchase_count, 27)
        form.basis = 'weighted_6m'
        self.assertAlmostEqual(form.price_unit, stats['weighted'], places=2)
        wizard = form.save()
        wizard.basis = 'moving_4w'
        wizard.price_unit = 122.79
        wizard.action_apply()
        line = self.plan.line_ids.filtered(lambda l: l.product_id == self.p_white)
        self.assertEqual(line.price_unit_planned, 122.79)
        self.assertIn('Media móvil de 4 semanas', line.price_basis)
        self.assertEqual(line.price_basis_date, date_to)

    def test_price_analysis_screen(self):
        """P-16: estadísticos, gráfico con atípicas y «Aplicar costo» con la
        base elegida."""
        self._small_history()
        line = self.env['construction.resource.plan.line'].create({
            'plan_id': self.plan.id, 'task_id': self.space_501.id, 'resource_type': 'material',
            'stage': 'production', 'product_id': self.p_white.id,
            'product_uom_id': self.unit.id, 'qty_planned': 10})
        action = line.action_open_purchase_prices()
        self.assertEqual(action['res_model'], 'construction.purchase.price.analysis')
        analysis = self.env['construction.purchase.price.analysis'].with_context(
            action['context']).create({'date_from': date(2031, 1, 1), 'date_to': date(2031, 3, 20),
                                       'basis': 'moving_4w'})
        self.assertEqual(analysis.product_id, self.p_white)
        self.assertEqual(analysis.plan_id, self.plan)
        self.assertEqual(analysis.purchase_count, 5)
        self.assertAlmostEqual(analysis.price_weighted, 117.56, places=2)
        self.assertAlmostEqual(analysis.price_moving_4w, 120.10, places=2)
        self.assertEqual(analysis.outlier_count, 1)
        self.assertEqual(len(analysis.purchase_ids), 5)
        self.assertIn('o_cp_outlier', analysis.chart_html)
        self.assertIn('<title>', analysis.chart_html)
        self.assertIn('Novopan', analysis.partner_html)
        # La ventana editable cambia las cifras.
        analysis.date_from = date(2031, 3, 1)
        self.assertEqual(analysis.purchase_count, 4)
        result = analysis.action_apply_cost()
        self.assertEqual(result['res_model'], 'construction.plan.price.wizard')
        self.assertEqual(result['context']['default_basis'], 'moving_4w')
        self.assertEqual(result['context']['default_basis_date'], '2031-03-20')
        wizard = self.env['construction.plan.price.wizard'].with_context(
            result['context']).create({})
        self.assertEqual(wizard.line_ids, line)
        self.assertAlmostEqual(wizard.price_unit, 8287.2 / 69, places=2)
        # Sin plan (desde el menú) no se aplica costo.
        loose = self.env['construction.purchase.price.analysis'].create(
            {'product_id': self.p_white.id})
        with self.assertRaises(UserError):
            loose.action_apply_cost()
        # Producto sin compras: sin gráfico y sin error.
        empty = self.env['construction.purchase.price.analysis'].create(
            {'product_id': self.p_cap.id})
        self.assertEqual(empty.purchase_count, 0)
        self.assertNotIn('<svg', empty.chart_html)

    # ------------------------------------------------------------------
    # Crear producto desde el plan (W-11, P-17)
    # ------------------------------------------------------------------
    def test_similarity(self):
        self.assertGreater(similarity('Bisagra push open copa 35 mm',
                                      'BISAGRA push-open copa 35mm'), 0.9)
        self.assertGreater(similarity('Melamina coñac 18 mm', '18 mm melamina conac'), 0.9)
        self.assertLess(similarity('Bisagra push open copa 35 mm', 'Tornillos 4×50'), 0.4)

    def test_create_product_from_plan(self):
        """Criterio 15: activo, con código de su familia y marcado con el plan;
        parecidos antes de crear; correlativo sin colisiones; actividad a
        Logística."""
        family = self.env['product.category'].create(
            {'name': 'Bisagras (test)', 'construction_family_code': '9917'})
        Product = self.env['product.product']
        push = Product.create({'name': 'Bisagra push open copa 35 mm (test)',
                               'default_code': '9917606', 'categ_id': family.id})
        Product.create({'name': 'Bisagra lateral Danco (test)', 'default_code': '9917001',
                        'categ_id': family.id})
        # Un archivado también ocupa su número.
        Product.create({'name': 'Bisagra antigua (test)', 'default_code': '9917700',
                        'categ_id': family.id, 'active': False})
        line = self.env['construction.resource.plan.line'].create({
            'plan_id': self.plan.id, 'task_id': self.space_501.id, 'resource_type': 'material',
            'stage': 'assembly', 'product_uom_id': self.unit.id, 'qty_planned': 10})
        action = line.action_open_product_create()
        form = Form(self.env['construction.product.create.wizard'].with_user(
            self.planner).with_context(action['context']))
        form.categ_id = family
        form.name = 'Bisagra push open copa 35 mm cierre lento'
        self.assertEqual(form.code_proposed, '9917701')
        self.assertEqual(form.plan_id, self.plan)
        self.assertEqual(form.uom_id, self.unit)
        self.assertGreaterEqual(form.similar_count, 2)
        form.partner_id = self.novopan
        form.purchase_uom_id = self.dozen
        form.price_reference = 30.0
        wizard = form.save()
        best = wizard.similar_ids.sorted('score', reverse=True)[0]
        self.assertEqual(best.product_id, push)
        self.assertGreater(best.score, 0.8)
        wizard.with_user(self.planner).action_create()
        product = line.product_id
        self.assertTrue(product)
        self.assertTrue(product.active)
        self.assertEqual(product.default_code, '9917701')
        self.assertEqual(product.categ_id, family)
        self.assertEqual(product.construction_created_from_plan_id, self.plan)
        self.assertEqual(product.seller_ids.partner_id, self.novopan)
        self.assertEqual(product.seller_ids.product_uom_id, self.dozen)
        self.assertEqual(product.seller_ids.price, 30.0)
        self.assertEqual(line.product_uom_id, self.unit)
        self.assertFalse(line.price_unit_planned, 'El costo se fija después con W-12.')
        activity = product.product_tmpl_id.activity_ids
        self.assertEqual(len(activity), 1)
        self.assertIn('Completar producto', activity.summary)
        self.assertIn('9917701', str(activity.note))
        # Otro planificador en la misma familia toma el número siguiente.
        second = self.env['construction.product.create.wizard'].with_user(self.planner).create({
            'plan_id': self.plan.id, 'categ_id': family.id, 'name': 'Bisagra recta (test)',
            'uom_id': self.unit.id})
        second.action_create()
        self.assertTrue(Product.search([('default_code', '=', '9917702')]))
        # Unidad de compra sin proveedor: no se pierde en silencio.
        third = self.env['construction.product.create.wizard'].create({
            'plan_id': self.plan.id, 'categ_id': family.id, 'name': 'Bisagra caja (test)',
            'uom_id': self.unit.id, 'purchase_uom_id': self.dozen.id})
        with self.assertRaises(UserError):
            third.action_create()
        # Línea de un plan que no está en borrador: no.
        self.plan.state = 'approved'
        with self.assertRaises(UserError):
            line.action_open_product_create()

    def test_use_similar_product(self):
        family = self.env['product.category'].create(
            {'name': 'Tornillería (test)', 'construction_family_code': '9918'})
        line = self.env['construction.resource.plan.line'].create({
            'plan_id': self.plan.id, 'task_id': self.space_501.id, 'resource_type': 'material',
            'stage': 'installation', 'product_uom_id': self.unit.id, 'qty_planned': 100})
        wizard = self.env['construction.product.create.wizard'].create({
            'plan_line_id': line.id, 'categ_id': family.id, 'name': 'Tornillos 4 x 50'})
        similar = wizard.similar_ids.filtered(lambda s: s.product_id == self.p_screw)
        self.assertTrue(similar)
        similar.action_use_product()
        self.assertEqual(line.product_id, self.p_screw)

    # ------------------------------------------------------------------
    # Abastecimiento de la obra (P-18)
    # ------------------------------------------------------------------
    def _supply_setup(self):
        """Melamina blanca del ejemplo de P-18: 330.82 en la obra, 192.13 en
        el horizonte de 4 semanas, 40 en stock y 96 en OC con la analítica de
        la obra."""
        if not self.project.account_id:
            self.project._create_analytic_account()
        today = fields.Date.context_today(self.env['construction.supply.board'])
        week0 = self.project._construction_period(today)[0]
        Stage = self.env['construction.space.stage']
        Stage.create([
            {'space_task_id': self.space_501.id, 'stage': 'production',
             'date_start': week0, 'date_end': week0 + timedelta(days=4)},
            {'space_task_id': self.space_502.id, 'stage': 'production',
             'date_start': week0 + timedelta(days=7), 'date_end': week0 + timedelta(days=11)},
        ])
        Line = self.env['construction.resource.plan.line']

        def line(product, task, stage, qty, price, need=None):
            vals = {'plan_id': self.plan.id, 'task_id': task.id, 'resource_type': 'material',
                    'stage': stage, 'product_id': product.id, 'product_uom_id': self.unit.id,
                    'qty_planned': qty, 'price_unit_planned': price}
            record = Line.create(vals)
            if need:
                record.date_needed = need
            return record

        white, cognac = self.p_white, self.p_cognac
        line(white, self.space_501, 'production', 36.07, 122.79)
        line(white, self.space_502, 'production', 52.02, 122.79)
        line(white, self.floor, 'assembly', 52.02, 122.79, week0 + timedelta(days=14))
        line(white, self.floor, 'installation', 52.02, 122.79, week0 + timedelta(days=21))
        line(white, self.floor, 'finishing', 138.69, 122.79, week0 + timedelta(days=35))
        line(cognac, self.space_501, 'production', 18.24, 228.07)
        # Sin compras ni proveedor (confirmar una OC registra al proveedor).
        line(self.p_rh, self.space_502, 'finishing', 5.0, 10.0)
        white.is_storable = True
        self.env['stock.quant']._update_available_quantity(
            white, self.company.construction_src_location_id, 40.0)
        analytic = {str(self.project.account_id.id): 100.0}
        self._purchase(self.novopan, white, 96, 123.89, today, analytic=analytic)
        # Sin la analítica de la obra no cuenta como «En OC».
        self._purchase(self.novopan, white, 50, 123.89, today - timedelta(days=1))
        self._purchase(self.carpicentro, cognac, 10, 239.42, today)
        self.env['product.supplierinfo'].create({
            'product_tmpl_id': cognac.product_tmpl_id.id, 'partner_id': self.carpicentro.id,
            'price': 239.42})
        return week0

    def test_supply_board(self):
        week0 = self._supply_setup()
        Board = self.env['construction.supply.board']
        data = Board._get_board_data(self.project)
        self.assertEqual(data['weeks'][0], fields.Date.to_string(week0))
        rows = {row['product_id']: row for row in data['rows']}
        white = rows[self.p_white.id]
        self.assertAlmostEqual(white['need_total'], 330.82, places=2)
        self.assertEqual([round(q, 2) for q in white['need_weeks']],
                         [36.07, 52.02, 52.02, 52.02])
        self.assertAlmostEqual(white['need_horizon'], 192.13, places=2)
        self.assertAlmostEqual(white['stock'], 40.0)
        self.assertAlmostEqual(white['on_order'], 96.0)
        # 192.13 − 40 − 96 = 56.13 → 57 planchas.
        self.assertAlmostEqual(white['to_buy'], 56.13, places=2)
        self.assertEqual(white['qty_to_buy'], 57.0)
        self.assertAlmostEqual(white['cost_plan'], 122.79, places=2)
        self.assertAlmostEqual(white['price_last'], 123.89, places=2)
        self.assertFalse(white['price_alert'])
        self.assertAlmostEqual(white['amount'], 6999.03, places=2)
        self.assertFalse(white['no_supplier_alert'], 'La OC registró al proveedor.')
        self.assertFalse(white['no_po_alert'])
        self.assertTrue(rows[self.p_rh.id]['no_supplier_alert'])
        # Alerta de precio: 239.42 sobre 228.07 es +5.0 %.
        cognac = rows[self.p_cognac.id]
        self.assertTrue(cognac['price_alert'])
        self.assertAlmostEqual(cognac['price_pct'], 4.98, places=2)
        self.assertFalse(cognac['no_supplier_alert'])
        self.assertTrue(cognac['no_po_alert'])
        alerts = Board._get_supply_alerts(self.project)
        self.assertEqual(
            sorted((a['type'], a['product_id']) for a in alerts),
            sorted([('price', self.p_cognac.id), ('no_po', self.p_cognac.id),
                    ('no_po', self.p_rh.id), ('no_supplier', self.p_rh.id)]))
        # El umbral es parámetro de la compañía.
        self.company.construction_price_alert_pct = 6.0
        rows = {row['product_id']: row for row in Board._get_board_data(self.project)['rows']}
        self.assertFalse(rows[self.p_cognac.id]['price_alert'])
        # Horizonte y etapas.
        data = Board._get_board_data(self.project, weeks=6)
        white = next(r for r in data['rows'] if r['product_id'] == self.p_white.id)
        self.assertAlmostEqual(white['need_horizon'], 330.82, places=2)
        data = Board._get_board_data(self.project, stages=['assembly'])
        self.assertEqual([r['product_id'] for r in data['rows']], [self.p_white.id])
        self.assertAlmostEqual(data['rows'][0]['need_total'], 52.02, places=2)
        # Interfaz de la pantalla.
        self.assertIn(self.project.id, [p['id'] for p in Board.get_board_projects()])
        board = Board.get_board(self.project.id, {'weeks': 4})
        self.assertEqual(len(board['alerts']), 3)
        action = Board.action_open_prices(self.p_white.id, self.project.id)
        self.assertEqual(action['context']['default_product_id'], self.p_white.id)

    def test_supply_board_opens_mass_purchase(self):
        """Las filas marcadas abren W-02 con esos productos (plan vigente)."""
        self._supply_setup()
        Board = self.env['construction.supply.board']
        with self.assertRaises(UserError):
            Board.action_open_purchase(self.project.id, [self.p_white.id])
        self.plan.write({'state': 'approved'})
        action = Board.action_open_purchase(
            self.project.id, [self.p_white.id], {'weeks': 4, 'stages': ['production']})
        self.assertEqual(action['res_model'], 'construction.plan.purchase.wizard')
        wizard = self.env['construction.plan.purchase.wizard'].with_context(
            action['context']).create({})
        self.assertEqual(wizard.product_ids, self.p_white)
        self.assertTrue(wizard.whole_project)
        self.assertFalse(wizard.stage_assembly)
        self.assertEqual(wizard.line_ids.product_id, self.p_white)
        self.assertAlmostEqual(wizard.line_ids.qty_need, 36.07 + 52.02, places=2)

    def test_open_from_plan(self):
        action = self.plan.action_open_supply_board()
        self.assertEqual(action['tag'], 'al_construction_planner.supply_board')
        self.assertEqual(action['context']['construction_project_id'], self.project.id)
        action = self.plan.action_open_product_create()
        self.assertEqual(action['context']['default_plan_id'], self.plan.id)

    # ------------------------------------------------------------------
    # Multicompañía
    # ------------------------------------------------------------------
    def test_multicompany(self):
        """Las compras de otra compañía no entran en los precios ni se ven."""
        self._small_history()
        other = self.env['res.company'].create({
            'name': 'Constructora B (test)', 'currency_id': self.soles.id})
        self.env.user.company_ids |= other
        self._purchase(self.novopan, self.p_white, 100, 999.0, date(2031, 3, 15), company=other)
        Report = self._report()
        stats = Report._get_price_stats(
            self.p_white, self.company, date(2031, 1, 1), date(2031, 3, 20), '3')
        self.assertEqual(stats['count'], 5)
        self.assertNotIn(999.0, [row['price'] for row in stats['rows']])
        other_stats = Report._get_price_stats(
            self.p_white, other, date(2031, 1, 1), date(2031, 3, 20), '3')
        self.assertEqual(other_stats['count'], 1)
        planner = new_test_user(
            self.env, 'plan_precios_a', groups='al_construction_planner.group_planner_planner',
            company_id=self.company.id, company_ids=[Command.set(self.company.ids)])
        visible = Report.with_user(planner).search([('product_id', '=', self.p_white.id)])
        self.assertEqual(len(visible), 5)
        self.assertEqual(visible.company_id, self.company)
        with self.assertRaises(AccessError):
            self.env['construction.purchase.price.analysis'].with_user(planner).create({
                'product_id': self.p_white.id, 'company_id': other.id})


@tagged('post_install', '-at_install')
class TestSupplyBoardTour(HttpCase):

    def test_supply_board_tour(self):
        self.env['tier.definition'].search(
            [('model', '=', 'construction.resource.plan')]).active = False
        project = self.env['project.project'].create({
            'name': 'Obra tour abastecimiento (test)', 'is_construction_site': True})
        product = self.env['product.product'].create({
            'name': 'Melamina tour abastecimiento (test)', 'type': 'consu'})
        plan = self.env['construction.resource.plan'].create({'project_id': project.id})
        self.env['construction.resource.plan.line'].create({
            'plan_id': plan.id, 'resource_type': 'material', 'stage': 'production',
            'product_id': product.id, 'product_uom_id': product.uom_id.id,
            'qty_planned': 12.4, 'price_unit_planned': 100.0})
        plan.write({'state': 'approved'})
        # 12.4 planchas → 13 a comprar.
        self.start_tour('/odoo/abastecimiento-obra', 'al_construction_planner_supply_board',
                        login='admin')
