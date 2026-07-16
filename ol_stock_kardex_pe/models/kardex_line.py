import re

from odoo import api, fields, models, tools

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


class L10nPeKardexLine(models.Model):
    """Kardex SUNAT como **vista SQL** sobre stock.move.

    No se puebla ningún registro: el saldo corrido (cantidad, valor y costo
    unitario) se calcula con window functions de PostgreSQL, tanto a nivel
    consolidado (producto+compañía) como por almacén (producto+almacén). Los
    campos de documento (Tabla 10, serie, folio) y el tipo de operación
    (Tabla 12) son calculados no almacenados, resueltos por lote solo para las
    filas efectivamente leídas.
    """
    _name = 'l10n_pe.kardex.line'
    _description = 'Kardex SUNAT (línea)'
    _auto = False
    _order = 'product_id, date, id'

    move_id = fields.Many2one('stock.move', string='Movimiento', readonly=True)
    product_id = fields.Many2one('product.product', string='Producto', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    picking_id = fields.Many2one('stock.picking', string='Transferencia', readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Almacén', readonly=True)
    date = fields.Datetime(string='Fecha', readonly=True)

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

    # Campos SUNAT resueltos por lote (no almacenados)
    document_type_code = fields.Char(string='Tipo (Tabla 10)', compute='_compute_document')
    serie = fields.Char(string='Serie', compute='_compute_document')
    folio = fields.Char(string='Número', compute='_compute_document')
    account_move_id = fields.Many2one('account.move', string='Comprobante', compute='_compute_document')
    operation_type = fields.Char(string='Operación (Tabla 12)', compute='_compute_operation_type')

    # ------------------------------------------------------------------
    # Vista SQL
    # ------------------------------------------------------------------
    def _query(self):
        return """
            SELECT
                s.*,
                CASE WHEN s.balance_qty <> 0
                     THEN s.balance_value / s.balance_qty ELSE 0.0 END AS balance_unit_cost,
                CASE WHEN s.balance_qty_wh <> 0
                     THEN s.balance_value_wh / s.balance_qty_wh ELSE 0.0 END AS balance_unit_cost_wh
            FROM (
                SELECT
                    b.id AS id,
                    b.id AS move_id,
                    b.product_id AS product_id,
                    b.company_id AS company_id,
                    b.picking_id AS picking_id,
                    b.warehouse_id AS warehouse_id,
                    b.date AS date,
                    CASE WHEN b.is_in THEN b.qty ELSE 0.0 END AS qty_in,
                    CASE WHEN b.is_in AND b.qty <> 0 THEN b.val / b.qty ELSE 0.0 END AS cost_unit_in,
                    CASE WHEN b.is_in THEN b.val ELSE 0.0 END AS cost_total_in,
                    CASE WHEN b.is_out THEN b.qty ELSE 0.0 END AS qty_out,
                    CASE WHEN b.is_out AND b.qty <> 0 THEN b.val / b.qty ELSE 0.0 END AS cost_unit_out,
                    CASE WHEN b.is_out THEN b.val ELSE 0.0 END AS cost_total_out,
                    SUM(b.signed_qty) OVER w_co AS balance_qty,
                    SUM(b.signed_val) OVER w_co AS balance_value,
                    SUM(b.signed_qty) OVER w_wh AS balance_qty_wh,
                    SUM(b.signed_val) OVER w_wh AS balance_value_wh
                FROM (
                    SELECT
                        sm.id, sm.product_id, sm.company_id, sm.picking_id,
                        sm.warehouse_id, sm.date, sm.is_in, sm.is_out,
                        sm.product_qty AS qty,
                        COALESCE(ABS(sm.value), 0.0) AS val,
                        CASE WHEN sm.is_in THEN sm.product_qty ELSE -sm.product_qty END AS signed_qty,
                        CASE WHEN sm.is_in THEN COALESCE(ABS(sm.value), 0.0)
                             ELSE -COALESCE(ABS(sm.value), 0.0) END AS signed_val
                    FROM stock_move sm
                    WHERE sm.state = 'done' AND (sm.is_in OR sm.is_out)
                ) b
                WINDOW
                    w_co AS (PARTITION BY b.product_id, b.company_id
                             ORDER BY b.date, b.id
                             ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW),
                    w_wh AS (PARTITION BY b.product_id, b.warehouse_id, b.company_id
                             ORDER BY b.date, b.id
                             ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
            ) s
        """

    def init(self):
        # Una encarnación previa de este modelo era TransientModel y creó una
        # TABLA con este nombre. Detectamos el tipo real para borrarlo bien
        # (DROP TABLE falla sobre una vista y viceversa).
        self.env.cr.execute(
            "SELECT relkind FROM pg_class WHERE relname = %s", (self._table,))
        row = self.env.cr.fetchone()
        if row and row[0] == 'r':
            self.env.cr.execute("DROP TABLE IF EXISTS %s CASCADE" % self._table)
        else:
            tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            "CREATE OR REPLACE VIEW %s AS (%s)" % (self._table, self._query()))

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

    @api.depends('move_id')
    def _compute_document(self):
        has_latam = 'l10n_latam_document_number' in self.env['stock.picking']._fields
        for line in self:
            move = line.move_id
            invoice = move.sale_line_id.invoice_lines.move_id[:1]
            bill = move.purchase_line_id.invoice_lines.move_id[:1]
            doc = invoice or bill
            if has_latam and move.picking_id.l10n_latam_document_number:
                number = move.picking_id.l10n_latam_document_number
            elif doc:
                number = doc.l10n_latam_document_number or doc.name or ''
            else:
                number = move.picking_id.name or move.reference or ''
            sf = self._get_serie_folio(number)
            line.document_type_code = doc.l10n_latam_document_type_id.code or '00'
            line.serie = (sf['serie'] or '').replace(' ', '').replace('/', '')
            line.folio = (sf['folio'] or '').replace(' ', '')
            line.account_move_id = doc.id if doc else False

    @api.depends('move_id')
    def _compute_operation_type(self):
        for line in self:
            move = line.move_id
            op = move.picking_id.l10n_pe_operation_type
            if op:
                line.operation_type = op.zfill(2)
                continue
            if move.scrapped:
                line.operation_type = '13'
                continue
            direction = 'in' if move.is_in else 'out'
            other = move.location_id if move.is_in else move.location_dest_id
            line.operation_type = OPERATION_FALLBACK[direction].get(other.usage, '99')

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
