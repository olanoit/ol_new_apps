import base64
from collections import defaultdict
from datetime import datetime, time, timedelta

from dateutil.relativedelta import relativedelta
from werkzeug.urls import url_encode

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Date, Domain
from odoo.tools import float_is_zero

from ..reports.kardex_xlsx import build_kardex_xlsx

# Usages "externos" al inventario: mismo universo que usa el wizard PLE de
# l10n_pe_reports_stock para los TXT 12.1/13.1.
EXTERNAL_USAGES = ('supplier', 'customer', 'inventory', 'production')

# Fallback de Tabla 12 (tipo de operación) según el usage de la contraparte,
# cuando el picking no tiene l10n_pe_operation_type (scrap, ajustes, etc.).
OPERATION_FALLBACK = {
    'in': {
        'supplier': '02',    # Compra nacional
        'customer': '24',    # Devolución de cliente
        'inventory': '28',   # Ajuste por diferencia de inventario
        'production': '19',  # Entrada de producción
        'internal': '21',    # Entrada por traslado entre almacenes
        'transit': '21',
    },
    'out': {
        'supplier': '25',    # Devolución a proveedor
        'customer': '01',    # Venta nacional
        'inventory': '28',   # Ajuste por diferencia de inventario
        'production': '10',  # Salida a producción
        'internal': '11',    # Salida por traslado entre almacenes
        'transit': '11',
    },
}

VALUATION_METHOD_LABELS = {
    'average': 'PROMEDIO PONDERADO',
    'fifo': 'PEPS (FIFO)',
    'standard': 'COSTO ESTÁNDAR',
}

# Tabla 5 SUNAT (tipo de existencia) en español, indexada por el código del
# Selection de l10n_pe_reports_stock (cuyas etiquetas están en inglés).
SUNAT_TABLE5_ES = {
    '1': 'Mercaderías',
    '2': 'Productos terminados',
    '3': 'Materias primas',
    '4': 'Envases',
    '5': 'Materiales auxiliares',
    '6': 'Suministros',
    '7': 'Repuestos',
    '8': 'Embalajes',
    '9': 'Subproductos',
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
        return results

    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True,
        default=lambda self: self.env.company)
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
        help='Genera una sección/hoja por almacén e incluye traslados '
             'internos entre almacenes (op. 11/21 de la Tabla 12). El costo '
             'por almacén es aproximado: Odoo valoriza por compañía. '
             'Desmarcado: kardex consolidado de la compañía, cuadra con el '
             'TXT PLE.')
    include_no_movement = fields.Boolean(
        string='Incluir productos sin movimientos',
        default=True,
        help='Incluye productos con saldo inicial distinto de cero aunque no '
             'tengan movimientos en el período.')
    line_ids = fields.One2many('l10n_pe.kardex.line', 'wizard_id')

    report_data = fields.Binary('Archivo', readonly=True, attachment=False)
    report_filename = fields.Char(string='Nombre de archivo', readonly=True)
    mimetype = fields.Char(readonly=True)

    # -------------------------------------------------------------------------
    # Acciones
    # -------------------------------------------------------------------------

    def action_view(self):
        self._generate_lines()
        group_by = ['product_id']
        if self.group_by_warehouse:
            group_by = ['warehouse_id', 'product_id']
        return {
            'name': self.env._('Kardex %(format)s del %(date_from)s al %(date_to)s',
                               format=self.report_type == '1301' and '13.1' or '12.1',
                               date_from=self.date_from, date_to=self.date_to),
            'type': 'ir.actions.act_window',
            'res_model': 'l10n_pe.kardex.line',
            'view_mode': 'list',
            'domain': [('wizard_id', '=', self.id)],
            'context': {
                'group_by': group_by,
                'create': False,
                'edit': False,
                'delete': False,
                'kardex_physical': self.report_type == '1201',
            },
        }

    def action_export_xlsx(self):
        self._generate_lines()
        content = build_kardex_xlsx(self)
        self.write({
            'report_data': base64.b64encode(content),
            'report_filename': self._get_export_filename('xlsx'),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
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

    def action_print_pdf(self):
        self._generate_lines()
        return self.env.ref('ol_stock_kardex_pe.action_report_kardex').report_action(self)

    def _get_export_filename(self, extension):
        return 'KARDEX_%s_%s_%s%02d.%s' % (
            self.report_type,
            self.company_id.vat or self.company_id.id,
            self.date_from.year, self.date_from.month, extension)

    # -------------------------------------------------------------------------
    # Motor de cálculo
    # -------------------------------------------------------------------------

    def _get_scopes(self):
        """Devuelve los ámbitos del reporte: una lista de almacenes (modo por
        almacén) o [None] (modo consolidado por compañía)."""
        self.ensure_one()
        if not self.group_by_warehouse:
            return [None]
        warehouses = self.warehouse_ids or self.env['stock.warehouse'].search(
            [('company_id', '=', self.company_id.id)])
        return list(warehouses)

    def _get_moves_domain(self, warehouse):
        dt_from = datetime.combine(self.date_from, time.min)
        dt_to = datetime.combine(self.date_to, time.max)
        domain = Domain([
            ('state', '=', 'done'),
            ('company_id', '=', self.company_id.id),
            ('date', '>=', dt_from),
            ('date', '<=', dt_to),
            ('product_id.is_storable', '=', True),
        ])
        domain &= self._get_products_domain('product_id')
        if warehouse:
            view_loc = warehouse.view_location_id
            domain &= Domain([
                '|',
                ('location_id', 'child_of', view_loc.id),
                ('location_dest_id', 'child_of', view_loc.id),
            ])
        else:
            # Consolidado: solo movimientos valorados de entrada/salida
            # (mismo universo que el TXT PLE).
            domain &= Domain(['|', ('is_in', '=', True), ('is_out', '=', True)])
            if self.warehouse_ids:
                view_locs = self.warehouse_ids.view_location_id.ids
                domain &= Domain([
                    '|',
                    ('location_id', 'child_of', view_locs),
                    ('location_dest_id', 'child_of', view_locs),
                ])
        return domain

    def _get_products_domain(self, prefix=''):
        field = prefix and prefix + '.' or ''
        if self.product_ids:
            return Domain([(prefix or 'id', 'in', self.product_ids.ids)])
        if self.categ_ids:
            return Domain([(field + 'categ_id', 'child_of', self.categ_ids.ids)])
        return Domain.TRUE

    @api.model
    def _location_in_warehouse(self, location, warehouse):
        return (
            location.usage == 'internal'
            and location.parent_path.startswith(warehouse.view_location_id.parent_path)
        )

    def _get_move_direction(self, move, warehouse):
        """'in' / 'out' respecto al ámbito, o None si el movimiento no cruza
        la frontera del ámbito (p. ej. reubicación interna del almacén)."""
        if not warehouse:
            if move.is_in:
                return 'in'
            if move.is_out:
                return 'out'
            return None
        src_in = self._location_in_warehouse(move.location_id, warehouse)
        dest_in = self._location_in_warehouse(move.location_dest_id, warehouse)
        if dest_in and not src_in:
            return 'in'
        if src_in and not dest_in:
            return 'out'
        return None

    @api.model
    def _get_move_operation_type(self, move, direction):
        if move.picking_id.l10n_pe_operation_type:
            return move.picking_id.l10n_pe_operation_type.zfill(2)
        if move.scrapped:
            return '13'  # Merma
        other = move.location_id if direction == 'in' else move.location_dest_id
        return OPERATION_FALLBACK[direction].get(other.usage, '99')

    def _get_move_document(self, move, has_latam_number):
        """(fecha_doc, código Tabla 10, serie, folio, account_move) del
        comprobante vinculado al movimiento; documento interno si no hay."""
        invoice = move.sale_line_id.invoice_lines.move_id[:1]
        bill = move.purchase_line_id.invoice_lines.move_id[:1]
        doc = invoice or bill
        number = ''
        if has_latam_number and move.picking_id.l10n_latam_document_number:
            number = move.picking_id.l10n_latam_document_number
        elif doc:
            # l10n_latam_document_number es el número crudo tecleado (p. ej.
            # "F001-00000123"); doc.name le antepone el prefijo del tipo de
            # documento y ensuciaría la serie.
            number = doc.l10n_latam_document_number or doc.name or ''
        else:
            number = move.picking_id.name or move.reference or ''
        serie_folio = self.env['l10n_pe.stock.ple.wizard']._get_serie_folio(number)
        return (
            doc.invoice_date or move.date.date(),
            doc.l10n_latam_document_type_id.code or '00',
            (serie_folio['serie'] or '').replace(' ', '').replace('/', ''),
            (serie_folio['folio'] or '').replace(' ', ''),
            doc,
        )

    def _generate_lines(self):
        self.ensure_one()
        self.line_ids.unlink()
        valued = self.report_type == '1301'
        Move = self.env['stock.move']
        Product = self.env['product.product']
        has_latam_number = 'l10n_latam_document_number' in self.env['stock.picking']._fields
        opening_dt = datetime.combine(self.date_from, time.min) - timedelta(seconds=1)
        price_prec = self.env['decimal.precision'].precision_get('Product Price')

        vals_list = []
        sequence = 0
        for warehouse in self._get_scopes():
            moves = Move.search(self._get_moves_domain(warehouse),
                                order='product_id, date, id')
            moves_by_product = defaultdict(lambda: Move)
            for move in moves:
                moves_by_product[move.product_id] |= move

            products = moves.product_id
            if self.include_no_movement:
                products |= Product.search(
                    Domain([('is_storable', '=', True)]) & self._get_products_domain())

            ctx = {'to_date': opening_dt}
            if warehouse:
                ctx['warehouse_id'] = warehouse.id
            products_at_opening = products.with_company(self.company_id).with_context(**ctx)
            # Prefetch en lote de cantidades/valores históricos
            products_at_opening.mapped('qty_available')
            if valued:
                products_at_opening.mapped('total_value')

            for product in products.sorted(lambda p: (p.default_code or '', p.name)):
                product_opening = products_at_opening.browse(product.id)
                balance_qty = product_opening.qty_available
                balance_value = product_opening.total_value if valued else 0.0
                product_moves = moves_by_product[product]
                if not product_moves and product.uom_id.is_zero(balance_qty):
                    continue

                sequence += 1
                vals_list.append({
                    'wizard_id': self.id,
                    'sequence': sequence,
                    'line_type': 'opening',
                    'warehouse_id': warehouse.id if warehouse else False,
                    'product_id': product.id,
                    'date': datetime.combine(self.date_from, time.min),
                    'document_type_code': '00',
                    'operation_type': '16',  # Saldo inicial
                    'qty_in': balance_qty if balance_qty > 0 else 0.0,
                    'cost_unit_in': (balance_value / balance_qty) if valued and balance_qty else 0.0,
                    'cost_total_in': balance_value if valued and balance_qty > 0 else 0.0,
                    'balance_qty': balance_qty,
                    'balance_unit_cost': (balance_value / balance_qty) if valued and balance_qty else 0.0,
                    'balance_value': balance_value if valued else 0.0,
                })

                total_qty_in = total_val_in = 0.0
                total_qty_out = total_val_out = 0.0
                for move in product_moves:
                    direction = self._get_move_direction(move, warehouse)
                    if not direction:
                        continue
                    if move.is_in or move.is_out:
                        qty = move._get_valued_qty()
                        value = abs(move.value) if valued else 0.0
                    else:
                        # Traslado interno (solo modo por almacén): no está
                        # valorado en stock.move; se valúa al costo promedio
                        # corriente del kardex.
                        qty = move.product_uom._compute_quantity(
                            move.quantity, product.uom_id)
                        unit = (balance_value / balance_qty) if balance_qty else 0.0
                        value = unit * qty if valued else 0.0
                    if product.uom_id.is_zero(qty) and float_is_zero(value, precision_digits=price_prec):
                        continue

                    doc_date, doc_type, serie, folio, doc = self._get_move_document(
                        move, has_latam_number)
                    unit_cost = (value / qty) if qty else 0.0
                    if direction == 'in':
                        balance_qty += qty
                        balance_value += value
                        total_qty_in += qty
                        total_val_in += value
                    else:
                        balance_qty -= qty
                        balance_value -= value
                        total_qty_out += qty
                        total_val_out += value

                    sequence += 1
                    vals_list.append({
                        'wizard_id': self.id,
                        'sequence': sequence,
                        'line_type': 'move',
                        'warehouse_id': warehouse.id if warehouse else False,
                        'product_id': product.id,
                        'date': move.date,
                        'document_type_code': doc_type,
                        'serie': serie,
                        'folio': folio,
                        'operation_type': self._get_move_operation_type(move, direction),
                        'picking_id': move.picking_id.id,
                        'move_id': move.id,
                        'account_move_id': doc.id if doc else False,
                        'qty_in': qty if direction == 'in' else 0.0,
                        'cost_unit_in': unit_cost if direction == 'in' else 0.0,
                        'cost_total_in': value if direction == 'in' else 0.0,
                        'qty_out': qty if direction == 'out' else 0.0,
                        'cost_unit_out': unit_cost if direction == 'out' else 0.0,
                        'cost_total_out': value if direction == 'out' else 0.0,
                        'balance_qty': balance_qty,
                        'balance_unit_cost': (balance_value / balance_qty) if balance_qty else 0.0,
                        'balance_value': balance_value if valued else 0.0,
                    })

                sequence += 1
                vals_list.append({
                    'wizard_id': self.id,
                    'sequence': sequence,
                    'line_type': 'total',
                    'warehouse_id': warehouse.id if warehouse else False,
                    'product_id': product.id,
                    'qty_in': total_qty_in,
                    'cost_total_in': total_val_in,
                    'qty_out': total_qty_out,
                    'cost_total_out': total_val_out,
                    'balance_qty': balance_qty,
                    'balance_unit_cost': (balance_value / balance_qty) if balance_qty else 0.0,
                    'balance_value': balance_value if valued else 0.0,
                })

        self.env['l10n_pe.kardex.line'].create(vals_list)
        return True

    # -------------------------------------------------------------------------
    # Datos estructurados para los renderizadores (XLSX / QWeb)
    # -------------------------------------------------------------------------

    def _get_report_data(self):
        """Estructura anidada ámbito → productos → líneas, común al XLSX y al
        PDF. Debe llamarse después de _generate_lines()."""
        self.ensure_one()
        scopes = []
        for warehouse in self._get_scopes():
            warehouse_id = warehouse.id if warehouse else False
            wh_lines = self.line_ids.filtered(
                lambda l: (l.warehouse_id.id or False) == warehouse_id)
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
            for product in wh_lines.product_id.sorted(
                    lambda p: (p.default_code or '', p.name)):
                lines = wh_lines.filtered(lambda l: l.product_id == product)
                template = product.product_tmpl_id
                existence_code = template.l10n_pe_type_of_existence or '99'
                products_data.append({
                    'product': product,
                    'code': product.default_code or '',
                    'description': product.name,
                    'existence_type': '%s - %s' % (
                        existence_code.zfill(2),
                        SUNAT_TABLE5_ES.get(existence_code, '')),
                    'uom_code': product.uom_id.l10n_pe_edi_measure_unit_code or '',
                    'uom_name': product.uom_id.name,
                    'valuation_method': VALUATION_METHOD_LABELS.get(
                        product.categ_id.property_cost_method, ''),
                    'lines': lines.filtered(lambda l: l.line_type != 'total'),
                    'total_line': lines.filtered(lambda l: l.line_type == 'total')[:1],
                })
            scopes.append({
                'warehouse': warehouse,
                'name': scope_name,
                'establishment': establishment,
                'products': products_data,
            })
        return scopes

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
