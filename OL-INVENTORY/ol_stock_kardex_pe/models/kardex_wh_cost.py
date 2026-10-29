from collections import defaultdict

from odoo import api, fields, models
from odoo.tools import SQL, split_every


class L10nPeKardexWhCost(models.Model):
    """Costo promedio ponderado por almacén, fila a fila del kardex.

    Odoo valoriza con un solo promedio por compañía y no da valor a los
    traslados entre almacenes. Aquí se reproducen los movimientos en orden y
    cada almacén lleva su propio saldo:

    * una entrada suma su valor (``stock.move.value``) al almacén de destino;
      una devolución de cliente vuelve al costo con que salió;
    * una salida sale al promedio de su almacén;
    * un traslado sale al promedio del almacén de origen y entra con ese mismo
      valor al de destino. Las ubicaciones de tránsito (sin almacén) son un
      almacén más, para que el valor viaje con la mercadería.

    ``line_key`` es el id de la fila de ``l10n_pe.kardex.line`` (``move_id * 3
    + k``); la vista del kardex toma de aquí el valor y los saldos. Solo se
    calculan los productos con costo promedio y sin valorización por lote.
    """
    _name = 'l10n_pe.kardex.wh.cost'
    _description = 'Costo por almacén (kardex)'
    _order = 'company_id, product_id, date, line_key'
    _log_access = False

    line_key = fields.Integer(required=True, index=True)
    move_id = fields.Many2one('stock.move', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one('product.product', required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', required=True, ondelete='cascade')
    warehouse_id = fields.Many2one('stock.warehouse', ondelete='cascade')
    date = fields.Datetime(required=True)
    qty = fields.Float(digits='Product Unit', help='Positiva si entra al almacén.')
    value = fields.Float(digits=(16, 6), help='Positivo si entra al almacén.')
    balance_qty_wh = fields.Float(digits='Product Unit')
    balance_value_wh = fields.Float(digits=(16, 6))
    balance_qty = fields.Float(digits='Product Unit')
    balance_value = fields.Float(digits=(16, 6))

    _company_product_date_idx = models.Index('(company_id, product_id, date, line_key)')

    def init(self):
        # La vista del kardex lee esta tabla: se rehace cuando ya existe.
        self.env['l10n_pe.kardex.line'].init()

    # ------------------------------------------------------------------
    # Motor
    # ------------------------------------------------------------------
    @api.model
    def _l10n_pe_products(self, company):
        """Productos con costo promedio por almacén en ``company``."""
        products = self.env['product.product'].with_company(company).with_context(active_test=False).search([
            ('is_storable', '=', True),
            '|', ('company_id', '=', False), ('company_id', 'parent_of', company.id),
        ])
        return products.filtered(lambda p: p.cost_method == 'average' and not p.lot_valuated)

    @api.model
    def _l10n_pe_recompute(self, company, date_from=None):
        """Rehace las filas de ``company`` desde ``date_from`` (UTC, o todo)."""
        self.env.flush_all()
        delete = SQL("DELETE FROM %s WHERE company_id = %s", SQL.identifier(self._table), company.id)
        if date_from:
            delete = SQL("%s AND date >= %s", delete, date_from)
        self.env.cr.execute(delete)
        self.invalidate_model()

        products = self._l10n_pe_products(company)
        if not products:
            return
        buckets, totals = self._l10n_pe_opening(company)
        moves = self._l10n_pe_moves(company, products, date_from)
        returned_unit = self._l10n_pe_returned_units(moves)
        uom_by_product = {p.id: p.uom_id for p in products}

        vals_list = []

        def is_zero(product_id, qty):
            return uom_by_product[product_id].is_zero(qty)

        def unit_cost(product_id, bucket, move):
            qty, value, last = buckets[product_id, bucket]
            if qty > 0 and not is_zero(product_id, qty):
                return value / qty
            if last is not None:
                return last
            co_qty, co_value = totals[product_id]
            if co_qty > 0 and not is_zero(product_id, co_qty):
                return co_value / co_qty
            return move['val'] / move['qty'] if move['qty'] else 0.0

        def push(move, k, bucket, qty, value):
            """Mueve el saldo de ``bucket`` y guarda la fila del kardex."""
            product_id = move['product_id']
            b_qty, b_value, last = buckets[product_id, bucket]
            if qty > 0 and (b_qty <= 0 or is_zero(product_id, b_qty)):
                # Desde saldo nulo o negativo, el promedio es el de la entrada
                # (como _run_average_batch de stock_account).
                unit = value / qty
                new_qty = b_qty + qty
                new_value = unit * new_qty
            else:
                new_qty = b_qty + qty
                new_value = b_value + value
            if is_zero(product_id, new_qty):
                new_value = 0.0
            if qty:
                last = abs(value / qty)
            if not is_zero(product_id, new_qty) and new_qty > 0:
                last = new_value / new_qty
            buckets[product_id, bucket] = (new_qty, new_value, last)
            co_qty, co_value = totals[product_id]
            if k == 0:
                co_qty += qty
            co_value += new_value - b_value
            totals[product_id] = (co_qty, co_value)
            vals_list.append({
                'line_key': move['move_id'] * 3 + k,
                'move_id': move['move_id'],
                'product_id': product_id,
                'company_id': company.id,
                'warehouse_id': bucket or False,
                'date': move['date'],
                'qty': qty,
                'value': value,
                'balance_qty_wh': new_qty,
                'balance_value_wh': new_value,
                'balance_qty': co_qty,
                'balance_value': co_value,
            })

        for move in moves:
            product_id, qty = move['product_id'], move['qty']
            src, dst = move['src_wh'] or 0, move['dst_wh'] or 0
            if move['is_in']:
                unit = returned_unit.get(move['origin_returned_move_id'])
                value = unit * qty if unit is not None else move['val']
                push(move, 0, dst, qty, value)
            elif move['is_out']:
                value = unit_cost(product_id, src, move) * qty
                push(move, 0, src, -qty, -value)
                returned_unit[move['move_id']] = value / qty if qty else 0.0
            else:
                value = unit_cost(product_id, src, move) * qty
                push(move, 1, src, -qty, -value)
                push(move, 2, dst, qty, value)

        # sudo: son datos derivados de los movimientos (como la vista del
        # kardex); los rehace cualquier usuario que abre el kardex o valida un
        # movimiento, y la tabla es de solo lectura para todos.
        cost_sudo = self.sudo()
        for batch in split_every(5000, vals_list, list):
            cost_sudo.create(batch)

    @api.model
    def _l10n_pe_opening(self, company):
        """Saldos de cada almacén y de la compañía según las filas guardadas."""
        buckets = defaultdict(lambda: (0.0, 0.0, None))
        totals = defaultdict(lambda: (0.0, 0.0))
        self.env.cr.execute(SQL(
            """
            SELECT DISTINCT ON (product_id, COALESCE(warehouse_id, 0))
                   product_id, COALESCE(warehouse_id, 0), balance_qty_wh, balance_value_wh, qty, value
              FROM %s
             WHERE company_id = %s
          ORDER BY product_id, COALESCE(warehouse_id, 0), date DESC, line_key DESC
            """, SQL.identifier(self._table), company.id))
        for product_id, bucket, qty, value, last_qty, last_value in self.env.cr.fetchall():
            last = value / qty if qty > 0 else (abs(last_value / last_qty) if last_qty else None)
            buckets[product_id, bucket] = (qty, value, last)
        self.env.cr.execute(SQL(
            """
            SELECT DISTINCT ON (product_id) product_id, balance_qty, balance_value
              FROM %s
             WHERE company_id = %s
          ORDER BY product_id, date DESC, line_key DESC
            """, SQL.identifier(self._table), company.id))
        for product_id, qty, value in self.env.cr.fetchall():
            totals[product_id] = (qty, value)
        return buckets, totals

    @api.model
    def _l10n_pe_moves(self, company, products, date_from):
        """Movimientos que mueven el costo por almacén, en orden."""
        conditions = [
            SQL("base.company_id = %s", company.id),
            SQL("base.product_id IN %s", tuple(products.ids)),
            SQL("base.qty <> 0"),
            SQL("""(base.is_in OR base.is_out OR (base.src_valued AND base.dst_valued
                    AND base.src_wh IS DISTINCT FROM base.dst_wh))"""),
        ]
        if date_from:
            conditions.append(SQL("base.date >= %s", date_from))
        self.env.cr.execute(SQL(
            """
            WITH base AS (%s)
            SELECT base.move_id, base.product_id, base.date, base.is_in, base.is_out,
                   base.src_wh, base.dst_wh, base.qty, base.val, base.origin_returned_move_id
              FROM base
             WHERE %s
          ORDER BY base.product_id, base.date, base.move_id
            """, self.env['l10n_pe.kardex.line']._base_query(), SQL(" AND ").join(conditions)))
        return self.env.cr.dictfetchall()

    @api.model
    def _l10n_pe_returned_units(self, moves):
        """Costo unitario guardado de las salidas que se devuelven."""
        origin_ids = {m['origin_returned_move_id'] for m in moves if m['origin_returned_move_id']}
        if not origin_ids:
            return {}
        rows = self.search_fetch([('line_key', 'in', [i * 3 for i in origin_ids])], ['move_id', 'qty', 'value'])
        return {row.move_id.id: row.value / row.qty for row in rows if row.qty}

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    @api.model
    def _l10n_pe_values_at(self, company, at_date=None):
        """Valor por producto (``{product: value}``) al cierre de ``at_date``."""
        query = SQL(
            """
            SELECT DISTINCT ON (product_id) product_id, balance_value
              FROM %s
             WHERE company_id = %s
            """, SQL.identifier(self._table), company.id)
        if at_date:
            end = self.env['res.company']._l10n_pe_day_end(at_date)
            query = SQL("%s AND date <= %s", query, end)
        self.env.cr.execute(SQL("%s ORDER BY product_id, date DESC, line_key DESC", query))
        Product = self.env['product.product']
        return {Product.browse(product_id): value for product_id, value in self.env.cr.fetchall()}

    @api.model
    def _cron_refresh(self):
        self.env['res.company'].search([
            ('l10n_pe_wh_cost', '=', True), ('l10n_pe_wh_cost_dirty_date', '!=', False),
        ])._l10n_pe_wh_cost_refresh()
