# -*- coding: utf-8 -*-
"""Precios de compra (P-16): una fila por línea de OC confirmada, con la
cantidad y el precio en la unidad del producto y convertidos a la moneda de
la compañía al tipo de cambio de Odoo de la fecha de aprobación.

Los estadísticos (ponderado, mediana, medias móviles, resumen por proveedor
y compras atípicas) salen de ``_get_price_stats``, que comparten P-16, W-12
y el tablero de abastecimiento (P-18)."""
import statistics
from collections import defaultdict
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.tools import SQL


def week_start(day, start_day):
    """Inicio de la semana de obra que contiene ``day`` (``start_day`` es
    ``date.weekday()`` del primer día)."""
    return day - timedelta(days=(day.weekday() - int(start_day)) % 7)


def weighted(rows):
    qty = sum(row['qty'] for row in rows)
    return sum(row['amount'] for row in rows) / qty if qty else 0.0


class ConstructionPurchasePriceReport(models.Model):
    _name = 'construction.purchase.price.report'
    _description = 'Precios de compra'
    _auto = False
    _order = 'date_approve desc, id desc'
    _rec_name = 'order_id'

    order_id = fields.Many2one('purchase.order', string='Orden de compra', readonly=True)
    product_id = fields.Many2one('product.product', string='Producto', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', string='Plantilla', readonly=True)
    categ_id = fields.Many2one('product.category', string='Categoría', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Proveedor', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    date_approve = fields.Date(string='Aprobada el', readonly=True)
    week_start = fields.Date(
        string='Semana', readonly=True,
        help='Inicio de la semana de la compra según el día configurado en la compañía.')
    month = fields.Date(string='Mes', readonly=True)
    product_uom_id = fields.Many2one('uom.uom', string='Unidad', readonly=True)
    qty = fields.Float(string='Cantidad', digits='Product Unit', readonly=True, aggregator='sum')
    currency_id = fields.Many2one('res.currency', string='Moneda de la compra', readonly=True)
    price_unit_currency = fields.Float(
        string='Precio en su moneda', digits='Product Price', readonly=True, aggregator='avg',
        help='Precio unitario con descuento en la unidad del producto y la moneda de la OC.')
    currency_rate = fields.Float(
        string='Tipo de cambio', digits=(12, 6), readonly=True, aggregator='avg',
        help='Moneda de la compañía por unidad de la moneda de la compra a la fecha de '
             'aprobación (inverse_company_rate de res.currency.rate).')
    company_currency_id = fields.Many2one(
        'res.currency', string='Moneda de la compañía', readonly=True)
    price_unit = fields.Monetary(
        string='Precio en soles', currency_field='company_currency_id', readonly=True,
        aggregator='avg')
    amount = fields.Monetary(
        string='Monto en soles', currency_field='company_currency_id', readonly=True,
        aggregator='sum')

    def init(self):
        self.env.cr.execute(SQL("DROP VIEW IF EXISTS %s", SQL.identifier(self._table)))
        self.env.cr.execute(SQL("CREATE VIEW %s AS (%s)", SQL.identifier(self._table),
                                self._get_view_query()))

    def _get_view_query(self):
        """Consulta de la vista. El tipo de cambio reproduce
        ``res.currency._get_rates``: la tasa de la compañía raíz o la global
        (primero la de la compañía) con fecha hasta el día de la compra; si no
        hay, la primera registrada; si tampoco, 1."""
        def rate(currency):
            return SQL(
                """COALESCE(
                    (SELECT r.rate FROM res_currency_rate r
                      WHERE r.currency_id = %(currency)s AND r.name <= a.day
                        AND (r.company_id IS NULL OR r.company_id = a.root_company_id)
                      ORDER BY r.company_id, r.name DESC LIMIT 1),
                    (SELECT r.rate FROM res_currency_rate r
                      WHERE r.currency_id = %(currency)s
                        AND (r.company_id IS NULL OR r.company_id = a.root_company_id)
                      ORDER BY r.company_id, r.name LIMIT 1),
                    1.0)""", currency=currency)

        week_day = SQL("COALESCE(c.construction_week_start_day, '3')::int")
        return SQL(
            """
            WITH a AS (
                SELECT pol.id,
                       pol.order_id,
                       pol.product_id,
                       pp.product_tmpl_id,
                       pt.categ_id,
                       po.partner_id,
                       po.company_id,
                       po.currency_id,
                       c.currency_id AS company_currency_id,
                       pt.uom_id AS product_uom_id,
                       split_part(c.parent_path, '/', 1)::int AS root_company_id,
                       (po.date_approve AT TIME ZONE 'UTC'
                            AT TIME ZONE COALESCE(cp.tz, 'UTC'))::date AS day,
                       %(week_day)s AS week_day,
                       pol.product_uom_qty AS qty,
                       pol.price_unit * (1 - COALESCE(pol.discount, 0) / 100.0)
                           * pu.factor / NULLIF(lu.factor, 0) AS price_unit_currency
                  FROM purchase_order_line pol
                  JOIN purchase_order po ON po.id = pol.order_id
                  JOIN res_company c ON c.id = po.company_id
                  JOIN res_partner cp ON cp.id = c.partner_id
                  JOIN product_product pp ON pp.id = pol.product_id
                  JOIN product_template pt ON pt.id = pp.product_tmpl_id
                  JOIN uom_uom pu ON pu.id = pt.uom_id
                  JOIN uom_uom lu ON lu.id = pol.product_uom_id
                 WHERE po.state = 'purchase'
                   AND po.date_approve IS NOT NULL
                   AND pol.display_type IS NULL
                   AND pol.product_uom_qty > 0
            ), b AS (
                SELECT a.*,
                       CASE WHEN a.currency_id = a.company_currency_id THEN 1.0
                            ELSE %(company_rate)s / NULLIF(%(currency_rate)s, 0) END AS currency_rate
                  FROM a
            )
            SELECT b.id,
                   b.order_id,
                   b.product_id,
                   b.product_tmpl_id,
                   b.categ_id,
                   b.partner_id,
                   b.company_id,
                   b.day AS date_approve,
                   b.day - ((EXTRACT(ISODOW FROM b.day)::int - 1 - b.week_day + 7) %% 7)
                       AS week_start,
                   date_trunc('month', b.day)::date AS month,
                   b.product_uom_id,
                   b.qty,
                   b.currency_id,
                   b.price_unit_currency,
                   b.currency_rate,
                   b.company_currency_id,
                   b.price_unit_currency * b.currency_rate AS price_unit,
                   b.qty * b.price_unit_currency * b.currency_rate AS amount
              FROM b
            """,
            week_day=week_day,
            company_rate=rate(SQL("a.company_currency_id")),
            currency_rate=rate(SQL("a.currency_id")),
        )

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------
    @api.model
    def _flush_sources(self):
        """La vista lee las tablas de compras: lo pendiente en caché debe
        estar escrito antes de consultarla."""
        for model in ('purchase.order', 'purchase.order.line', 'res.currency.rate',
                      'product.product', 'product.template', 'uom.uom', 'res.company'):
            self.env[model].flush_model()

    @api.model
    def _get_rows(self, product, company, date_from=None, date_to=None):
        """Compras del producto en la compañía, ordenadas por fecha: lista de
        dicts con fecha, cantidad, precio y monto en la moneda de la compañía,
        proveedor y moneda."""
        self._flush_sources()
        domain = [('product_id', '=', product.id), ('company_id', '=', company.id)]
        if date_from:
            domain.append(('date_approve', '>=', date_from))
        if date_to:
            domain.append(('date_approve', '<=', date_to))
        records = self.search(domain, order='date_approve, id')
        return [{
            'id': record.id,
            'date': record.date_approve,
            'qty': record.qty,
            'price': record.price_unit,
            'amount': record.amount,
            'price_currency': record.price_unit_currency,
            'rate': record.currency_rate,
            'partner': record.partner_id,
            'currency': record.currency_id,
            'order': record.order_id,
        } for record in records]

    @api.model
    def _get_last_prices(self, products, company, date_to=None):
        """{producto: (fecha, precio)} de la última compra confirmada de cada
        producto hasta ``date_to``, en la moneda de la compañía."""
        if not products:
            return {}
        self._flush_sources()
        domain = [('product_id', 'in', products.ids), ('company_id', '=', company.id)]
        if date_to:
            domain.append(('date_approve', '<=', date_to))
        result = {}
        for record in self.search(domain, order='date_approve desc, id desc'):
            result.setdefault(record.product_id, (record.date_approve, record.price_unit))
        return result

    # ------------------------------------------------------------------
    # Estadísticos
    # ------------------------------------------------------------------
    @api.model
    def _get_price_stats(self, product, company, date_from, date_to, week_start_day='3'):
        """Estadísticos de P-16 en la ventana [date_from, date_to]."""
        rows = self._get_rows(product, company, date_from, date_to)
        return self._compute_price_stats(rows, date_to, week_start_day)

    @api.model
    def _compute_price_stats(self, rows, date_to, week_start_day='3'):
        """Estadísticos de una lista de compras (ver ``_get_rows``).

        - ponderado: monto entre cantidad; promedio simple, mediana, mínimo,
          máximo y desviación estándar muestral sobre los precios;
        - por semana (que empieza el día ``week_start_day``) y por mes, con
          la media móvil ponderada de 4 semanas (la semana y las 3 anteriores)
          y de 3 meses calendario (el mes y los 2 anteriores);
        - media móvil de 4 semanas y de 3 meses a ``date_to``;
        - resumen por proveedor;
        - compras atípicas: fuera de 1.5 veces el rango intercuartílico (con 4
          compras o más)."""
        prices = [row['price'] for row in rows]
        stats = {
            'count': len(rows),
            'qty': sum(row['qty'] for row in rows),
            'amount': sum(row['amount'] for row in rows),
            'weighted': weighted(rows),
            'mean': statistics.fmean(prices) if prices else 0.0,
            'median': statistics.median(prices) if prices else 0.0,
            'min': min(prices, default=0.0),
            'max': max(prices, default=0.0),
            'stdev': statistics.stdev(prices) if len(prices) > 1 else 0.0,
            'last': rows[-1]['price'] if rows else 0.0,
            'last_date': rows[-1]['date'] if rows else False,
        }

        by_week = defaultdict(list)
        by_month = defaultdict(list)
        for row in rows:
            by_week[week_start(row['date'], week_start_day)].append(row)
            by_month[row['date'].replace(day=1)].append(row)

        def window_weeks(start):
            return [row for offset in range(4)
                    for row in by_week.get(start - timedelta(weeks=offset), [])]

        def window_months(start):
            return [row for offset in range(3)
                    for row in by_month.get(start - relativedelta(months=offset), [])]

        stats['weeks'] = [{
            'week': start,
            'count': len(week_rows),
            'qty': sum(row['qty'] for row in week_rows),
            'weighted': weighted(week_rows),
            'moving_4w': weighted(window_weeks(start)),
        } for start, week_rows in sorted(by_week.items())]
        stats['months'] = [{
            'month': start,
            'count': len(month_rows),
            'qty': sum(row['qty'] for row in month_rows),
            'weighted': weighted(month_rows),
            'moving_3m': weighted(window_months(start)),
        } for start, month_rows in sorted(by_month.items())]
        if date_to:
            stats['moving_4w'] = weighted(window_weeks(week_start(date_to, week_start_day)))
            stats['moving_3m'] = weighted(window_months(date_to.replace(day=1)))
        else:
            stats['moving_4w'] = stats['moving_3m'] = 0.0

        by_partner = defaultdict(list)
        for row in rows:
            by_partner[row['partner']].append(row)
        stats['partners'] = sorted([{
            'partner': partner,
            'currencies': ', '.join(sorted({row['currency'].symbol or row['currency'].name
                                            for row in partner_rows})),
            'count': len(partner_rows),
            'qty': sum(row['qty'] for row in partner_rows),
            'weighted': weighted(partner_rows),
            'last': partner_rows[-1]['price'],
        } for partner, partner_rows in by_partner.items()], key=lambda p: -p['qty'])

        outliers = set()
        if len(prices) >= 4:
            q1, _q2, q3 = statistics.quantiles(prices, n=4, method='inclusive')
            low, high = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
            outliers = {row['id'] for row in rows if not low <= row['price'] <= high}
        stats['outlier_ids'] = outliers
        stats['rows'] = rows
        return stats

    @api.model
    def _get_basis_prices(self, product, company, basis_date, week_start_day='3'):
        """Sugerencias de costo de W-12 a ``basis_date``: último precio,
        ponderado de 3 y 6 meses y media móvil de 4 semanas."""
        rows = self._get_rows(product, company, date_to=basis_date)
        since_6m = basis_date - relativedelta(months=6)
        since_3m = basis_date - relativedelta(months=3)
        last_6m = [row for row in rows if row['date'] >= since_6m]
        return {
            'last': rows[-1]['price'] if rows else 0.0,
            'weighted_6m': weighted(last_6m),
            'weighted_3m': weighted([row for row in rows if row['date'] >= since_3m]),
            'moving_4w': self._compute_price_stats(
                last_6m, basis_date, week_start_day)['moving_4w'],
            'count_6m': len(last_6m),
        }

