# -*- coding: utf-8 -*-
import base64
import calendar
import io
import re
import zipfile
from datetime import date, datetime, time

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class L10nPePleExportWizard(models.TransientModel):
    _name = 'l10n_pe.ple.export.wizard'
    _inherit = 'l10n_pe.ple.mixin'
    _description = 'Exportar Libros Electrónicos PLE'

    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True,
        default=lambda self: self.env.company)
    year = fields.Integer(
        string='Ejercicio', required=True,
        default=lambda self: fields.Date.context_today(self).year)
    operations_indicator = fields.Selection(
        [('1', '1 - Empresa operativa'),
         ('2', '2 - Cierre del libro (no obligado a llevarlo)'),
         ('0', '0 - Cierre de operaciones (baja de RUC)')],
        string='Indicador de operaciones', required=True, default='1')
    month = fields.Selection(
        [('%02d' % m, '%02d' % m) for m in range(1, 13)],
        string='Mes', help='Solo aplica a los libros mensuales (4.1, 9.1, '
                           '9.2). Los libros anuales usan únicamente el '
                           'ejercicio.',
        default=lambda self: '%02d' % fields.Date.context_today(self).month)
    export_71 = fields.Boolean(string='7.1 Activos fijos', default=True)
    export_73 = fields.Boolean(string='7.3 Diferencia de cambio')
    export_74 = fields.Boolean(string='7.4 Arrendamiento financiero')
    export_41 = fields.Boolean(string='4.1 Retenciones Art. 34 LIR')
    export_91 = fields.Boolean(string='9.1 Consignaciones (consignador)')
    export_92 = fields.Boolean(string='9.2 Consignaciones (consignatario)')

    balance_date = fields.Date(
        string='Fecha de los EEFF',
        compute='_compute_balance_date', store=True, readonly=False,
        help='Fecha del balance para los formatos del Libro 3 '
             '(normalmente el 31/12 del ejercicio). Forma parte del nombre '
             'del archivo (AAAAMMDD).')
    opportunity = fields.Selection(
        [('01', '01 - Al 31 de diciembre'),
         ('02', '02 - Al 31 de enero (modificación de porcentaje)'),
         ('03', '03 - Al 30 de junio (modificación coeficiente/porcentaje)'),
         ('04', '04 - Último día del mes de suspensión/modificación'),
         ('05', '05 - Día anterior a fusión/escisión/extinción'),
         ('06', '06 - Balance de liquidación/cierre/cese'),
         ('07', '07 - Libre propósito')],
        string='Oportunidad (CC)', default='01',
        help='Oportunidad de presentación del EEFF (solo Libro 3).')
    export_38 = fields.Boolean(string='3.8 Inversiones mobiliarias (cta. 30)')
    export_39 = fields.Boolean(string='3.9 Intangibles (cta. 34)')
    export_319 = fields.Boolean(string='3.19 Cambios en el patrimonio neto')
    export_101 = fields.Boolean(string='10.1 Costo de ventas anual')
    export_102 = fields.Boolean(string='10.2 Elementos del costo (mensual)')
    export_103 = fields.Boolean(string='10.3 Costo de producción valorizado')
    export_104 = fields.Boolean(string='10.4 Centros de costos')
    export_52 = fields.Boolean(string='5.2 Diario Simplificado')
    export_54 = fields.Boolean(string='5.4 Plan contable (Diario Simpl.)')
    export_83 = fields.Boolean(string='8.3 Compras Simplificado')
    export_142 = fields.Boolean(string='14.2 Ventas Simplificado')
    l10n_pe_ple_simplified = fields.Boolean(
        related='company_id.l10n_pe_ple_simplified')
    notes_pdf = fields.Binary(
        string='3.23 Notas a los EEFF (PDF)',
        help='El 3.23 se presenta en PDF (no tiene estructura TXT). Si '
             'adjunta el archivo aquí, se incluye en el ZIP con el nombre '
             'oficial.')

    file_name = fields.Char(readonly=True)
    file_data = fields.Binary(string='Archivo', readonly=True)

    # ------------------------------------------------------------------
    # Acción principal
    # ------------------------------------------------------------------
    def action_export(self):
        self.ensure_one()
        if self.company_id.account_fiscal_country_id.code != 'PE':
            raise UserError(_('La compañía %s no pertenece a la localización '
                              'peruana.', self.company_id.display_name))
        simplified = (self.export_52 or self.export_54 or self.export_83
                      or self.export_142)
        if simplified and not self.company_id.l10n_pe_ple_simplified:
            raise UserError(_(
                'Los formatos simplificados (5.2/5.4, 8.3, 14.2) son '
                'excluyentes con los formatos completos y solo aplican a '
                'contribuyentes autorizados. Habilítelos en Ajustes ▸ Perú ▸ '
                '«Libros PLE simplificados».'))
        monthly = (self.export_41 or self.export_91 or self.export_92
                   or simplified)
        if monthly and not self.month:
            raise UserError(_('Indique el mes para los libros mensuales '
                              '(4.1 / 9.1 / 9.2 / simplificados).'))
        lib_books = (self.export_38 or self.export_39 or self.export_319
                     or self.notes_pdf)
        if lib_books and not self.balance_date:
            raise UserError(_('Indique la fecha de los EEFF para los '
                              'formatos del Libro 3.'))
        exports = []
        if self.export_71:
            exports.append(self._export_71())
        if self.export_73:
            exports.append(self._export_73())
        if self.export_74:
            exports.append(self._export_74())
        if self.export_41:
            exports.append(self._export_41())
        if self.export_91:
            exports.append(self._export_9('090100'))
        if self.export_92:
            exports.append(self._export_9('090200'))
        if self.export_52:
            exports.append(self._export_52())
        if self.export_54:
            exports.append(self._export_54())
        if self.export_83:
            exports.append(self._export_83())
        if self.export_142:
            exports.append(self._export_142())
        if self.export_101:
            exports.append(self._export_101())
        if self.export_102:
            exports.append(self._export_102())
        if self.export_103:
            exports.append(self._export_103())
        if self.export_104:
            exports.append(self._export_104())
        if self.export_38:
            exports.append(self._export_38())
        if self.export_39:
            exports.append(self._export_39())
        if self.export_319:
            exports.append(self._export_319())
        if self.notes_pdf:
            exports.append((
                self._lib_filename('032300', True, extension='.pdf'),
                base64.b64decode(self.notes_pdf)))
        if not exports:
            raise UserError(_('Seleccione al menos un formato a generar.'))

        if len(exports) == 1:
            file_name, content = exports[0]
        else:
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for name, content in exports:
                    zf.writestr(name, content)
            file_name = 'PLE_%s_%04d.zip' % (
                self._ple_ruc(self.company_id), self.year)
            content = buffer.getvalue()

        self.write({
            'file_name': file_name,
            'file_data': base64.b64encode(content),
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # ------------------------------------------------------------------
    # Datos comunes del Libro 7
    # ------------------------------------------------------------------
    def _period_71(self):
        return '%04d0000' % self.year

    def _date_range(self):
        return date(self.year, 1, 1), date(self.year, 12, 31)

    def _get_assets(self, extra_domain=None):
        """Activos raíz vigentes durante el ejercicio (excluye modelos,
        borradores, cancelados y los hijos por aumento de valor, que se
        agregan al padre)."""
        date_from, date_to = self._date_range()
        domain = [
            ('company_id', '=', self.company_id.id),
            ('state', 'in', ('open', 'paused', 'close')),
            ('parent_id', '=', False),
            ('acquisition_date', '<=', date_to),
            '|', ('disposal_date', '=', False),
            ('disposal_date', '>=', date_from),
        ]
        return self.env['account.asset'].search(
            domain + (extra_domain or []), order='acquisition_date, id')

    def _depreciation_sums(self, assets, date_from=None, date_to=None):
        """{asset_raíz: (dep. acumulada anterior, dep. del ejercicio)} sobre
        asientos de depreciación publicados (incluye los de sus hijos)."""
        default_from, default_to = self._date_range()
        date_from = date_from or default_from
        date_to = date_to or default_to
        all_assets = assets | assets.mapped('children_ids')
        result = {asset.id: [0.0, 0.0] for asset in assets}
        root_of = {asset.id: asset.id for asset in assets}
        for child in assets.mapped('children_ids'):
            root_of[child.id] = child.parent_id.id
        moves = self.env['account.move'].search_read(
            [('asset_id', 'in', all_assets.ids),
             ('state', '=', 'posted'),
             ('date', '<=', date_to)],
            ['asset_id', 'date', 'amount_total'])
        for move in moves:
            root = root_of.get(move['asset_id'][0])
            if root is None:
                continue
            index = 1 if move['date'] >= date_from else 0
            result[root][index] += move['amount_total']
        for asset in assets:
            # depreciación importada de sistemas previos = acumulada anterior
            result[asset.id][0] += asset.already_depreciated_amount_import
        return result

    def _asset_code(self, asset):
        return self._ple_text(
            asset.l10n_pe_ple_code, 24, default='AF%06d' % asset.id)

    def _require(self, assets, field_name, label):
        missing = assets.filtered(lambda a: not a[field_name])
        if missing:
            raise UserError(_(
                'Los siguientes activos no tienen configurado «%(label)s» '
                '(pestaña PLE SUNAT): %(assets)s',
                label=label,
                assets=', '.join(missing.mapped('display_name')[:20])))

    def _make_file(self, book_code, lines):
        file_name = self._ple_filename(
            self.company_id, book_code, self.year,
            operations=self.operations_indicator, has_data=bool(lines))
        return file_name, self._ple_content(book_code, lines)

    # ------------------------------------------------------------------
    # Utilidades de libros mensuales
    # ------------------------------------------------------------------
    def _month_range(self):
        month = int(self.month)
        last_day = calendar.monthrange(self.year, month)[1]
        return date(self.year, month, 1), date(self.year, month, last_day)

    def _period_month(self):
        return '%04d%s00' % (self.year, self.month)

    def _make_file_monthly(self, book_code, lines):
        file_name = self._ple_filename(
            self.company_id, book_code, self.year, month=int(self.month),
            operations=self.operations_indicator, has_data=bool(lines))
        return file_name, self._ple_content(book_code, lines)

    def _partner_doc(self, partner):
        """(tipo doc tabla 2, nº doc, nombre) de una contraparte."""
        code = partner.l10n_latam_identification_type_id.l10n_pe_vat_code
        vat = (partner.vat or '').strip()
        if not code:
            code = '6' if len(vat) == 11 and vat.isdigit() else '0'
        return code, self._ple_text(vat, 15, '-'), self._ple_text(
            partner.name, 100, '-')

    # ------------------------------------------------------------------
    # Utilidades del Libro 3 (Inventarios y Balances, AAAAMMDD + CC)
    # ------------------------------------------------------------------
    @api.depends('year')
    def _compute_balance_date(self):
        for wizard in self:
            if wizard.year:
                wizard.balance_date = date(wizard.year, 12, 31)

    def _period_lib(self):
        return self.balance_date.strftime('%Y%m%d')

    def _lib_filename(self, book_code, has_data, extension='.txt'):
        bd = self.balance_date
        return self._ple_filename(
            self.company_id, book_code, bd.year, month=bd.month, day=bd.day,
            opportunity=self.opportunity or '01',
            operations=self.operations_indicator, has_data=has_data,
            extension=extension)

    def _make_file_lib(self, book_code, lines):
        return (self._lib_filename(book_code, bool(lines)),
                self._ple_content(book_code, lines))

    # ------------------------------------------------------------------
    # 7.1 — Activos fijos revaluados y no revaluados (37 campos)
    # ------------------------------------------------------------------
    def _export_71(self):
        date_from, date_to = self._date_range()
        assets = self._get_assets()
        self._require(assets, 'l10n_pe_asset_type', 'Tipo de activo (T18)')
        dep_sums = self._depreciation_sums(assets)
        lines = []
        for asset in assets:
            initial = additions = improvements = retirement = 0.0
            children = asset.children_ids.filtered(
                lambda c: c.state in ('open', 'paused', 'close'))
            prior_children = sum(
                c.original_value for c in children
                if (c.acquisition_date or date_from) < date_from)
            year_children = sum(
                c.original_value for c in children
                if date_from <= (c.acquisition_date or date_from) <= date_to)
            if asset.acquisition_date < date_from:
                initial = asset.original_value + prior_children
            else:
                additions = asset.original_value
                improvements += prior_children
            improvements += year_children
            if asset.disposal_date and date_from <= asset.disposal_date <= date_to:
                retirement = asset.original_value
            prev_dep, year_dep = dep_sums[asset.id]
            lines.append([
                self._period_71(),                                    # 1
                asset.id,                                             # 2 CUO
                'M%d' % asset.id,                                     # 3
                self._ple_text(asset.l10n_pe_ple_catalog, 1, '9'),    # 4
                self._asset_code(asset),                              # 5
                '',                                                   # 6 UNSPSC (op)
                '',                                                   # 7 (op)
                self._ple_text(asset.l10n_pe_asset_type, 1),          # 8
                self._ple_text(asset.account_asset_id.code, 24),      # 9
                self._ple_text(asset.l10n_pe_asset_status, 1, '1'),   # 10
                self._ple_text(asset.name, 40),                       # 11
                self._ple_text(asset.l10n_pe_brand, 20, '-'),         # 12
                self._ple_text(asset.l10n_pe_model, 20, '-'),         # 13
                self._ple_text(asset.l10n_pe_plate, 30, '-'),         # 14
                self._ple_amount(initial),                            # 15
                self._ple_amount(additions),                          # 16
                self._ple_amount(improvements),                       # 17
                self._ple_amount(retirement),                         # 18
                self._ple_amount(0.0),                                # 19 otros ajustes
                self._ple_amount(0.0),                                # 20 reval. voluntaria
                self._ple_amount(0.0),                                # 21 reval. reorganización
                self._ple_amount(0.0),                                # 22 otras reval.
                self._ple_amount(0.0),                                # 23 ajuste inflación
                self._ple_date(asset.acquisition_date),               # 24
                self._ple_date(asset.prorata_date
                               or asset.acquisition_date),            # 25
                self._ple_text(asset.l10n_pe_depre_method, 1, '9'),   # 26
                self._ple_text(asset.l10n_pe_depre_auth_doc, 20, '-'),  # 27
                self._ple_amount(asset.l10n_pe_depre_rate),           # 28
                self._ple_amount(prev_dep),                           # 29
                self._ple_amount(year_dep),                           # 30
                self._ple_amount(0.0),                                # 31 dep. retiros
                self._ple_amount(0.0),                                # 32 dep. otros ajustes
                self._ple_amount(0.0),                                # 33 dep. reval. voluntaria
                self._ple_amount(0.0),                                # 34 dep. reval. reorg.
                self._ple_amount(0.0),                                # 35 dep. otras reval.
                self._ple_amount(0.0),                                # 36 ajuste inflación dep.
                '1',                                                  # 37 estado
            ])
        return self._make_file('070100', lines)

    # ------------------------------------------------------------------
    # 7.3 — Diferencia de cambio (15 campos)
    # ------------------------------------------------------------------
    def _export_73(self):
        date_from, date_to = self._date_range()
        assets = self._get_assets(
            [('l10n_pe_fx_currency_id', '!=', False)])
        self._require(assets, 'l10n_pe_fx_amount', 'Valor adquisición en ME')
        self._require(assets, 'l10n_pe_fx_rate', 'TC a fecha de adquisición')
        dep_sums = self._depreciation_sums(assets)
        pen = self.company_id.currency_id
        lines = []
        for asset in assets:
            close_rate = self.env['res.currency']._get_conversion_rate(
                asset.l10n_pe_fx_currency_id, pen, self.company_id, date_to)
            mn_value = asset.original_value
            fx_adjust = asset.l10n_pe_fx_amount * close_rate - mn_value
            lines.append([
                self._period_71(),                                    # 1
                asset.id,                                             # 2 CUO
                'M%d' % asset.id,                                     # 3
                self._ple_text(asset.l10n_pe_ple_catalog, 1, '9'),    # 4
                self._asset_code(asset),                              # 5
                self._ple_date(asset.acquisition_date),               # 6
                self._ple_amount(asset.l10n_pe_fx_amount),            # 7
                self._ple_rate(asset.l10n_pe_fx_rate),                # 8
                self._ple_amount(mn_value),                           # 9
                self._ple_rate(close_rate),                           # 10
                self._ple_amount(fx_adjust),                          # 11
                self._ple_amount(dep_sums[asset.id][1]),              # 12
                self._ple_amount(0.0),                                # 13
                self._ple_amount(0.0),                                # 14
                '1',                                                  # 15 estado
            ])
        return self._make_file('070300', lines)

    # ------------------------------------------------------------------
    # 7.4 — Arrendamiento financiero (11 campos)
    # ------------------------------------------------------------------
    def _export_74(self):
        assets = self._get_assets([('l10n_pe_is_leasing', '=', True)])
        self._require(assets, 'l10n_pe_leasing_contract', 'Nº contrato leasing')
        self._require(assets, 'l10n_pe_leasing_date', 'Fecha del contrato')
        lines = []
        for asset in assets:
            lines.append([
                self._period_71(),                                    # 1
                asset.id,                                             # 2 CUO
                'M%d' % asset.id,                                     # 3
                self._ple_text(asset.l10n_pe_ple_catalog, 1, '9'),    # 4
                self._ple_text(asset.l10n_pe_leasing_contract, 20),   # 5
                self._ple_date(asset.l10n_pe_leasing_date),           # 6
                self._asset_code(asset),                              # 7
                self._ple_date(asset.l10n_pe_leasing_start
                               or asset.acquisition_date),            # 8
                asset.l10n_pe_leasing_installments or 0,              # 9
                self._ple_amount(asset.l10n_pe_leasing_total),        # 10
                '1',                                                  # 11 estado
            ])
        return self._make_file('070400', lines)

    # ------------------------------------------------------------------
    # 4.1 — Retenciones Art. 34 inc. e) y f) LIR (10 campos)
    # ------------------------------------------------------------------
    def _export_41(self):
        date_from, date_to = self._month_range()
        records = self.env['l10n_pe.ple.withholding'].search([
            ('company_id', '=', self.company_id.id),
            ('date', '>=', date_from), ('date', '<=', date_to),
        ], order='date, id')
        lines = []
        for record in records:
            doc_code, doc_number, name = self._partner_doc(record.partner_id)
            lines.append([
                self._period_month(),                       # 1
                record.id,                                  # 2 CUO
                'M%d' % record.id,                          # 3
                self._ple_date(record.date),                # 4
                doc_code,                                   # 5
                doc_number,                                 # 6
                name,                                       # 7
                self._ple_amount(record.gross_amount),      # 8
                self._ple_amount(-abs(record.withheld_amount)),  # 9
                '1',                                        # 10 estado
            ])
        return self._make_file_monthly('040100', lines)

    # ------------------------------------------------------------------
    # 9.1 / 9.2 — Registro de Consignaciones
    # ------------------------------------------------------------------
    CONSIGNMENT_KINDS = {
        '090100': ('out_delivery', 'out_return', 'out_sale'),
        '090200': ('in_receipt', 'in_return', 'in_sale'),
    }

    def _consignment_moves(self, kinds, date_from, date_to):
        return self.env['stock.move'].search([
            ('company_id', '=', self.company_id.id),
            ('state', '=', 'done'),
            ('picking_id.l10n_pe_consignment', 'in', kinds),
            ('date', '>=', datetime.combine(date_from, time.min)),
            ('date', '<=', datetime.combine(date_to, time.max)),
        ], order='product_id, date, id')

    @api.model
    def _consignment_qty(self, move):
        return move.quantity or move.product_uom_qty

    def _guia_parts(self, picking):
        """(serie, número) de la guía de remisión del albarán."""
        number = (getattr(picking, 'l10n_latam_document_number', False)
                  or picking.name or '')
        if '-' in number:
            left, _sep, right = number.rpartition('-')
            serie = ''.join(ch for ch in left if ch.isdigit()) or '0'
            num = ''.join(ch for ch in right if ch.isdigit()) or '0'
        else:
            serie = '0'
            num = ''.join(ch for ch in number if ch.isdigit()) or '0'
        return serie[:20], num[:20]

    def _consignment_cdp(self, picking):
        """Comprobante ligado (mejor esfuerzo, solo operaciones de venta):
        (tipo t10, fecha, serie, número)."""
        if picking.l10n_pe_consignment in ('out_sale', 'in_sale'):
            sale = getattr(picking, 'sale_id', False)
            invoices = sale and sale.invoice_ids.filtered(
                lambda m: m.state == 'posted')
            if invoices:
                invoice = invoices[0]
                serie, _sep, number = invoice.name.rpartition('-')
                return (invoice.l10n_latam_document_type_id.code or '00',
                        self._ple_date(invoice.invoice_date),
                        self._ple_text(serie, 20, '0'),
                        self._ple_text(number, 20, '0'))
        return '00', '', '0', '0'

    def _consignment_product_data(self, product):
        existence = (product.l10n_pe_type_of_existence or '99').zfill(2)
        code = self._ple_text(
            product.default_code, 24, 'P%06d' % product.id)
        uom_code = product.uom_id.l10n_pe_edi_measure_unit_code or 'NIU'
        return existence, code, uom_code

    def _export_9(self, book_code):
        date_from, date_to = self._month_range()
        kinds = self.CONSIGNMENT_KINDS[book_code]
        moves = self._consignment_moves(kinds, date_from, date_to)
        # saldo inicial por (producto, contraparte): entregas − devoluciones
        # − ventas anteriores al periodo
        prior = {}
        prior_moves = self.env['stock.move'].search([
            ('company_id', '=', self.company_id.id),
            ('state', '=', 'done'),
            ('picking_id.l10n_pe_consignment', 'in', kinds),
            ('date', '<', datetime.combine(date_from, time.min)),
        ])
        for move in prior_moves:
            key = (move.product_id, move.picking_id.partner_id)
            sign = 1 if move.picking_id.l10n_pe_consignment in (
                'out_delivery', 'in_receipt') else -1
            prior[key] = prior.get(key, 0.0) + sign * self._consignment_qty(move)

        lines = []
        rounding = 0.005
        seen_initial = set()

        def initial_row(product, partner):
            balance = prior.get((product, partner), 0.0)
            if abs(balance) < rounding or (product, partner) in seen_initial:
                return
            seen_initial.add((product, partner))
            lines.append(self._consignment_row(
                book_code, product, partner, 'I%d-%d' % (product.id, partner.id),
                date_from, '0', '0', ('00', '', '0', '0'), date_from,
                balance, 0.0, 0.0))

        for move in moves:
            picking = move.picking_id
            partner = picking.partner_id
            initial_row(move.product_id, partner)
            qty = self._consignment_qty(move)
            kind = picking.l10n_pe_consignment
            delivered = qty if kind in ('out_delivery', 'in_receipt') else 0.0
            returned = -qty if kind in ('out_return', 'in_return') else 0.0
            sold = -qty if kind in ('out_sale', 'in_sale') else 0.0
            move_date = move.date.date()
            serie, number = self._guia_parts(picking)
            lines.append(self._consignment_row(
                book_code, move.product_id, partner, move.id, move_date,
                serie, number, self._consignment_cdp(picking), move_date,
                delivered, returned, sold))
        return self._make_file_monthly(book_code, lines)

    def _consignment_row(self, book_code, product, partner, cuo, guia_date,
                         guia_serie, guia_number, cdp, op_date,
                         delivered, returned, sold):
        existence, code, uom_code = self._consignment_product_data(product)
        cdp_type, cdp_date, cdp_serie, cdp_number = cdp
        row = [
            self._period_month(),                     # 1
            '9',                                      # 2 catálogo propio (t13)
            existence,                                # 3 tipo existencia (t5)
            code,                                     # 4 código existencia
            cuo,                                      # 5 CUO
            self._ple_text(product.display_name, 80),  # 6
            uom_code,                                 # 7 UM (t6)
            self._ple_date(guia_date),                # 8 fecha guía
            guia_serie,                               # 9 serie guía
            guia_number,                              # 10 número guía
            cdp_type,                                 # 11 tipo CdP
            cdp_date,                                 # 12 fecha CdP (op)
            cdp_serie,                                # 13 serie CdP
            cdp_number,                               # 14 número CdP
            self._ple_date(op_date),                  # 15 fecha entrega/devol.
        ]
        if book_code == '090100':
            doc_code, doc_number, name = self._partner_doc(partner)
            row += [doc_code, doc_number, name]       # 16-18 consignatario
        else:
            ruc = (partner.vat or '').strip()
            row += [self._ple_text(ruc, 11, '-'),
                    self._ple_text(partner.name, 100, '-')]  # 16-17 consignador
        row += [
            self._ple_amount(delivered),              # entregada / recibida
            self._ple_amount(returned),               # devuelta (−)
            self._ple_amount(sold),                   # vendida (−)
            '1',                                      # estado
        ]
        return row

    # ------------------------------------------------------------------
    # Formatos simplificados (5.2/5.4, 8.3, 14.2) — mensuales
    # ------------------------------------------------------------------
    @api.model
    def _serie_folio(self, number):
        """(serie, folio) del número de documento: el folio es el último
        grupo de dígitos, la serie lo que lo precede (sin guiones)."""
        matches = list(re.finditer(r'\d+', number or ''))
        if not matches:
            return '', ''
        last = matches[-1]
        serie = number[:last.start()].replace('-', '').strip('/ ')
        return self._ple_text(serie, 20), last.group()

    def _invoice_amounts(self, move):
        """(BI gravada, IGV/IPM, ICBPER, otros conceptos) con signo
        (negativos en notas de crédito)."""
        sign = -1 if move.move_type in ('in_refund', 'out_refund') else 1
        icbper = 0.0
        for line in move.line_ids:
            if line.tax_line_id and 'ICBPER' in (
                    line.tax_line_id.name or '').upper():
                icbper += abs(line.balance)
        igv = max(move.amount_tax - icbper, 0.0)
        base = move.amount_untaxed if igv else 0.0
        others = move.amount_untaxed if not igv else 0.0
        return (sign * base, sign * igv, sign * icbper, sign * others)

    def _invoice_rate(self, move):
        """TC #.### si el documento no está en soles; '' en caso contrario."""
        if (move.currency_id != self.company_id.currency_id
                and move.amount_total):
            return '%.3f' % abs(move.amount_total_signed / move.amount_total)
        return ''

    def _reversed_doc(self, move):
        """(fecha, tipo, serie, número) del comprobante modificado (NC/ND)."""
        origin = move.reversed_entry_id
        if not origin:
            return '', '', '', ''
        serie, folio = self._serie_folio(
            origin.l10n_latam_document_number or origin.name)
        return (self._ple_date(origin.invoice_date or origin.date),
                origin.l10n_latam_document_type_id.code or '00',
                serie, folio)

    def _invoice_moves(self, move_types):
        date_from, date_to = self._month_range()
        return self.env['account.move'].search([
            ('company_id', '=', self.company_id.id),
            ('move_type', 'in', move_types),
            ('state', '=', 'posted'),
            ('date', '>=', date_from), ('date', '<=', date_to),
        ], order='date, id')

    def _export_52(self):
        """5.2 Diario Simplificado — misma estructura de 21 campos que el
        5.1: una línea por apunte contable del mes."""
        date_from, date_to = self._month_range()
        moves = self.env['account.move'].search([
            ('company_id', '=', self.company_id.id),
            ('state', '=', 'posted'),
            ('date', '>=', date_from), ('date', '<=', date_to),
        ], order='date, id')
        lines = []
        for move in moves:
            doc_type = move.l10n_latam_document_type_id.code or '00'
            serie, folio = self._serie_folio(
                move.l10n_latam_document_number or move.name)
            gloss_move = (getattr(move, 'l10n_pe_gloss', '')
                          or move.ref or move.name)
            for line in move.line_ids:
                if line.display_type in ('line_section', 'line_note'):
                    continue
                lines.append([
                    self._period_month(),                        # 1
                    move.id,                                     # 2 CUO
                    'M%d' % line.id,                             # 3
                    self._ple_text(line.account_id.code, 24),    # 4
                    '',                                          # 5 unidad op.
                    '',                                          # 6 c. costos
                    (line.currency_id or move.currency_id).name,  # 7 (t4)
                    '',                                          # 8 (op)
                    '',                                          # 9 (op)
                    doc_type,                                    # 10 (t10)
                    serie,                                       # 11 (op)
                    folio or '-',                                # 12
                    self._ple_date(move.date),                   # 13 contable
                    self._ple_date(move.invoice_date_due),       # 14 (op)
                    self._ple_date(move.invoice_date or move.date),  # 15
                    self._ple_text(
                        getattr(line, 'l10n_pe_gloss', '')
                        or line.name or gloss_move, 200),        # 16 glosa
                    '',                                          # 17 (op)
                    self._ple_amount(line.debit),                # 18
                    self._ple_amount(line.credit),               # 19
                    '',                                          # 20 dato estr.
                    '1',                                         # 21 estado
                ])
        return self._make_file_monthly('050200', lines)

    def _export_54(self):
        """5.4 Plan contable del Diario Simplificado (8 campos, como 5.3)."""
        accounts = self.env['account.account'].with_company(
            self.company_id).search([], order='code')
        period = '%04d%s01' % (self.year, self.month)
        lines = []
        for account in accounts:
            lines.append([
                period,                                          # 1
                self._ple_text(account.code, 24),                # 2
                self._ple_text(account.name, 100),               # 3
                '01',                                            # 4 PCGE (t17)
                '',                                              # 5 (op)
                '',                                              # 6 (op)
                '',                                              # 7 (op)
                '1',                                             # 8 estado
            ])
        return self._make_file_monthly('050400', lines)

    def _simplified_invoice_row(self, move):
        """Campos 1-23 comunes de 8.3 y 14.2 (sin la cola de opcionales)."""
        if move.move_type.startswith('in_'):
            # en compras el número del CdP es el del proveedor (referencia)
            number = (move.ref or move.l10n_latam_document_number
                      or move.name)
        else:
            number = move.l10n_latam_document_number or move.name
        serie, folio = self._serie_folio(number)
        doc_code, doc_number, name = self._partner_doc(move.partner_id)
        base, igv, icbper, others = self._invoice_amounts(move)
        total = base + igv + icbper + others
        return [
            self._period_month(),                                # 1
            move.id,                                             # 2 CUO
            'M%d' % move.id,                                     # 3
            self._ple_date(move.invoice_date or move.date),      # 4
            self._ple_date(move.invoice_date_due),               # 5 (op)
            move.l10n_latam_document_type_id.code or '00',       # 6 (t10)
            serie,                                               # 7
            folio or '-',                                        # 8
            '',                                                  # 9 (op)
            doc_code,                                            # 10
            doc_number,                                          # 11
            name,                                                # 12
            self._ple_amount(base),                              # 13
            self._ple_amount(igv),                               # 14
            self._ple_amount(icbper),                            # 15
            self._ple_amount(others),                            # 16
            self._ple_amount(total),                             # 17
            move.currency_id.name,                               # 18 (op)
            self._invoice_rate(move),                            # 19 (op)
            *self._reversed_doc(move),                           # 20-23
        ]

    def _export_83(self):
        """8.3 Registro de Compras Simplificado (32 campos)."""
        lines = []
        for move in self._invoice_moves(('in_invoice', 'in_refund')):
            row = self._simplified_invoice_row(move)
            row += ['', '',                                      # 24-25 detracción
                    '',                                          # 26 retención
                    '',                                          # 27 clasificación
                    '', '', '',                                  # 28-30 errores
                    '',                                          # 31 medio de pago
                    '1']                                         # 32 estado
            lines.append(row)
        return self._make_file_monthly('080300', lines)

    def _export_142(self):
        """14.2 Registro de Ventas e Ingresos Simplificado (26 campos)."""
        lines = []
        for move in self._invoice_moves(('out_invoice', 'out_refund')):
            row = self._simplified_invoice_row(move)
            row += ['',                                          # 24 error 1
                    '',                                          # 25 medio de pago
                    '1']                                         # 26 estado
            lines.append(row)
        return self._make_file_monthly('140200', lines)

    # ------------------------------------------------------------------
    # Libro 10 — Registro de Costos (anual, MM=00 en el nombre)
    # ------------------------------------------------------------------
    def _cost_records(self, model):
        return self.env[model].search([
            ('company_id', '=', self.company_id.id),
            ('year', '=', self.year),
        ])

    def _export_101(self):
        lines = []
        for record in self._cost_records('l10n_pe.ple.cost.sales'):
            lines.append([
                self._period_71(),                               # 1 ejercicio
                self._ple_amount(record.initial_finished),       # 2
                self._ple_amount(record.production_cost),        # 3
                self._ple_amount(-abs(record.final_finished)),   # 4 (−)
                self._ple_amount(record.adjustments),            # 5
                '1',                                             # 6 estado
            ])
        return self._make_file('100100', lines)

    def _export_102(self):
        Element = self.env['l10n_pe.ple.cost.element']
        lines = []
        for record in self._cost_records('l10n_pe.ple.cost.element').sorted(
                key=lambda r: r.month):
            row = ['%04d%s00' % (record.year, record.month)]     # 1 periodo
            row += [self._ple_amount(record[column])
                    for column in Element.ELEMENT_COLUMNS]       # 2-7
            row.append('1')                                      # 8 estado
            lines.append(row)
        return self._make_file('100200', lines)

    def _export_103(self):
        Element = self.env['l10n_pe.ple.cost.element']
        lines = []
        for record in self._cost_records('l10n_pe.ple.cost.production'):
            row = [
                self._period_71(),                               # 1 ejercicio
                self._ple_text(record.process_code, 10),         # 2
                self._ple_text(record.process_name, 100),        # 3
            ]
            row += [self._ple_amount(record[column])
                    for column in Element.ELEMENT_COLUMNS]       # 4-9
            row += [
                self._ple_amount(record.initial_wip),            # 10
                self._ple_amount(-abs(record.final_wip)),        # 11 (−)
                self._ple_text(record.grouping_code, 1),         # 12 (t21)
                '1',                                             # 13 estado
            ]
            lines.append(row)
        return self._make_file('100300', lines)

    def _export_104(self):
        lines = []
        for record in self._cost_records('l10n_pe.ple.cost.center'):
            lines.append([
                self._period_71(),                               # 1 periodo
                record.id,                                       # 2 correlativo
                self._ple_text(record.operation_unit_code, 24),  # 3 (op)
                self._ple_text(record.operation_unit_name, 100),  # 4 (op)
                self._ple_text(record.cost_center_code, 24),     # 5 (op)
                self._ple_text(record.cost_center_name, 100),    # 6 (op)
                '1',                                             # 7 estado
            ])
        return self._make_file('100400', lines)

    # ------------------------------------------------------------------
    # 3.8 — Inversiones mobiliarias, cta. 30 (12 campos)
    # ------------------------------------------------------------------
    def _export_38(self):
        records = self.env['l10n_pe.ple.investment'].search([
            ('company_id', '=', self.company_id.id),
            ('date', '=', self.balance_date),
        ], order='id')
        lines = []
        for record in records:
            if record.partner_id:
                doc_code, doc_number, name = self._partner_doc(
                    record.partner_id)
            else:
                doc_code, doc_number = '0', '-'
                name = self._ple_text(record.issuer_name, 100, '-')
            lines.append([
                self._period_lib(),                          # 1
                record.id,                                   # 2 CUO
                'M%d' % record.id,                           # 3
                doc_code,                                    # 4
                doc_number,                                  # 5
                name,                                        # 6
                (record.title_code or '').zfill(2),          # 7 (t15)
                self._ple_amount(record.nominal_value),      # 8
                record.quantity,                             # 9
                self._ple_amount(record.book_cost),          # 10
                self._ple_amount(-abs(record.provision)),    # 11
                '1',                                         # 12 estado
            ])
        return self._make_file_lib('030800', lines)

    # ------------------------------------------------------------------
    # 3.9 — Intangibles, cta. 34 (9 campos)
    # ------------------------------------------------------------------
    INTANGIBLE_ACCOUNT_PREFIX = '34'

    def _export_39(self):
        assets = self.env['account.asset'].search([
            ('company_id', '=', self.company_id.id),
            ('state', 'in', ('open', 'paused', 'close')),
            ('parent_id', '=', False),
            ('account_asset_id.code', '=like',
             self.INTANGIBLE_ACCOUNT_PREFIX + '%'),
            ('acquisition_date', '<=', self.balance_date),
            '|', ('disposal_date', '=', False),
            ('disposal_date', '>', self.balance_date),
        ], order='acquisition_date, id')
        dep_sums = self._depreciation_sums(assets, date_to=self.balance_date)
        lines = []
        for asset in assets:
            total_dep = sum(dep_sums[asset.id])
            lines.append([
                self._period_lib(),                          # 1
                asset.id,                                    # 2 CUO
                'M%d' % asset.id,                            # 3
                self._ple_date(asset.acquisition_date),      # 4 inicio operación
                self._ple_text(asset.account_asset_id.code, 24),  # 5
                self._ple_text(asset.name, 40),              # 6
                self._ple_amount(asset.original_value),      # 7 valor contable
                self._ple_amount(-abs(total_dep)),           # 8 amortización (−)
                '1',                                         # 9 estado
            ])
        return self._make_file_lib('030900', lines)

    # ------------------------------------------------------------------
    # 3.19 — Estado de cambios en el patrimonio neto (16 campos)
    # ------------------------------------------------------------------
    def _export_319(self):
        Equity = self.env['l10n_pe.ple.equity']
        records = Equity.search([
            ('company_id', '=', self.company_id.id),
            ('date', '=', self.balance_date),
        ], order='id')
        lines = []
        for record in records:
            row = [
                self._period_lib(),                          # 1
                (record.catalog_code or '01').zfill(2),      # 2 (t22)
                self._ple_text(record.rubric_id.name, 6),    # 3 (t34)
            ]
            row += [self._ple_amount(record[column])
                    for column in Equity.EQUITY_COLUMNS]     # 4-15
            row.append('1')                                  # 16 estado
            lines.append(row)
        return self._make_file_lib('031900', lines)
