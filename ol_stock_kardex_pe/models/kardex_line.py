import re

from odoo import api, fields, models, tools
from odoo.tools import SQL

# Fallback de Tabla 12 (tipo de operación) según el usage de la contraparte,
# cuando el picking no tiene l10n_pe_operation_type.
OPERATION_FALLBACK = {
    'in': {
        'supplier': '02', 'customer': '24', 'inventory': '28',
        'production': '19', 'internal': '21', 'transit': '21',
    },
    'out': {
        'supplier': '25', 'customer': '01', 'inventory': '28',
        'production': '10', 'internal': '11', 'transit': '11',
    },
}

# Tabla 12 de venta, compra, consignación y devoluciones: sin comprobante, el
# documento de traslado es la guía de remisión (Tabla 10 = 09), como en el PLE
# de l10n_pe_reports_stock.
GUIA_OPERATIONS = ('01', '02', '03', '04', '05', '06')

# Una ubicación se valoriza si pertenece a una compañía y es interna o de
# tránsito (stock.location._should_be_valued en stock_account).
_VALUED = "({alias}.company_id IS NOT NULL AND {alias}.usage IN ('internal', 'transit'))"


class L10nPeKardexLine(models.Model):
    """Kardex SUNAT como **vista SQL** sobre stock.move.

    No se puebla ningún registro: el saldo corrido (cantidad, valor y costo
    unitario) se calcula con window functions de PostgreSQL, tanto a nivel
    consolidado (producto+compañía) como por almacén (producto+almacén). Los
    campos de documento (Tabla 10, serie, folio) y el tipo de operación
    (Tabla 12) son calculados no almacenados, resueltos por lote solo para las
    filas efectivamente leídas.

    Filas (``id = move_id * 3 + k``):

    - ``k = 0``: movimiento valorizado (``is_in``/``is_out``). Cantidad =
      cantidad valorizada de sus líneas (como ``_get_valued_qty``), no la
      demanda.
    - ``k = 1`` / ``k = 2``: salida / entrada de un traslado entre almacenes de
      la misma compañía (``is_internal``). No mueven el saldo consolidado; en
      el saldo por almacén se valoran al costo unitario consolidado corriente.
    """
    _name = 'l10n_pe.kardex.line'
    _description = 'Kardex SUNAT (línea)'
    _auto = False
    _order = 'product_id, date, id'
    # Campos que lee la vista: el ORM los vuelca a la base antes de buscar en
    # ella (sin esto, valores recién calculados como stock.location.warehouse_id
    # o stock.move.is_in podrían no estar aún en la base).
    _depends = {
        'stock.move': [
            'product_id', 'company_id', 'picking_id', 'date', 'state', 'is_in',
            'is_out', 'value', 'location_id', 'location_dest_id',
        ],
        'stock.move.line': [
            'move_id', 'picked', 'owner_id', 'quantity_product_uom',
            'location_id', 'location_dest_id',
        ],
        'stock.location': ['company_id', 'usage', 'warehouse_id'],
        'res.company': ['partner_id'],
    }

    move_id = fields.Many2one('stock.move', string='Movimiento', readonly=True)
    product_id = fields.Many2one('product.product', string='Producto', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    picking_id = fields.Many2one('stock.picking', string='Transferencia', readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Almacén', readonly=True)
    date = fields.Datetime(string='Fecha', readonly=True)
    direction = fields.Selection(
        [('in', 'Entrada'), ('out', 'Salida')], string='Sentido', readonly=True)
    is_internal = fields.Boolean(string='Traslado entre almacenes', readonly=True)

    qty_in = fields.Float(string='Entrada', digits='Product Unit', readonly=True)
    cost_unit_in = fields.Float(string='C.U. entrada', digits='Product Price', readonly=True)
    cost_total_in = fields.Float(string='C.T. entrada', digits=(16, 2), readonly=True)
    qty_out = fields.Float(string='Salida', digits='Product Unit', readonly=True)
    cost_unit_out = fields.Float(string='C.U. salida', digits='Product Price', readonly=True)
    cost_total_out = fields.Float(string='C.T. salida', digits=(16, 2), readonly=True)

    # Saldo corrido consolidado (producto + compañía)
    balance_qty = fields.Float(string='Saldo', digits='Product Unit', readonly=True)
    balance_value = fields.Float(string='C.T. saldo', digits=(16, 2), readonly=True)
    balance_unit_cost = fields.Float(string='C.U. saldo', digits='Product Price', readonly=True)
    # Saldo corrido por almacén (producto + almacén)
    balance_qty_wh = fields.Float(string='Saldo (almacén)', digits='Product Unit', readonly=True)
    balance_value_wh = fields.Float(string='C.T. saldo (almacén)', digits=(16, 2), readonly=True)
    balance_unit_cost_wh = fields.Float(string='C.U. saldo (almacén)', digits='Product Price', readonly=True)

    # Campos SUNAT resueltos por lote (no almacenados). compute_sudo: leen
    # líneas de venta/compra y facturas, que un usuario solo de Inventario no
    # puede leer; solo se exponen códigos y números del comprobante.
    document_type_code = fields.Char(
        string='Tipo (Tabla 10)', compute='_compute_document', compute_sudo=True)
    serie = fields.Char(string='Serie', compute='_compute_document', compute_sudo=True)
    folio = fields.Char(string='Número', compute='_compute_document', compute_sudo=True)
    account_move_id = fields.Many2one(
        'account.move', string='Comprobante', compute='_compute_document', compute_sudo=True)
    operation_type = fields.Char(
        string='Operación (Tabla 12)', compute='_compute_operation_type', compute_sudo=True)

    # ------------------------------------------------------------------
    # Vista SQL
    # ------------------------------------------------------------------
    def _query(self):
        src_valued = SQL(_VALUED.format(alias='src'))
        dst_valued = SQL(_VALUED.format(alias='dst'))
        sl_valued = SQL(_VALUED.format(alias='sl'))
        dl_valued = SQL(_VALUED.format(alias='dl'))
        return SQL("""
            WITH base AS (
                SELECT
                    sm.id AS move_id, sm.product_id, sm.company_id, sm.picking_id,
                    sm.date,
                    COALESCE(sm.is_in, FALSE) AS is_in, COALESCE(sm.is_out, FALSE) AS is_out,
                    src.warehouse_id AS src_wh, dst.warehouse_id AS dst_wh,
                    %(src_valued)s AS src_valued, %(dst_valued)s AS dst_valued,
                    COALESCE(ABS(sm.value), 0.0) AS val,
                    -- Cantidad valorizada (stock.move._get_valued_qty): líneas
                    -- recogidas, sin propietario ajeno, que entran o salen del
                    -- inventario valorizado. No la demanda (product_qty).
                    (SELECT COALESCE(SUM(sml.quantity_product_uom), 0.0)
                       FROM stock_move_line sml
                       JOIN stock_location sl ON sl.id = sml.location_id
                       JOIN stock_location dl ON dl.id = sml.location_dest_id
                       JOIN res_company c ON c.id = sm.company_id
                      WHERE sml.move_id = sm.id
                        AND sml.picked
                        AND (sml.owner_id IS NULL OR sml.owner_id = c.partner_id)
                        AND (NOT COALESCE(sm.is_in, FALSE) OR (NOT %(sl_valued)s AND %(dl_valued)s))
                        AND (NOT COALESCE(sm.is_out, FALSE) OR (%(sl_valued)s AND NOT %(dl_valued)s))
                    ) AS qty
                FROM stock_move sm
                JOIN stock_location src ON src.id = sm.location_id
                JOIN stock_location dst ON dst.id = sm.location_dest_id
                WHERE sm.state = 'done'
            ),
            krows AS (
                SELECT move_id * 3 AS id, move_id, product_id, company_id, picking_id, date,
                       CASE WHEN is_in THEN dst_wh ELSE src_wh END AS warehouse_id,
                       CASE WHEN is_in THEN 'in' ELSE 'out' END AS direction,
                       FALSE AS is_internal, qty, val
                  FROM base WHERE is_in OR is_out
                UNION ALL
                SELECT move_id * 3 + 1, move_id, product_id, company_id, picking_id, date,
                       src_wh, 'out', TRUE, qty, 0.0
                  FROM base
                 WHERE NOT is_in AND NOT is_out AND src_valued AND dst_valued
                   AND src_wh IS NOT NULL AND src_wh IS DISTINCT FROM dst_wh
                UNION ALL
                SELECT move_id * 3 + 2, move_id, product_id, company_id, picking_id, date,
                       dst_wh, 'in', TRUE, qty, 0.0
                  FROM base
                 WHERE NOT is_in AND NOT is_out AND src_valued AND dst_valued
                   AND dst_wh IS NOT NULL AND dst_wh IS DISTINCT FROM src_wh
            ),
            co AS (
                SELECT r.*,
                       SUM(CASE WHEN r.is_internal THEN 0.0
                                WHEN r.direction = 'in' THEN r.qty ELSE -r.qty END) OVER w_co AS balance_qty,
                       SUM(CASE WHEN r.is_internal THEN 0.0
                                WHEN r.direction = 'in' THEN r.val ELSE -r.val END) OVER w_co AS balance_value
                  FROM krows r
                WINDOW w_co AS (PARTITION BY r.product_id, r.company_id
                                ORDER BY r.date, r.id
                                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
            ),
            ev AS (
                SELECT co.*,
                       CASE WHEN NOT co.is_internal THEN co.val
                            WHEN co.balance_qty <> 0 THEN co.qty * co.balance_value / co.balance_qty
                            ELSE 0.0 END AS val_eff
                  FROM co
            ),
            wh AS (
                SELECT ev.*,
                       SUM(CASE WHEN ev.direction = 'in' THEN ev.qty ELSE -ev.qty END) OVER w_wh AS balance_qty_wh,
                       SUM(CASE WHEN ev.direction = 'in' THEN ev.val_eff ELSE -ev.val_eff END) OVER w_wh AS balance_value_wh
                  FROM ev
                WINDOW w_wh AS (PARTITION BY ev.product_id, ev.warehouse_id, ev.company_id
                                ORDER BY ev.date, ev.id
                                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
            )
            SELECT
                id, move_id, product_id, company_id, picking_id, warehouse_id, date,
                direction, is_internal,
                CASE WHEN direction = 'in' THEN qty ELSE 0.0 END AS qty_in,
                CASE WHEN direction = 'in' AND qty <> 0 THEN val_eff / qty ELSE 0.0 END AS cost_unit_in,
                CASE WHEN direction = 'in' THEN val_eff ELSE 0.0 END AS cost_total_in,
                CASE WHEN direction = 'out' THEN qty ELSE 0.0 END AS qty_out,
                CASE WHEN direction = 'out' AND qty <> 0 THEN val_eff / qty ELSE 0.0 END AS cost_unit_out,
                CASE WHEN direction = 'out' THEN val_eff ELSE 0.0 END AS cost_total_out,
                balance_qty, balance_value,
                CASE WHEN balance_qty <> 0 THEN balance_value / balance_qty ELSE 0.0 END AS balance_unit_cost,
                balance_qty_wh, balance_value_wh,
                CASE WHEN balance_qty_wh <> 0 THEN balance_value_wh / balance_qty_wh ELSE 0.0 END AS balance_unit_cost_wh
            FROM wh
        """, src_valued=src_valued, dst_valued=dst_valued,
             sl_valued=sl_valued, dl_valued=dl_valued)

    def init(self):
        # Una encarnación previa de este modelo era TransientModel y creó una
        # TABLA con este nombre. Detectamos el tipo real para borrarlo bien
        # (DROP TABLE falla sobre una vista y viceversa).
        self.env.cr.execute(SQL(
            "SELECT relkind FROM pg_class WHERE relname = %s", self._table))
        row = self.env.cr.fetchone()
        if row and row[0] == 'r':
            self.env.cr.execute(SQL(
                "DROP TABLE IF EXISTS %s CASCADE", SQL.identifier(self._table)))
        else:
            tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(SQL(
            "CREATE OR REPLACE VIEW %s AS (%s)",
            SQL.identifier(self._table), self._query()))

    # ------------------------------------------------------------------
    # Campos SUNAT (por lote)
    # ------------------------------------------------------------------
    @api.model
    def _get_serie_folio(self, number):
        values = {'serie': '', 'folio': ''}
        matches = list(re.finditer(r"\d+", number or ''))
        if matches:
            last = matches[-1]
            values['serie'] = (number[:last.start()] or '').replace('-', '')
            values['folio'] = last.group() or ''
        return values

    @api.depends('move_id', 'direction', 'is_internal')
    def _compute_document(self):
        has_latam = 'l10n_latam_document_number' in self.env['stock.picking']._fields
        for line in self:
            move = line.move_id
            # sorted('id'): account.move se ordena por fecha desc; sin esto
            # [:1] tomaría la última factura (p. ej. una nota de crédito).
            invoice = move.sale_line_id.invoice_lines.move_id.sorted('id')[:1]
            bill = move.purchase_line_id.invoice_lines.move_id.sorted('id')[:1]
            doc = invoice or bill
            delivery_number = has_latam and move.picking_id.l10n_latam_document_number
            if delivery_number:
                number = delivery_number
            elif doc:
                number = doc.l10n_latam_document_number or doc.name or ''
            else:
                number = move.picking_id.name or move.reference or ''
            sf = self._get_serie_folio(number)
            code = doc.l10n_latam_document_type_id.code or '00'
            if delivery_number or (code == '00' and line.operation_type in GUIA_OPERATIONS):
                code = '09'
            line.document_type_code = code
            line.serie = (sf['serie'] or '').replace(' ', '').replace('/', '')
            line.folio = (sf['folio'] or '').replace(' ', '')
            line.account_move_id = doc.id if doc else False

    @api.depends('move_id', 'direction', 'is_internal')
    def _compute_operation_type(self):
        for line in self:
            move = line.move_id
            if line.is_internal:
                # Traslado entre almacenes: salida 11 en el origen, entrada 21
                # en el destino (Tabla 12).
                line.operation_type = '11' if line.direction == 'out' else '21'
                continue
            op = move.picking_id.l10n_pe_operation_type
            if op:
                line.operation_type = op.zfill(2)
                continue
            if move.scrap_id:
                line.operation_type = '13'
                continue
            other = move.location_id if line.direction == 'in' else move.location_dest_id
            line.operation_type = OPERATION_FALLBACK[line.direction or 'out'].get(other.usage, '99')

    def action_open_origin(self):
        self.ensure_one()
        target = self.account_move_id or self.picking_id or self.move_id
        if not target:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': target._name,
            'res_id': target.id,
            'view_mode': 'form',
        }
