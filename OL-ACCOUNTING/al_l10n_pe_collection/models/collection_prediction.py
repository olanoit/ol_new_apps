from collections import defaultdict
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models

CONFIDENCE = [('high', 'Alta'), ('medium', 'Media'), ('low', 'Baja')]
PREDICTION_SOURCES = [
    ('history', 'Historial del cliente'),
    ('overdue', 'Historial, ya atrasada'),
    ('segment', 'Comportamiento de la cartera'),
    ('promise', 'Compromiso de pago'),
]
#: Vida media del peso de un pago del historial: los recientes pesan más.
HALF_LIFE_DAYS = 180
#: Pagos desde los que el historial propio da confianza media.
MIN_SAMPLES = 3
#: Ajuste estacional máximo (días) y pagos mínimos por mes para calcularlo.
MAX_SEASONAL_DAYS = 15
MIN_MONTH_SAMPLES = 5


def weighted_quantile(samples, q):
    """Cuantil ponderado de [(valor, peso)]."""
    samples = sorted(samples)
    total = sum(w for _v, w in samples)
    if not total:
        return 0.0
    acc = 0.0
    for value, weight in samples:
        acc += weight
        if acc >= q * total:
            return value
    return samples[-1][0]


class L10nPeCollectionPredictor(models.AbstractModel):
    """Predicción de la fecha de pago de cada cuota por cobrar.

    Modelo estadístico explicable, sin servicios externos:

    * **Historial del cliente:** atraso de sus cuotas pagadas (fecha del pago −
      vencimiento) en los meses de historial de Ajustes, ponderado por importe y
      por antigüedad (vida media de 180 días). La estimación es la mediana
      ponderada, robusta a un pago excepcional.
    * **Cuota ya atrasada:** si la cuota ya superó el atraso habitual, solo
      cuentan los pagos del cliente que se atrasaron al menos lo mismo; si
      nunca se atrasó tanto, se extrapola con confianza baja.
    * **Estacionalidad:** diferencia del atraso promedio de la cartera en el mes
      del vencimiento frente al promedio general (hasta ±15 días).
    * **Sin pagos previos:** comportamiento de toda la cartera (confianza baja).
    * **Compromiso de pago pendiente:** manda su fecha.

    La confianza sale de la cantidad de pagos y de su dispersión (rango
    intercuartílico). ``_backtest`` mide el error contra pagos reales.
    """
    _name = 'l10n_pe.collection.predictor'
    _description = 'Predicción de pagos de cobranza'

    # ------------------------------------------------------------------
    # Historial
    # ------------------------------------------------------------------

    @api.model
    def _paid_samples(self, company, today, months=None):
        """Cuotas pagadas del historial: [{partner, due, paid_on, delay, amount}]."""
        root = company.root_id
        months = months or root.l10n_pe_collection_history_months or 12
        since = today - relativedelta(months=months)
        # sudo: la predicción usa los pagos de toda la cartera, no solo los del gestor.
        terms_sudo = self.env['account.move.line'].sudo().search([
            ('company_id', 'child_of', root.id),
            ('display_type', '=', 'payment_term'),
            ('parent_state', '=', 'posted'),
            ('move_id.move_type', '=', 'out_invoice'),
            ('reconciled', '=', True),
            ('account_id', 'not in', root._l10n_pe_collection_excluded_accounts().ids),
            ('date_maturity', '>=', since - relativedelta(months=6)),
        ])
        samples = []
        for term in terms_sudo:
            # Solo cobros por bancos y cajas: un castigo o una nota de crédito no es un pago.
            partials = term.matched_credit_ids.filtered(
                lambda p: p.credit_move_id.journal_id.type in ('bank', 'cash'))
            if not partials:
                continue
            paid_on = max(partials.mapped('max_date'))
            if paid_on < since or paid_on > today:
                continue
            due = term.date_maturity or term.date
            samples.append({
                'partner': term.partner_id.commercial_partner_id.id, 'due': due, 'paid_on': paid_on,
                'delay': (paid_on - due).days, 'amount': abs(term.balance),
            })
        return samples

    @api.model
    def _profile(self, company, today, samples=None):
        """Historial por cliente, de la cartera y efecto de cada mes."""
        samples = self._paid_samples(company, today) if samples is None else samples
        by_partner = defaultdict(list)
        for sample in samples:
            by_partner[sample['partner']].append(sample)
        month_effect = {}
        if samples:
            overall = sum(s['delay'] * s['amount'] for s in samples) / (sum(s['amount'] for s in samples) or 1)
            by_month = defaultdict(list)
            for sample in samples:
                by_month[sample['due'].month].append(sample)
            for month, rows in by_month.items():
                if len(rows) >= MIN_MONTH_SAMPLES:
                    mean = sum(s['delay'] * s['amount'] for s in rows) / (sum(s['amount'] for s in rows) or 1)
                    month_effect[month] = max(-MAX_SEASONAL_DAYS, min(MAX_SEASONAL_DAYS, round(mean - overall)))
        return {'today': today, 'samples': samples, 'by_partner': by_partner, 'month_effect': month_effect}

    @staticmethod
    def _weights(rows, today):
        return [(s['delay'], s['amount'] * 0.5 ** (max((today - s['paid_on']).days, 0) / HALF_LIFE_DAYS))
                for s in rows]

    @staticmethod
    def _confidence(count, spread):
        if count >= 8 and spread <= 15:
            return 'high'
        if count >= MIN_SAMPLES and spread <= 30:
            return 'medium'
        return 'low'

    # ------------------------------------------------------------------
    # Predicción
    # ------------------------------------------------------------------

    @api.model
    def _predict_delay(self, partner_id, due, today, profile, rows=None):
        """Atraso previsto (días desde el vencimiento) de una cuota que vence
        en ``due`` y sigue abierta ``today``. Devuelve dict con delay,
        confidence, source y samples."""
        rows = profile['by_partner'].get(partner_id, []) if rows is None else rows
        source = 'history'
        if not rows:
            rows, source = profile['samples'], 'segment'
        if not rows:
            return {'delay': max((today - due).days, 0), 'confidence': 'low', 'source': 'segment', 'samples': 0}
        days_open = (today - due).days
        weighted = self._weights(rows, today)
        if source == 'segment':
            # En la cartera cada pago cuenta igual: unas pocas deudas grandes no deben
            # marcar el comportamiento de todos.
            weighted = [(d, w / (s['amount'] or 1.0)) for (d, w), s in zip(weighted, rows)]
        if days_open > 0:
            later = [(d, w) for d, w in weighted if d >= days_open]
            if len(later) >= 2:
                weighted = later
            else:
                # Ya pasó lo que el cliente suele atrasarse: se extrapola.
                typical = weighted_quantile(weighted, 0.75) - weighted_quantile(weighted, 0.25)
                return {'delay': days_open + max(15, round(typical)), 'confidence': 'low', 'source': 'overdue',
                        'samples': len(rows)}
            source = 'overdue' if source == 'history' else source
        delay = weighted_quantile(weighted, 0.5)
        if days_open <= 0:
            delay += profile['month_effect'].get(due.month, 0)
        spread = weighted_quantile(weighted, 0.75) - weighted_quantile(weighted, 0.25)
        confidence = self._confidence(len(weighted), spread)
        if source == 'segment':
            confidence = 'low'
        return {'delay': round(delay), 'confidence': confidence, 'source': source, 'samples': len(rows)}

    @api.model
    def _predict_lines(self, lines, company, today, profile=None):
        """{apunte: {'date', 'delay', 'confidence', 'source', 'samples'}} de cuotas abiertas."""
        profile = profile or self._profile(company, today)
        promises = self._pending_promises(lines, company, today)
        result = {}
        for line in lines:
            due = line.date_maturity or line.date
            if line in promises:
                promise = promises[line]
                result[line] = {'date': promise.date, 'delay': (promise.date - due).days,
                                'confidence': promise.partner_id._l10n_pe_collection_promise_confidence(company, today),
                                'source': 'promise', 'samples': 0}
                continue
            data = self._predict_delay(line.partner_id.commercial_partner_id.id, due, today, profile)
            data['date'] = max(due + timedelta(days=data['delay']), today)
            data['delay'] = (data['date'] - due).days
            result[line] = data
        return result

    @api.model
    def _pending_promises(self, lines, company, today):
        """Compromiso pendiente que cubre cada cuota: el de sus documentos o, si
        no tiene, el del cliente aplicado a sus cuotas más antiguas."""
        # sudo: la predicción mira los compromisos de todos los gestores.
        promises_sudo = self.env['l10n_pe.collection.promise'].sudo().search([
            ('partner_id', 'in', lines.partner_id.commercial_partner_id.ids),
            ('company_id', 'child_of', company.root_id.id),
            ('state', '=', 'pending'), ('date', '>=', today)], order='date')
        covered = {}
        for promise in promises_sudo:
            if promise.line_ids:
                for line in promise.line_ids & lines:
                    covered.setdefault(line, promise)
                continue
            remaining = promise.amount
            partner_lines = lines.filtered(
                lambda l: l.partner_id.commercial_partner_id == promise.partner_id and l not in covered)
            for line in partner_lines.sorted(lambda l: (l.date_maturity or l.date, l.id)):
                if remaining <= 0:
                    break
                covered[line] = promise
                remaining -= line.amount_residual
        return covered

    # ------------------------------------------------------------------
    # Precisión
    # ------------------------------------------------------------------

    @api.model
    def _backtest(self, company, today=None, months=3):
        """Error de la predicción en las cuotas pagadas los últimos meses,
        prediciendo cada una con lo que se sabía a su vencimiento. Compara con
        suponer que se paga al vencer."""
        today = today or fields.Date.context_today(self)
        samples = self._paid_samples(company, today, months=(company.root_id.l10n_pe_collection_history_months or 12)
                                     + months)
        tested = [s for s in samples if s['paid_on'] >= today - relativedelta(months=months)]
        # Las más recientes primero y con tope: cada una rehace el perfil de la cartera.
        tested = sorted(tested, key=lambda s: s['paid_on'], reverse=True)[:400]
        errors, naive, within = [], [], 0
        for sample in tested:
            known = [s for s in samples if s['paid_on'] < sample['due']]
            if not known:
                continue
            profile = self._profile(company, sample['due'], samples=known)
            rows = [s for s in known if s['partner'] == sample['partner']]
            delay = self._predict_delay(sample['partner'], sample['due'], sample['due'], profile,
                                        rows=rows)['delay']
            error = abs(delay - sample['delay'])
            errors.append(error)
            naive.append(abs(sample['delay']))
            within += error <= 7
        count = len(errors)
        return {
            'count': count,
            'mae': round(sum(errors) / count, 1) if count else 0.0,
            'naive_mae': round(sum(naive) / count, 1) if count else 0.0,
            'within_7': round(100.0 * within / count) if count else 0,
        }

    @api.model
    def _backtest_notification(self, company):
        result = self._backtest(company)
        if not result['count']:
            message = _('Todavía no hay pagos suficientes para medir la predicción.')
        else:
            message = _(
                'En %(count)s cuotas pagadas en los últimos 3 meses, la predicción se equivocó en %(mae)s días en '
                'promedio (suponer el pago al vencer: %(naive)s días). El %(within)s %% de los pagos cayó a menos de '
                '7 días de la fecha prevista.', count=result['count'], mae=result['mae'],
                naive=result['naive_mae'], within=result['within_7'])
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'title': _('Precisión de la predicción de pago'), 'message': message, 'sticky': True,
                       'type': 'info'},
        }

    # ------------------------------------------------------------------
    # Proceso diario
    # ------------------------------------------------------------------

    @api.model
    def _cron_predict(self):
        today = fields.Date.context_today(self)
        for company in self.env['res.company'].search([('parent_id', '=', False)]):
            self._refresh(company, today)

    @api.model
    def _refresh(self, company, today=None):
        """Recalcula las predicciones de toda la cartera abierta de la compañía y
        el atraso típico de cada cliente."""
        today = today or fields.Date.context_today(self)
        root = company.root_id
        # sudo: proceso de toda la cartera, no de un gestor.
        Prediction_sudo = self.env['l10n_pe.collection.prediction'].sudo()
        lines_sudo = self.env['account.move.line'].sudo().search([
            ('company_id', 'child_of', root.id),
            ('parent_state', '=', 'posted'),
            ('account_id.account_type', '=', 'asset_receivable'),
            ('account_id', 'not in', root._l10n_pe_collection_excluded_accounts().ids),
            ('reconciled', '=', False),
            ('amount_residual', '>', 0),
            ('partner_id', '!=', False),
        ])
        profile = self._profile(root, today)
        predictions = self._predict_lines(lines_sudo, root, today, profile)
        late_days = root.l10n_pe_collection_prediction_late_days
        Prediction_sudo.search([('company_id', 'child_of', root.id)]).unlink()
        Prediction_sudo.create([{
            'move_line_id': line.id,
            'company_id': line.company_id.id,
            'partner_id': line.partner_id.commercial_partner_id.id,
            'date_due': line.date_maturity or line.date,
            'predicted_date': data['date'],
            'predicted_delay': data['delay'],
            'confidence': data['confidence'],
            'source': data['source'],
            'late_risk': data['delay'] > late_days,
            'computed_on': today,
        } for line, data in predictions.items()])
        partners_sudo = lines_sudo.partner_id.commercial_partner_id.with_company(root)
        for partner_sudo in partners_sudo:
            typical = self._predict_delay(partner_sudo.id, today, today, profile)
            partner_sudo.write({
                'l10n_pe_collection_typical_delay': typical['delay'],
                'l10n_pe_collection_prediction_confidence': typical['confidence']
                if typical['source'] != 'segment' else 'low',
            })
        return len(predictions)


class L10nPeCollectionPrediction(models.Model):
    """Fecha prevista de pago de cada cuota abierta; la recalcula el proceso
    diario y la usa la cartera."""
    _name = 'l10n_pe.collection.prediction'
    _description = 'Fecha prevista de pago'
    _order = 'predicted_date'

    move_line_id = fields.Many2one('account.move.line', string='Cuota', required=True, index=True,
                                   ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Compañía', required=True, index=True)
    partner_id = fields.Many2one('res.partner', string='Cliente', index=True)
    date_due = fields.Date(string='Vencimiento')
    predicted_date = fields.Date(string='Pago previsto')
    predicted_delay = fields.Integer(string='Atraso previsto (días)')
    confidence = fields.Selection(CONFIDENCE, string='Confianza')
    source = fields.Selection(PREDICTION_SOURCES, string='Base de la predicción')
    late_risk = fields.Boolean(string='Atraso previsto')
    computed_on = fields.Date(string='Calculada el')

    _move_line_uniq = models.Constraint('unique(move_line_id)', 'La cuota ya tiene predicción.')
