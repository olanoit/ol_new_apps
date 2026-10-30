"""Armado del tablero Perú (spreadsheet.dashboard).

El tablero nativo de Odoo 19 es una hoja de cálculo en JSON. Aquí se arma
desde Python con los bloques de los módulos instalados: cada bloque declara
los campos que necesita y se omite si no existen. El JSON se reescribe al
instalar o actualizar este módulo y, al cargar el registro, cuando cambió el
conjunto de módulos (``_register_hook``), salvo que alguien haya editado el
tablero en la app Tableros (tiene revisiones propias).
"""
import json
import logging

from odoo import api, models
from odoo.tools import BinaryBytes

_logger = logging.getLogger(__name__)

SALES = ['out_invoice', 'out_refund']
PURCHASES = ['in_invoice', 'in_refund']
# Grupos que ven el tablero (data/dashboard_data.xml).
DASHBOARD_GROUPS = ('account.group_account_user', 'account.group_account_readonly')

F_PERIOD = 'a1pe0000-0000-4000-8000-000000000001'
F_PARTNER = 'a1pe0000-0000-4000-8000-000000000002'

# Fila 0 = 23 px. Los gráficos miden 345 px = 15 filas.
CARD_W, CARD_H, CARD_GAP = 235, 109, 20
CHART_ROWS, TABLE_ROWS = 15, 10

STYLES = {
    '1': {'textColor': '#01666b', 'bold': True, 'fontSize': 16},
    '2': {'textColor': '#434343', 'bold': True, 'fontSize': 11},
    '3': {'textColor': '#01666B', 'verticalAlign': 'middle'},
    '4': {'textColor': '#434343', 'verticalAlign': 'middle'},
    '5': {'textColor': '#434343', 'bold': True, 'fontSize': 11, 'align': 'center'},
    '6': {'fillColor': '#f8f9fa'},
    '7': {'textColor': '#ffffff', 'fillColor': '#01666b', 'bold': True, 'fontSize': 14,
          'verticalAlign': 'middle'},
}
TABLE_CONFIG = {'hasFilters': False, 'totalRow': False, 'firstColumn': False, 'lastColumn': False,
                'numberOfHeaders': 1, 'bandedRows': True, 'bandedColumns': False,
                'automaticAutofill': True, 'styleId': 'None'}


def _domain(terms):
    """Dominio en notación prefija, como lo guarda el editor de Odoo."""
    return ['&'] * (len(terms) - 1) + [list(term) for term in terms]


def _col(index):
    return 'ABCDEFG'[index]


def _raw(cell):
    """Celda con el valor numérico (columna B) de una fila de «Datos»."""
    return cell.replace('!C', '!B')


class _Sheet:
    """Hoja «Tablero» que crece hacia abajo, más la hoja oculta «Datos»."""

    def __init__(self):
        self.row = 0
        self.cells, self.styles, self.rows, self.merges = {}, {}, {}, []
        self.figures, self.tables, self.conditional_formats = [], [], []
        self.pivots, self.lists, self.menus = {}, {}, {}
        self.data_cells, self.data_formats = {}, {}
        self.data_row = 0

    # -------------------------------------------------------- fuentes de datos
    def pivot(self, name, model, terms, measures, matching, rows=(), sorted_by=None):
        pid = str(len(self.pivots) + 1)
        pivot = {
            'type': 'ODOO', 'id': pid, 'formulaId': pid, 'name': name, 'model': model,
            'domain': _domain(terms), 'context': {}, 'fieldMatching': matching,
            'measures': [dict(m, id=m.get('id') or m['fieldName']) for m in measures],
            'rows': [{'fieldName': r} for r in rows], 'columns': [],
        }
        if sorted_by:
            pivot['sortedColumn'] = {'measure': sorted_by, 'order': 'desc', 'domain': []}
        self.pivots[pid] = pivot
        return pid

    def odoo_list(self, name, model, terms, columns, order, matching):
        lid = str(len(self.lists) + 1)
        self.lists[lid] = {
            'id': lid, 'name': name, 'model': model, 'columns': columns, 'domain': _domain(terms),
            'context': {}, 'orderBy': [{'name': field, 'asc': asc} for field, asc in order],
            'fieldMatching': matching,
        }
        return lid

    def value(self, label, formula, shown='large', fmt=None):
        """Fila de la hoja «Datos»: devuelve la celda con el texto mostrado."""
        self.data_row += 1
        r = self.data_row
        self.data_cells[f'A{r}'] = label
        self.data_cells[f'B{r}'] = formula
        self.data_cells[f'C{r}'] = f'=FORMAT.LARGE.NUMBER(B{r})' if shown == 'large' else f'=B{r}'
        if fmt:
            self.data_formats[f'C{r}'] = fmt
        return f'Datos!C{r}'

    # ------------------------------------------------------------- maquetado
    def section(self, title):
        r = self.row + 1
        self.rows[str(self.row)] = {'size': 44}
        self.styles[f'A{r}'] = 7
        self.merges.append(f'A{r}:G{r}')
        self.cells[f'A{r}'] = title
        self.row += 2

    def title(self, left, right=None):
        r = self.row + 1
        self.rows[str(self.row)] = {'size': 40}
        if left:
            self.cells[f'A{r}'] = left
            self.styles[f'A{r}'] = 1
        if right:
            self.cells[f'E{r}'] = right
            self.styles[f'E{r}'] = 1
        self.row += 1

    def cards(self, cards):
        """Hasta cuatro indicadores por fila: (título, celda valor, celda base, texto base)."""
        for start in range(0, len(cards), 4):
            for i, (title, key, base, text) in enumerate(cards[start:start + 4]):
                fid = f'kpi-{len(self.figures) + 1}'
                data = {'type': 'scorecard', 'title': {'text': title, 'color': '#434343', 'bold': True},
                        'background': '#EFF6FF', 'keyValue': key, 'baselineMode': 'text',
                        'baselineColorUp': '#00A04A', 'baselineColorDown': '#DC6965', 'humanize': False,
                        'chartId': fid}
                if base:
                    data.update(baseline=base, baselineDescr={'text': text})
                self.figures.append({'id': fid, 'col': 0, 'row': self.row,
                                     'offset': {'x': i * (CARD_W + CARD_GAP), 'y': 6},
                                     'width': CARD_W, 'height': CARD_H, 'tag': 'chart', 'data': data})
            self.row += 6

    def chart(self, ctype, model, group_by, measure, terms, matching, col, width,
              stacked=False, legend='none', menu=None):
        fid = f'chart-{len(self.figures) + 1}'
        data = {
            'type': ctype, 'title': {'text': ''}, 'background': '#FFFFFF', 'legendPosition': legend,
            'metaData': {'groupBy': group_by, 'measure': measure, 'order': None, 'resModel': model,
                         'mode': ctype.removeprefix('odoo_'), 'cumulatedStart': False},
            'searchParams': {'comparison': None, 'context': {}, 'domain': _domain(terms),
                             'groupBy': group_by, 'orderBy': []},
            'dataSets': [], 'fieldMatching': matching, 'chartId': fid,
        }
        if ctype in ('odoo_bar', 'odoo_line'):
            data.update(verticalAxisPosition='left', stacked=stacked)
        self.figures.append({'id': fid, 'col': col, 'row': self.row, 'offset': {'x': 0, 'y': 0},
                             'width': width, 'height': 345, 'tag': 'chart', 'data': data})
        if menu:
            self.menus[fid] = menu

    def end_charts(self):
        self.row += CHART_ROWS + 1

    def pivot_table(self, col, pid, bar_color=None):
        """Tabla dinámica de 3 columnas (título de fila + 2 medidas)."""
        c0, c2 = _col(col), _col(col + 2)
        head, first, last = self.row + 1, self.row + 2, self.row + 1 + TABLE_ROWS
        self.cells[f'{c0}{head}'] = f'=PIVOT({pid}, {TABLE_ROWS}, FALSE, FALSE)'
        self._table_styles(col, head, first, last)
        if bar_color:
            self.conditional_formats.append({
                'id': f'barras-{pid}', 'ranges': [f'{c0}{first}:{c0}{last}'],
                'rule': {'type': 'DataBarRule', 'color': bar_color,
                         'rangeValues': f'{_col(col + 1)}{first}:{_col(col + 1)}{last}'}})
        self.tables.append({'range': f'{c0}{head}:{c2}{last}', 'type': 'static', 'config': TABLE_CONFIG})

    def list_table(self, col, lid, fields_labels, columns=None):
        """Lista de registros; ``columns`` permite saltar la columna D (50 px), que es un separador."""
        columns = columns or [col + i for i in range(len(fields_labels))]
        head = self.row + 1
        for c_index, (field, label) in zip(columns, fields_labels):
            c = _col(c_index)
            self.cells[f'{c}{head}'] = f'=ODOO.LIST.HEADER({lid}, "{field}", "{label}")'
            for n in range(1, TABLE_ROWS + 1):
                self.cells[f'{c}{head + n}'] = f'=ODOO.LIST({lid},{n},"{field}")'
        width = columns[-1] - columns[0] + 1
        self._table_styles(columns[0], head, head + 1, head + TABLE_ROWS, width=width)
        self.tables.append({'range': f'{_col(columns[0])}{head}:{_col(columns[-1])}{head + TABLE_ROWS}',
                            'type': 'static', 'config': TABLE_CONFIG})

    def _table_styles(self, col, head, first, last, width=3):
        c0, cn = _col(col), _col(col + width - 1)
        self.styles[f'{c0}{head}:{cn}{head}'] = 2
        self.styles[f'{c0}{first}:{c0}{last}'] = 3
        if width > 1:
            self.styles[f'{_col(col + 1)}{first}:{cn}{last}'] = 4
        self.rows[str(head - 1)] = {'size': 34}
        for r in range(first - 1, last):
            self.rows[str(r)] = {'size': 27}

    def end_tables(self):
        self.row += TABLE_ROWS + 2

    # ----------------------------------------------------------------- JSON
    def snapshot(self, global_filters):
        dashboard = {
            'id': 'tablero-peru', 'name': 'Tablero', 'colNumber': 7, 'rowNumber': self.row + 2,
            'rows': self.rows,
            'cols': {'0': {'size': 225}, '1': {'size': 150}, '2': {'size': 100}, '3': {'size': 50},
                     '4': {'size': 225}, '5': {'size': 150}, '6': {'size': 100}},
            'merges': self.merges, 'cells': self.cells, 'styles': self.styles, 'formats': {}, 'borders': {},
            'conditionalFormats': self.conditional_formats, 'figures': self.figures, 'tables': self.tables,
            'dataValidationRules': [], 'areGridLinesVisible': False, 'isVisible': True,
            'headerGroups': {'ROW': [], 'COL': []}, 'comments': {},
        }
        data = {
            'id': 'datos-peru', 'name': 'Datos', 'colNumber': 4, 'rowNumber': self.data_row + 5,
            'rows': {}, 'cols': {'0': {'size': 260}, '1': {'size': 130}, '2': {'size': 130}},
            'merges': [], 'cells': self.data_cells, 'styles': {f'C1:C{max(self.data_row, 1)}': 6},
            'formats': self.data_formats, 'borders': {}, 'conditionalFormats': [], 'figures': [], 'tables': [],
            'dataValidationRules': [], 'areGridLinesVisible': True, 'isVisible': False,
            'headerGroups': {'ROW': [], 'COL': []}, 'comments': {},
        }
        return {
            'version': '18.5.10', 'sheets': [dashboard, data], 'styles': STYLES,
            'formats': {'1': '0.0%', '2': '#,##0.000'}, 'borders': {}, 'revisionId': 'START_REVISION',
            'uniqueFigureIds': True, 'settings': {}, 'pivots': self.pivots, 'pivotNextId': len(self.pivots) + 1,
            'customTableStyles': {}, 'globalFilters': global_filters, 'lists': self.lists,
            'listNextId': len(self.lists) + 1, 'chartOdooMenusReferences': self.menus,
        }


class L10nPeDashboardBuilder(models.AbstractModel):
    _name = 'l10n_pe.dashboard.builder'
    _description = 'Tablero Perú: armado de la hoja de cálculo'

    # ------------------------------------------------------------------ hooks
    def _register_hook(self):
        super()._register_hook()
        try:
            with self.env.cr.savepoint():
                self._refresh_dashboard()
        except Exception:  # noqa: BLE001 - nunca impedir que arranque el servidor
            _logger.warning('No se pudo rearmar el tablero Perú', exc_info=True)

    @api.model
    def _refresh_dashboard(self, force=False):
        """Reescribe el JSON del tablero si cambió. Devuelve True si lo escribió."""
        dashboard = self.env.ref('al_l10n_pe_dashboard.dashboard_pe', raise_if_not_found=False)
        if not dashboard:
            return False
        # sudo: el tablero es un dato técnico del módulo; el armado corre al
        # cargar el registro, sin usuario con permiso de edición de tableros.
        dashboard_sudo = dashboard.sudo().with_context(active_test=False)
        revisions = dashboard_sudo._fields.get('spreadsheet_revision_ids')
        if not force and revisions and dashboard_sudo.spreadsheet_revision_ids:
            return False
        content = json.dumps(self._build_snapshot(), ensure_ascii=False, sort_keys=True)
        raw = content.encode()
        current = dashboard_sudo.spreadsheet_binary_data
        if current and current.content == raw:
            return False
        dashboard_sudo.spreadsheet_binary_data = BinaryBytes(raw)
        return True

    # ---------------------------------------------------------------- bloques
    def _has(self, model, *field_names):
        """El modelo y sus campos existen y lo pueden leer todos los grupos del tablero."""
        Model = self.env.get(model)
        return Model is not None and all(name in Model._fields for name in field_names) \
            and self._readable(model)

    def _readable(self, model):
        # Una fuente sin permiso de lectura para alguno de los grupos del
        # tablero mostraría un error en su celda: se omite el bloque.
        # sudo: se consultan los permisos, no los datos.
        # Odoo 20 (ir.access): un permiso lleva grupo; sin grupo es restricción.
        Access = self.env['ir.access'].sudo()
        for xmlid in DASHBOARD_GROUPS:
            group = self.env.ref(xmlid)
            groups = group | group.all_implied_ids
            if not Access.search_count([('model_id.model', '=', model), ('for_read', '=', True),
                                        ('group_id', 'in', groups.ids)], limit=1):
                return False
        return True

    def _sections(self):
        """(método, campos requeridos) en el orden del tablero."""
        return [
            (self._section_tax, [('l10n_pe.dashboard.tax', 'igv')]),
            (self._section_edi, [('account.move', 'l10n_pe_edi_status'), ('account.move', 'l10n_pe_edi_warnings')]),
            (self._section_withholdings, []),
            (self._section_treasury, []),
            (self._section_returns, [('l10n_pe.monthly.tax', 'total_to_pay')]),
        ]

    def _active_sections(self):
        return [method for method, needs in self._sections() if all(self._has(m, f) for m, f in needs)]

    def _build_snapshot(self):
        sheet = _Sheet()
        for method in self._active_sections():
            method(sheet)
        return sheet.snapshot([
            {'id': F_PERIOD, 'type': 'date', 'label': 'Periodo', 'defaultValue': 'year_to_date'},
            {'id': F_PARTNER, 'type': 'relation', 'label': 'Cliente o proveedor', 'modelName': 'res.partner',
             'defaultValueDisplayNames': []},
        ])

    @staticmethod
    def _match(date=None, partner='partner_id', date_type='date'):
        matching = {}
        if date:
            matching[F_PERIOD] = {'chain': date, 'type': date_type, 'offset': 0}
        if partner:
            matching[F_PARTNER] = {'chain': partner, 'type': 'many2one'}
        return matching

    # Ventas, compras e IGV ------------------------------------------------
    def _section_tax(self, sheet):
        model, match = 'l10n_pe.dashboard.tax', self._match('date')
        base = {'fieldName': 'base', 'userDefinedName': 'Base imponible'}
        igv = {'fieldName': 'igv', 'userDefinedName': 'IGV'}
        count = {'id': '__count', 'fieldName': '__count', 'userDefinedName': 'Comprobantes'}
        p_sale = sheet.pivot('Ventas', model, [('kind', '=', 'sale')], [base, igv, count], match)
        p_purchase = sheet.pivot('Compras', model, [('kind', '=', 'purchase')], [base, igv, count], match)
        sale_base = sheet.value('Ventas (base)', f'=PIVOT.VALUE({p_sale},"base")')
        sale_igv = sheet.value('IGV de ventas', f'=PIVOT.VALUE({p_sale},"igv")')
        sale_count = sheet.value('Comprobantes de venta', f'=PIVOT.VALUE({p_sale},"__count")', shown='raw')
        purchase_base = sheet.value('Compras (base)', f'=PIVOT.VALUE({p_purchase},"base")')
        purchase_igv = sheet.value('IGV de compras', f'=PIVOT.VALUE({p_purchase},"igv")')
        purchase_count = sheet.value('Comprobantes de compra', f'=PIVOT.VALUE({p_purchase},"__count")',
                                     shown='raw')
        result = sheet.value('IGV resultante', f'={_raw(sale_igv)}-{_raw(purchase_igv)}')
        rate = sheet.value('IGV sobre ventas', f'=IFERROR({_raw(sale_igv)}/{_raw(sale_base)},0)',
                           shown='raw', fmt=1)

        sheet.section('Ventas, compras e IGV')
        sheet.cards([
            ('Ventas', sale_base, sale_count, 'comprobantes'),
            ('Compras', purchase_base, purchase_count, 'comprobantes'),
            ('IGV de ventas (débito)', sale_igv, rate, 'de las ventas'),
            ('IGV de compras (crédito)', purchase_igv, None, ''),
        ])
        sheet.cards([('IGV resultante del periodo', result, None, 'débito menos crédito, sin saldos anteriores')])
        sheet.title('Ventas y compras por mes', 'Ventas por tipo de comprobante')
        sheet.chart('odoo_bar', model, ['date:month', 'kind'], 'base', [], match, 0, 475, legend='top')
        sheet.chart('odoo_pie', model, ['document_type_id'], 'total', [('kind', '=', 'sale')], match, 4, 475,
                    legend='top')
        sheet.end_charts()
        sheet.title('Principales clientes', 'Principales proveedores')
        p_customers = sheet.pivot('Cliente', model, [('kind', '=', 'sale')],
                                  [dict(base, userDefinedName='Ventas'), dict(igv, userDefinedName='IGV')],
                                  match, rows=['partner_id'], sorted_by='base')
        p_vendors = sheet.pivot('Proveedor', model, [('kind', '=', 'purchase')],
                                [dict(base, userDefinedName='Compras'), dict(igv, userDefinedName='IGV')],
                                match, rows=['partner_id'], sorted_by='base')
        sheet.pivot_table(0, p_customers, bar_color=15726335)
        sheet.pivot_table(4, p_vendors, bar_color=16708338)
        sheet.end_tables()

    # Comprobantes electrónicos --------------------------------------------
    def _section_edi(self, sheet):
        # Odoo 20: l10n_pe_edi dejó account.edi.document; el estado del CPE
        # está en la factura (l10n_pe_edi_status, avisos en l10n_pe_edi_warnings).
        doc = 'account.move'
        pe = [('l10n_pe_edi_status', '!=', False)]
        partner = self._match(partner='partner_id')
        count = [{'id': '__count', 'fieldName': '__count', 'userDefinedName': 'Cantidad'}]
        cells = []
        p = sheet.pivot('CPE por enviar', doc, [('l10n_pe_edi_status', '=', 'to_send')], count, partner)
        cells.append(('Por enviar a SUNAT', sheet.value('CPE por enviar', f'=PIVOT.VALUE({p},"__count")', 'raw'),
                      None, ''))
        p = sheet.pivot('CPE con error', doc, pe + [('l10n_pe_edi_warnings', '!=', False)], count, partner)
        cells.append(('Con observaciones', sheet.value('CPE con error', f'=PIVOT.VALUE({p},"__count")', 'raw'),
                      None, ''))
        p = sheet.pivot('Bajas pendientes', doc,
                        [('l10n_pe_edi_status', '=', 'sent'), ('l10n_pe_edi_cancel_reason', '!=', False)],
                        count, partner)
        cells.append(('Bajas por comunicar', sheet.value('Bajas pendientes', f'=PIVOT.VALUE({p},"__count")', 'raw'),
                      None, ''))
        p = sheet.pivot('CPE aceptados', doc, [('l10n_pe_edi_status', '=', 'sent')], count,
                        self._match('date', 'partner_id'))
        cells.append(('Aceptados en el periodo',
                      sheet.value('CPE aceptados', f'=PIVOT.VALUE({p},"__count")', 'raw'), None, ''))
        if self._has('stock.picking', 'l10n_pe_edi_status'):
            p = sheet.pivot('Guías por enviar', 'stock.picking',
                            [('l10n_pe_edi_status', '=', 'to_send'), ('state', '=', 'done')], count,
                            self._match())
            cells.append(('Guías de remisión por enviar',
                          sheet.value('Guías por enviar', f'=PIVOT.VALUE({p},"__count")', 'raw'), None, ''))
        if self._has('account.payment', 'l10n_pe_edi_status', 'l10n_pe_edi_overdue'):
            p = sheet.pivot('CRE por enviar', 'account.payment', [('l10n_pe_edi_status', '=', 'to_send')], count,
                            self._match())
            cells.append(('Retenciones (CRE) por enviar',
                          sheet.value('CRE por enviar', f'=PIVOT.VALUE({p},"__count")', 'raw'), None, ''))
            p = sheet.pivot('CRE fuera de plazo', 'account.payment', [('l10n_pe_edi_overdue', '=', True)], count,
                            self._match())
            cells.append(('CRE fuera de plazo',
                          sheet.value('CRE fuera de plazo', f'=PIVOT.VALUE({p},"__count")', 'raw'), None, ''))

        sheet.section('Comprobantes electrónicos')
        sheet.cards(cells)
        sheet.title('Pendientes de envío', 'Con observaciones o error')
        columns = [('name', 'Comprobante'), ('partner_id', 'Cliente'), ('amount_total_signed', 'Total')]
        move_match = self._match()
        pending = sheet.odoo_list('CPE por enviar', 'account.move',
                                  [('l10n_pe_edi_status', '=', 'to_send')],
                                  [c for c, _label in columns], [('invoice_date', True)], move_match)
        errors = sheet.odoo_list('CPE con error', 'account.move',
                                 [('l10n_pe_edi_status', '!=', False), ('l10n_pe_edi_warnings', '!=', False)],
                                 [c for c, _label in columns], [('invoice_date', False)], move_match)
        sheet.list_table(0, pending, columns)
        sheet.list_table(4, errors, columns)
        sheet.end_tables()

    # Detracciones, retenciones y percepciones -----------------------------
    def _section_withholdings(self, sheet):
        cards, charts = [], []
        move = 'account.move'
        posted = [('state', '=', 'posted')]
        if self._has(move, 'l10n_pe_detraction_amount', 'l10n_pe_detraction_type_id'):
            amount = [{'fieldName': 'l10n_pe_detraction_amount', 'userDefinedName': 'Detracción'}]
            applies = posted + [('l10n_pe_detraction_applies', '=', True)]
            p = sheet.pivot('Detracciones de ventas', move, applies + [('move_type', '=', 'out_invoice')], amount,
                            self._match('date'))
            cards.append(('Detracciones de ventas',
                          sheet.value('Detracciones de ventas', f'=PIVOT.VALUE({p},"l10n_pe_detraction_amount")'),
                          None, ''))
            p = sheet.pivot('Detracciones de compras', move, applies + [('move_type', '=', 'in_invoice')], amount,
                            self._match('date'))
            cards.append(('Detracciones de compras',
                          sheet.value('Detracciones de compras', f'=PIVOT.VALUE({p},"l10n_pe_detraction_amount")'),
                          None, ''))
            if self._has('account.payment', 'l10n_pe_detraction_move_id'):
                p = sheet.pivot('Depósitos de detracción', 'account.payment',
                                [('l10n_pe_detraction_move_id', '!=', False), ('payment_type', '=', 'outbound'),
                                 ('state', 'in', ['in_process', 'paid'])],
                                [{'fieldName': 'amount', 'userDefinedName': 'Depositado'}], self._match('date'))
                cards.append(('Depositado en el Banco de la Nación',
                              sheet.value('Depósitos de detracción', f'=PIVOT.VALUE({p},"amount")'), None, ''))
            charts.append(('Detracciones por tipo', move, ['l10n_pe_detraction_type_id'], 'l10n_pe_detraction_amount',
                           applies, self._match('date')))
        if self._has('account.payment', 'l10n_pe_retention_amount'):
            p = sheet.pivot('Retenciones efectuadas', 'account.payment',
                            [('l10n_pe_retention_amount', '>', 0), ('state', 'in', ['in_process', 'paid'])],
                            [{'fieldName': 'l10n_pe_retention_amount', 'userDefinedName': 'Retención'}],
                            self._match('date'))
            cards.append(('Retenciones efectuadas',
                          sheet.value('Retenciones efectuadas', f'=PIVOT.VALUE({p},"l10n_pe_retention_amount")'),
                          None, ''))
        if self._has('l10n_pe.retention.received', 'amount', 'date'):
            p = sheet.pivot('Retenciones recibidas', 'l10n_pe.retention.received', [('state', '=', 'posted')],
                            [{'fieldName': 'amount', 'userDefinedName': 'Retención'}], self._match('date'))
            cards.append(('Retenciones que nos hicieron',
                          sheet.value('Retenciones recibidas', f'=PIVOT.VALUE({p},"amount")'), None, ''))
        if self._has(move, 'l10n_pe_perception_amount'):
            p = sheet.pivot('Percepciones de ventas', move,
                            posted + [('move_type', '=', 'out_invoice'), ('l10n_pe_perception_amount', '>', 0)],
                            [{'fieldName': 'l10n_pe_perception_amount', 'userDefinedName': 'Percepción'}],
                            self._match('date'))
            cards.append(('Percepciones de ventas',
                          sheet.value('Percepciones de ventas', f'=PIVOT.VALUE({p},"l10n_pe_perception_amount")'),
                          None, ''))
        if self._has('l10n_pe.perception.received', 'amount', 'date'):
            p = sheet.pivot('Percepciones recibidas', 'l10n_pe.perception.received', [('state', '=', 'posted')],
                            [{'fieldName': 'amount', 'userDefinedName': 'Percepción'}], self._match('date'))
            cards.append(('Percepciones que nos hicieron',
                          sheet.value('Percepciones recibidas', f'=PIVOT.VALUE({p},"amount")'), None, ''))
        if not cards:
            return
        sheet.section('Detracciones, retenciones y percepciones')
        sheet.cards(cards)
        if charts:
            title, model, group_by, measure, terms, match = charts[0]
            sheet.title(title)
            sheet.chart('odoo_bar', model, group_by, measure, terms, match, 0, 1000)
            sheet.end_charts()

    # Tesorería ------------------------------------------------------------
    def _section_treasury(self, sheet):
        move = 'account.move'
        open_terms = [('state', '=', 'posted'), ('payment_state', 'in', ['not_paid', 'partial'])]
        residual = [{'fieldName': 'amount_residual_signed', 'userDefinedName': 'Saldo'}]
        p_in = sheet.pivot('Por cobrar', move, open_terms + [('move_type', 'in', SALES)], residual, self._match())
        p_out = sheet.pivot('Por pagar', move, open_terms + [('move_type', 'in', PURCHASES)], residual,
                            self._match())
        cards = [
            ('Por cobrar (comprobantes)', sheet.value('Por cobrar', f'=PIVOT.VALUE({p_in},"amount_residual_signed")'),
             None, ''),
            ('Por pagar (comprobantes)', sheet.value('Por pagar', f'=-PIVOT.VALUE({p_out},"amount_residual_signed")'),
             None, ''),
        ]
        letters = self._has('account.move.line', 'l10n_pe_letter_line_id')
        if letters:
            aml = 'account.move.line'
            open_lines = [('parent_state', '=', 'posted'), ('reconciled', '=', False),
                          ('l10n_pe_letter_line_id', '!=', False)]
            res = [{'fieldName': 'amount_residual', 'userDefinedName': 'Saldo'}]
            p = sheet.pivot('Letras por cobrar', aml,
                            open_lines + [('account_id.account_type', '=', 'asset_receivable')], res, self._match())
            cards.append(('Letras por cobrar', sheet.value('Letras por cobrar', f'=PIVOT.VALUE({p},"amount_residual")'),
                          None, ''))
            p = sheet.pivot('Letras por pagar', aml,
                            open_lines + [('account_id.account_type', '=', 'liability_payable')], res, self._match())
            cards.append(('Letras por pagar', sheet.value('Letras por pagar', f'=-PIVOT.VALUE({p},"amount_residual")'),
                          None, ''))
        sheet.section('Tesorería')
        sheet.cards(cards)
        rates = self._has('res.currency.rate', 'rate_purchase', 'rate_sale')
        if letters or rates:
            sheet.title('Letras por cobrar por situación' if letters else None,
                        'Tipo de cambio SUNAT (dólar)' if rates else None)
            if letters:
                sheet.chart('odoo_bar', 'account.move.line', ['account_id'], 'amount_residual',
                            [('parent_state', '=', 'posted'), ('reconciled', '=', False),
                             ('l10n_pe_letter_line_id', '!=', False),
                             ('account_id.account_type', '=', 'asset_receivable')], self._match(), 0, 475)
            if rates:
                lid = sheet.odoo_list('Tipo de cambio', 'res.currency.rate', [('currency_id.name', '=', 'USD')],
                                      ['name', 'rate_purchase', 'rate_sale'], [('name', False)], {})
                sheet.list_table(4, lid, [('name', 'Fecha'), ('rate_purchase', 'Compra'), ('rate_sale', 'Venta')])
            sheet.row += CHART_ROWS + 1 if letters else TABLE_ROWS + 2

    # Declaraciones mensuales ----------------------------------------------
    def _section_returns(self, sheet):
        model = 'l10n_pe.monthly.tax'
        p = sheet.pivot('IGV y renta declarados', model, [('state', '=', 'declared')],
                        [{'fieldName': 'total_to_pay', 'userDefinedName': 'Total pagado'}],
                        self._match('date_from', partner=None))
        p_pending = sheet.pivot('Por declarar', model, [('state', '!=', 'declared')],
                                [{'id': '__count', 'fieldName': '__count', 'userDefinedName': 'Periodos'}],
                                self._match(partner=None))
        sheet.section('Declaraciones mensuales')
        sheet.cards([
            ('Pagado en declaraciones', sheet.value('Total de declaraciones', f'=PIVOT.VALUE({p},"total_to_pay")'),
             None, ''),
            ('Periodos por declarar', sheet.value('Periodos por declarar', f'=PIVOT.VALUE({p_pending},"__count")',
                                                  'raw'), None, ''),
        ])
        sheet.title('Últimos periodos')
        lid = sheet.odoo_list('Declaraciones', model, [],
                              ['name', 'igv_to_pay', 'income_tax_to_pay', 'total_to_pay', 'state'],
                              [('date_from', False)], {})
        sheet.list_table(0, lid, [('name', 'Periodo'), ('igv_to_pay', 'IGV a pagar'),
                                  ('income_tax_to_pay', 'Renta a pagar'), ('total_to_pay', 'Total a pagar'),
                                  ('state', 'Estado')], columns=[0, 1, 2, 4, 5])
        sheet.end_tables()
