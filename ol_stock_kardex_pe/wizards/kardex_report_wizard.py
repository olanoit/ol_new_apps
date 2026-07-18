import base64
import calendar
from datetime import date, datetime, time
from types import SimpleNamespace

from dateutil.relativedelta import relativedelta
from werkzeug.urls import url_encode

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Date, Domain

from ..reports.kardex_xlsx import build_kardex_xlsx

VALUATION_METHOD_LABELS = {
    'average': 'PROMEDIO PONDERADO',
    'fifo': 'PEPS (FIFO)',
    'standard': 'COSTO ESTÁNDAR',
}

MONTH_SELECTION = [
    ('1', 'Enero'), ('2', 'Febrero'), ('3', 'Marzo'), ('4', 'Abril'),
    ('5', 'Mayo'), ('6', 'Junio'), ('7', 'Julio'), ('8', 'Agosto'),
    ('9', 'Setiembre'), ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre'),
]

# Tabla 5 SUNAT (tipo de existencia) en español, indexada por el código del
# Selection de l10n_pe_reports_stock (cuyas etiquetas están en inglés).
SUNAT_TABLE5_ES = {
    '1': 'Mercaderías', '2': 'Productos terminados', '3': 'Materias primas',
    '4': 'Envases', '5': 'Materiales auxiliares', '6': 'Suministros',
    '7': 'Repuestos', '8': 'Embalajes', '9': 'Subproductos',
    '10': 'Desechos y desperdicios',
    '91': 'Otros 1', '92': 'Otros 2', '93': 'Otros 3', '94': 'Otros 4',
    '95': 'Otros 5', '96': 'Otros 6', '97': 'Otros 7', '98': 'Otros 8',
    '99': 'Otros',
}


class L10nPeKardexReportWizard(models.TransientModel):
    _name = 'l10n_pe.kardex.report.wizard'
    _description = 'Kardex SUNAT (Formato 13.1 / 12.1)'

    @api.model
    def default_get(self, fields_list):
        results = super().default_get(fields_list)
        if self.env.company.country_code != 'PE':
            raise UserError(self.env._(
                'Esta opción solo está disponible para compañías peruanas.'))
        date_from = Date.today().replace(day=1)
        results.setdefault('date_from', date_from)
        results.setdefault('date_to', date_from + relativedelta(months=1, days=-1))
        results.update(self._defaults_from_context())
        return results

    @api.model
    def _defaults_from_context(self):
        """Precarga productos/categorías cuando el asistente se abre desde el
        botón «Ver Kardex» de un producto, plantilla o categoría."""
        ctx = self.env.context
        model = ctx.get('active_model')
        active_ids = ctx.get('active_ids') or (
            [ctx['active_id']] if ctx.get('active_id') else [])
        if not active_ids:
            return {}
        if model == 'product.product':
            return {'product_ids': [(6, 0, active_ids)]}
        if model == 'product.template':
            variants = self.env['product.template'].browse(
                active_ids).product_variant_ids
            return {'product_ids': [(6, 0, variants.ids)]}
        if model == 'product.category':
            return {'categ_ids': [(6, 0, active_ids)]}
        return {}

    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True,
        default=lambda self: self.env.company)
    period_range = fields.Selection(
        [('month', 'Por mes'), ('dates', 'Rango de fechas')],
        string='Período', default='month', required=True)
    month = fields.Selection(
        MONTH_SELECTION, string='Mes',
        default=lambda self: str(fields.Date.context_today(self).month))
    year = fields.Char(
        'Año', default=lambda self: str(fields.Date.context_today(self).year))
    date_from = fields.Date(string='Desde', required=True)
    date_to = fields.Date(string='Hasta', required=True)
    report_type = fields.Selection(
        [
            ('1301', 'Formato 13.1 — Inventario Permanente Valorizado'),
            ('1201', 'Formato 12.1 — Inventario Permanente en Unidades Físicas'),
        ],
        string='Formato', required=True, default='1301')
    warehouse_ids = fields.Many2many(
        'stock.warehouse', string='Almacenes',
        domain="[('company_id', '=', company_id)]",
        help='Vacío = todos los almacenes de la compañía.')
    product_ids = fields.Many2many(
        'product.product', string='Productos',
        domain=[('is_storable', '=', True)],
        help='Vacío = todos los productos almacenables.')
    categ_ids = fields.Many2many(
        'product.category', string='Categorías',
        help='Filtro alternativo cuando no se seleccionan productos.')
    group_by_warehouse = fields.Boolean(
        string='Kardex por almacén',
        help='Genera una sección/hoja por almacén con su propio saldo corrido. '
             'El costo por almacén es aproximado: Odoo valoriza por compañía. '
             'Desmarcado: kardex consolidado de la compañía, cuadra con el TXT PLE.')
    include_no_movement = fields.Boolean(
        string='Incluir productos sin movimientos', default=True,
        help='Incluye productos con saldo inicial distinto de cero aunque no '
             'tengan movimientos en el período.')

    report_data = fields.Binary('Archivo', readonly=True, attachment=False)
    report_filename = fields.Char(string='Nombre de archivo', readonly=True)
    mimetype = fields.Char(readonly=True)

    # -------------------------------------------------------------------------
    # Período
    # -------------------------------------------------------------------------

    @api.onchange('period_range', 'month', 'year')
    def _onchange_period(self):
        for rec in self:
            rec._sync_period_dates()

    def _sync_period_dates(self):
        """En modo «Por mes» calcula date_from/date_to a partir de mes/año."""
        self.ensure_one()
        if self.period_range != 'month' or not (self.month and self.year):
            return
        try:
            y, m = int(self.year), int(self.month)
        except (TypeError, ValueError):
            return
        last_day = calendar.monthrange(y, m)[1]
        self.date_from = date(y, m, 1)
        self.date_to = date(y, m, last_day)

    # -------------------------------------------------------------------------
    # Acciones
    # -------------------------------------------------------------------------

    def action_view(self):
        """Abre la vista SQL del kardex filtrada; no se puebla nada."""
        self.ensure_one()
        self._sync_period_dates()
        group_by = ['warehouse_id', 'product_id'] if self.group_by_warehouse else ['product_id']
        return {
            'name': self.env._('Kardex %(fmt)s (%(df)s a %(dt)s)',
                               fmt='13.1' if self.report_type == '1301' else '12.1',
                               df=self.date_from, dt=self.date_to),
            'type': 'ir.actions.act_window',
            'res_model': 'l10n_pe.kardex.line',
            'view_mode': 'list',
            'domain': self._get_line_domain(None),
            'context': {
                'group_by': group_by,
                'kardex_physical': self.report_type == '1201',
                'kardex_by_warehouse': self.group_by_warehouse,
            },
        }

    def action_export_xlsx(self):
        self.ensure_one()
        self._sync_period_dates()
        content = build_kardex_xlsx(self)
        self.write({
            'report_data': base64.b64encode(content),
            'report_filename': self._get_export_filename('xlsx'),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return self._download_action()

    def action_print_pdf(self):
        self.ensure_one()
        self._sync_period_dates()
        return self.env.ref('ol_stock_kardex_pe.action_report_kardex').report_action(self)

    def action_generate_background(self):
        """Encola la generación del archivo en segundo plano."""
        self.ensure_one()
        self._sync_period_dates()
        report = self.env['l10n_pe.kardex.report'].create(self._background_vals())
        report._enqueue()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': self.env._('Generación en segundo plano'),
                'message': self.env._(
                    'El kardex se está generando. Lo encontrarás en '
                    'Inventario ▸ Informes ▸ Kardex SUNAT · Generados.'),
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': 'l10n_pe.kardex.report',
                    'res_id': report.id,
                    'view_mode': 'form',
                },
            },
        }

    def _background_vals(self):
        return {
            'company_id': self.company_id.id,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'report_type': self.report_type,
            'group_by_warehouse': self.group_by_warehouse,
            'include_no_movement': self.include_no_movement,
            'file_format': 'xlsx',
            'warehouse_ids': [(6, 0, self.warehouse_ids.ids)],
            'product_ids': [(6, 0, self.product_ids.ids)],
            'categ_ids': [(6, 0, self.categ_ids.ids)],
        }

    def _download_action(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/?' + url_encode({
                'model': self._name,
                'id': self.id,
                'filename_field': 'report_filename',
                'field': 'report_data',
                'download': 'true',
            }),
            'target': 'new',
        }

    def _get_export_filename(self, extension):
        return 'KARDEX_%s_%s_%s%02d.%s' % (
            self.report_type, self.company_id.vat or self.company_id.id,
            self.date_from.year, self.date_from.month, extension)

    # -------------------------------------------------------------------------
    # Consulta de la vista SQL
    # -------------------------------------------------------------------------

    def _get_scopes(self):
        self.ensure_one()
        if not self.group_by_warehouse:
            return [None]
        warehouses = self.warehouse_ids or self.env['stock.warehouse'].search(
            [('company_id', '=', self.company_id.id)])
        return list(warehouses)

    def _candidate_product_ids(self):
        if self.product_ids:
            return self.product_ids.ids
        if self.categ_ids:
            return self.env['product.product'].search(
                [('categ_id', 'child_of', self.categ_ids.ids)]).ids
        return None

    def _get_line_domain(self, warehouse):
        dt_from = datetime.combine(self.date_from, time.min)
        dt_to = datetime.combine(self.date_to, time.max)
        domain = Domain([
            ('company_id', '=', self.company_id.id),
            ('date', '>=', dt_from),
            ('date', '<=', dt_to),
        ])
        products = self._candidate_product_ids()
        if products is not None:
            domain &= Domain([('product_id', 'in', products)])
        if warehouse:
            domain &= Domain([('warehouse_id', '=', warehouse.id)])
        elif self.warehouse_ids:
            domain &= Domain([('warehouse_id', 'in', self.warehouse_ids.ids)])
        return domain

    def _get_opening_balances(self, warehouse):
        """{product_id: (saldo_qty, saldo_value)} justo antes de date_from,
        vía DISTINCT ON sobre la vista (una consulta, sin recorrer historia)."""
        qty_col = 'balance_qty_wh' if warehouse else 'balance_qty'
        val_col = 'balance_value_wh' if warehouse else 'balance_value'
        params = [self.company_id.id, datetime.combine(self.date_from, time.min)]
        where = "company_id = %s AND date < %s"
        products = self._candidate_product_ids()
        if products is not None:
            if not products:
                return {}
            where += " AND product_id IN %s"
            params.append(tuple(products))
        if warehouse:
            where += " AND warehouse_id = %s"
            params.append(warehouse.id)
        elif self.warehouse_ids:
            where += " AND warehouse_id IN %s"
            params.append(tuple(self.warehouse_ids.ids))
        self.env.cr.execute(
            "SELECT DISTINCT ON (product_id) product_id, %s, %s "
            "FROM l10n_pe_kardex_line WHERE %s "
            "ORDER BY product_id, date DESC, id DESC"
            % (qty_col, val_col, where), params)
        return {r[0]: (r[1], r[2]) for r in self.env.cr.fetchall()}

    # -------------------------------------------------------------------------
    # Estructura de datos para los renderizadores (XLSX / QWeb)
    # -------------------------------------------------------------------------

    @staticmethod
    def _row(**kw):
        base = dict(
            line_type='move', date=None, document_type_code='', serie='',
            folio='', operation_type='', qty_in=0.0, cost_unit_in=0.0,
            cost_total_in=0.0, qty_out=0.0, cost_unit_out=0.0, cost_total_out=0.0,
            balance_qty=0.0, balance_unit_cost=0.0, balance_value=0.0)
        base.update(kw)
        return SimpleNamespace(**base)

    def _get_report_data(self):
        self.ensure_one()
        valued = self.report_type == '1301'
        Line = self.env['l10n_pe.kardex.line']
        scopes = []
        for warehouse in self._get_scopes():
            use_wh = bool(warehouse)
            lines = Line.search(self._get_line_domain(warehouse))
            opening = self._get_opening_balances(warehouse)

            products = lines.product_id
            if self.include_no_movement:
                extra_ids = [pid for pid, (q, _v) in opening.items()
                             if not products.browse(pid).uom_id.is_zero(q)]
                products |= self.env['product.product'].browse(extra_ids)

            if warehouse:
                code = warehouse.l10n_pe_anexo_establishment_code or '0000'
                establishment = '%s - %s' % (code, warehouse.name)
                scope_name = warehouse.name
            else:
                partner = self.company_id.partner_id
                parts = [partner.street, partner.l10n_pe_district_name or partner.city,
                         partner.state_id.name]
                establishment = ', '.join(p for p in parts if p) or '0000'
                scope_name = self.env._('Consolidado')

            products_data = []
            for product in products.sorted(lambda p: (p.default_code or '', p.name)):
                plines = lines.filtered(lambda l: l.product_id == product)
                oq, ov = opening.get(product.id, (0.0, 0.0))
                rows = [self._opening_row(product, oq, ov, valued)]
                t_qin = t_vin = t_qout = t_vout = 0.0
                bal_qty, bal_val = oq, ov
                for l in plines:
                    bal_qty = l.balance_qty_wh if use_wh else l.balance_qty
                    bal_val = l.balance_value_wh if use_wh else l.balance_value
                    bal_uc = l.balance_unit_cost_wh if use_wh else l.balance_unit_cost
                    rows.append(self._row(
                        line_type='move', date=l.date,
                        document_type_code=l.document_type_code,
                        serie=l.serie, folio=l.folio, operation_type=l.operation_type,
                        qty_in=l.qty_in, qty_out=l.qty_out,
                        cost_unit_in=l.cost_unit_in if valued else 0.0,
                        cost_total_in=l.cost_total_in if valued else 0.0,
                        cost_unit_out=l.cost_unit_out if valued else 0.0,
                        cost_total_out=l.cost_total_out if valued else 0.0,
                        balance_qty=bal_qty,
                        balance_unit_cost=bal_uc if valued else 0.0,
                        balance_value=bal_val if valued else 0.0))
                    t_qin += l.qty_in
                    t_vin += l.cost_total_in
                    t_qout += l.qty_out
                    t_vout += l.cost_total_out
                total = self._row(
                    line_type='total', qty_in=t_qin, qty_out=t_qout,
                    cost_total_in=t_vin if valued else 0.0,
                    cost_total_out=t_vout if valued else 0.0, balance_qty=bal_qty,
                    balance_unit_cost=(bal_val / bal_qty) if (valued and bal_qty) else 0.0,
                    balance_value=bal_val if valued else 0.0)

                template = product.product_tmpl_id
                existence_code = template.l10n_pe_type_of_existence or '99'
                products_data.append({
                    'product': product,
                    'code': product.default_code or '',
                    'description': product.name,
                    'existence_type': '%s - %s' % (
                        existence_code.zfill(2), SUNAT_TABLE5_ES.get(existence_code, '')),
                    'uom_code': product.uom_id.l10n_pe_edi_measure_unit_code or '',
                    'uom_name': product.uom_id.name,
                    'valuation_method': VALUATION_METHOD_LABELS.get(
                        product.categ_id.property_cost_method, ''),
                    'lines': rows,
                    'total_line': total,
                })
            scopes.append({
                'warehouse': warehouse, 'name': scope_name,
                'establishment': establishment, 'products': products_data,
            })
        return scopes

    def _opening_row(self, product, oq, ov, valued):
        return self._row(
            line_type='opening',
            date=datetime.combine(self.date_from, time.min),
            document_type_code='00', operation_type='16',
            qty_in=oq if oq > 0 else 0.0,
            cost_unit_in=(ov / oq) if (valued and oq) else 0.0,
            cost_total_in=ov if (valued and oq > 0) else 0.0,
            balance_qty=oq,
            balance_unit_cost=(ov / oq) if (valued and oq) else 0.0,
            balance_value=ov if valued else 0.0)

    def _get_report_header(self):
        self.ensure_one()
        return {
            'period': '%s%02d' % (self.date_from.year, self.date_from.month),
            'date_from': self.date_from,
            'date_to': self.date_to,
            'ruc': self.company_id.vat or '',
            'company_name': self.company_id.name,
            'valued': self.report_type == '1301',
            'title': (
                'FORMATO 13.1: "REGISTRO DE INVENTARIO PERMANENTE VALORIZADO '
                '- DETALLE DEL INVENTARIO VALORIZADO"'
                if self.report_type == '1301' else
                'FORMATO 12.1: "REGISTRO DEL INVENTARIO PERMANENTE EN '
                'UNIDADES FÍSICAS - DETALLE DEL INVENTARIO PERMANENTE EN '
                'UNIDADES FÍSICAS"'),
        }
