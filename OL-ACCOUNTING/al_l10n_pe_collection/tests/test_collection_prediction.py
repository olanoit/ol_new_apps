from datetime import date, timedelta

from odoo.tests import tagged

from odoo.addons.al_l10n_pe_collection.models.collection_prediction import weighted_quantile

from .common import CollectionCommon


@tagged('post_install', '-at_install')
class TestCollectionPrediction(CollectionCommon):
    """Predicción de la fecha de pago."""

    def _profile(self, today, rows_by_partner, others=(), month_effect=None):
        samples = [s for rows in rows_by_partner.values() for s in rows] + list(others)
        return {'today': today, 'samples': samples, 'by_partner': rows_by_partner,
                'month_effect': month_effect or {}}

    @staticmethod
    def _sample(partner, delay, paid_on, amount=100.0):
        return {'partner': partner, 'due': paid_on - timedelta(days=delay), 'paid_on': paid_on,
                'delay': delay, 'amount': amount}

    def test_weighted_quantile(self):
        self.assertEqual(weighted_quantile([(10, 1), (20, 1), (30, 1)], 0.5), 20)
        self.assertEqual(weighted_quantile([(10, 1), (90, 10)], 0.5), 90, 'Pesa el importe.')
        self.assertEqual(weighted_quantile([], 0.5), 0.0)

    def test_median_is_robust_and_recent_payments_weigh_more(self):
        today = date(2026, 10, 22)
        Predictor = self.env['l10n_pe.collection.predictor']
        rows = [self._sample(1, d, today - timedelta(days=20 + i)) for i, d in enumerate((8, 10, 12, 9, 11, 200))]
        data = Predictor._predict_delay(1, today + timedelta(days=5), today, self._profile(today, {1: rows}))
        self.assertEqual(data['delay'], 10, 'Un pago excepcional de 200 días no mueve la mediana.')
        self.assertEqual((data['source'], data['confidence']), ('history', 'medium'))
        old_late = [self._sample(2, 60, today - timedelta(days=700), 1000.0) for _i in range(3)]
        recent_punctual = [self._sample(2, 2, today - timedelta(days=10), 1000.0) for _i in range(3)]
        data = Predictor._predict_delay(2, today, today, self._profile(today, {2: old_late + recent_punctual}))
        self.assertEqual(data['delay'], 2, 'El historial reciente pesa más.')

    def test_overdue_installment_conditions_on_longer_delays(self):
        today = date(2026, 10, 22)
        Predictor = self.env['l10n_pe.collection.predictor']
        rows = [self._sample(1, d, today - timedelta(days=30)) for d in (5, 5, 6, 40, 45, 50)]
        profile = self._profile(today, {1: rows})
        data = Predictor._predict_delay(1, today - timedelta(days=30), today, profile)
        self.assertEqual((data['delay'], data['source']), (45, 'overdue'),
                         'Ya lleva 30 días: cuenta solo cuando se atrasó 30 o más.')
        data = Predictor._predict_delay(1, today - timedelta(days=90), today, profile)
        self.assertEqual(data['confidence'], 'low')
        self.assertGreaterEqual(data['delay'], 105, 'Nunca se atrasó 90 días: se extrapola al menos 15 más.')

    def test_seasonality_and_segment_fallback(self):
        today = date(2026, 10, 22)
        Predictor = self.env['l10n_pe.collection.predictor']
        rows = [self._sample(1, 10, today - timedelta(days=15)) for _i in range(4)]
        others = [self._sample(9, 30, today - timedelta(days=15)) for _i in range(5)]
        profile = self._profile(today, {1: rows}, others, month_effect={12: 8})
        self.assertEqual(Predictor._predict_delay(1, date(2026, 12, 15), today, profile)['delay'], 18,
                         'Diciembre se paga 8 días más tarde en la cartera.')
        data = Predictor._predict_delay(5, date(2026, 11, 15), today, profile)
        self.assertEqual((data['source'], data['confidence']), ('segment', 'low'))
        self.assertEqual(data['delay'], 30, 'Sin pagos previos: el comportamiento de la cartera.')

    def test_profile_month_effect(self):
        today = date(2026, 10, 22)
        Predictor = self.env['l10n_pe.collection.predictor']
        samples = [self._sample(1, 10, date(2026, 6, 20)) for _i in range(10)]
        samples += [{'partner': 1, 'due': date(2026, 3, 31), 'paid_on': date(2026, 4, 30), 'delay': 30,
                     'amount': 100.0} for _i in range(5)]
        profile = Predictor._profile(self.company, today, samples=samples)
        self.assertEqual(profile['month_effect'][3], 13, '30 frente al promedio de 16,7.')
        self.assertLess(profile['month_effect'][6], 0)

    def test_refresh_feeds_portfolio_partner_and_forecast(self):
        for days_ago, due_ago in ((90, 100), (60, 75), (30, 45)):
            invoice = self._invoice(400, -due_ago, invoice_date=self.today - timedelta(days=due_ago + 30))
            self._pay(invoice, day=self.today - timedelta(days=days_ago))  # paga 10 a 15 días tarde
        upcoming = self._invoice(800, 5)
        count = self.env['l10n_pe.collection.predictor']._refresh(self.company)
        self.assertGreaterEqual(count, 1)
        prediction = self.env['l10n_pe.collection.prediction'].search(
            [('move_line_id', '=', self._receivable(upcoming).id)])
        self.assertEqual(prediction.source, 'history')
        self.assertGreaterEqual(prediction.predicted_delay, 10)
        self.assertEqual(prediction.predicted_date, self.today + timedelta(days=5 + prediction.predicted_delay))
        self.assertEqual(prediction.late_risk, prediction.predicted_delay > 7)
        customer = self.customer.with_company(self.company)
        self.assertGreaterEqual(customer.l10n_pe_collection_typical_delay, 10)
        self.assertEqual(customer.l10n_pe_collection_prediction_confidence, 'medium')
        Portfolio = self.env['l10n_pe.collection.portfolio']
        Portfolio.flush_model()
        row = Portfolio.search([('move_id', '=', upcoming.id)])
        self.assertEqual((row.predicted_date, row.late_risk), (prediction.predicted_date, prediction.late_risk))
        forecast = self.env['l10n_pe.collection.forecast'].create({'name': 'Predicción'})
        line = forecast.line_ids.filtered(lambda l: l.move_id == upcoming)
        self.assertEqual((line.source, line.expected_date), ('prediction', prediction.predicted_date))

    def test_promise_sets_date_and_confidence(self):
        invoice = self._invoice(600, -20)
        self._promise(600, self.today + timedelta(days=4), self._receivable(invoice))
        data = self.env['l10n_pe.collection.predictor']._predict_lines(
            self._receivable(invoice), self.company, self.today)[self._receivable(invoice)]
        self.assertEqual((data['source'], data['date']), ('promise', self.today + timedelta(days=4)))
        self.assertEqual(data['confidence'], 'medium', 'Sin compromisos evaluados: confianza media.')

    def test_backtest_and_settings_actions(self):
        for due_ago in (120, 90, 60, 30):
            invoice = self._invoice(500, -due_ago, invoice_date=self.today - timedelta(days=due_ago + 30))
            self._pay(invoice, day=self.today - timedelta(days=due_ago - 10))
        result = self.env['l10n_pe.collection.predictor']._backtest(self.company)
        self.assertGreaterEqual(result['count'], 1)
        self.assertGreaterEqual(result['naive_mae'], 0)
        settings = self.env['res.config.settings'].create({})
        self.assertEqual(settings.action_l10n_pe_collection_prediction_backtest()['tag'], 'display_notification')
        self.assertEqual(settings.action_l10n_pe_collection_prediction_refresh()['tag'], 'display_notification')
