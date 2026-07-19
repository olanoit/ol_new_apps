from odoo import fields, models

# Notas de venta y documentos internos que no van al RVIE
RVIE_EXCLUDED_DOC_TYPES = ('NV',)


class L10nPeSireRvie(models.Model):
    """Periodo del Registro de Ventas e Ingresos Electrónico (RVIE)."""
    _name = 'l10n_pe.sire.rvie'
    _inherit = ['l10n_pe.sire.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'SIRE — Registro de Ventas e Ingresos Electrónico'
    _order = 'year desc, month desc, id desc'

    sire_line_ids = fields.One2many(
        'l10n_pe.sire.rvie.line', 'sire_id', string='Líneas SIRE', copy=False,
        domain=[('type_line', '=', 'sire')])
    system_line_ids = fields.One2many(
        'l10n_pe.sire.rvie.line', 'sire_id', string='Líneas del sistema', copy=False,
        domain=[('type_line', '=', 'system')])
    diff_line_ids = fields.One2many(
        'l10n_pe.sire.rvie.line', 'sire_id', string='Diferencias', copy=False,
        domain=[('compare_state', 'in', ('1', '2', '3'))])

    def _sire_book_type(self):
        return 'rvie'

    def _sire_ple_book_code(self):
        return '140400'

    def _sire_proposal_endpoint(self):
        return '/libros/rvie/propuesta/web/propuesta/%s/exportapropuesta' % self._sire_period()

    def _sire_min_columns(self):
        return 40

    def _sire_parse_row(self, cols):
        return {
            'car_sunat': cols[3],
            'fecha_emision': self._sire_parse_date(cols[4]),
            'fecha_vencimiento': self._sire_parse_date(cols[5]),
            'tipo_cp': cols[6],
            'serie_cp': cols[7],
            'nro_cp': cols[8].lstrip('0'),
            'nro_final': cols[9],
            'tipo_doc_identidad': cols[10],
            'nro_doc_identidad': cols[11],
            'razon_social': cols[12],
            'valor_exportacion': self._sire_parse_float(cols[13]),
            'bi_gravada': self._sire_parse_float(cols[14]),
            'dscto_bi': self._sire_parse_float(cols[15]),
            'igv_ipm': self._sire_parse_float(cols[16]),
            'dscto_igv': self._sire_parse_float(cols[17]),
            'mto_exonerado': self._sire_parse_float(cols[18]),
            'mto_inafecto': self._sire_parse_float(cols[19]),
            'isc': self._sire_parse_float(cols[20]),
            'bi_ivap': self._sire_parse_float(cols[21]),
            'ivap': self._sire_parse_float(cols[22]),
            'icbper': self._sire_parse_float(cols[23]),
            'otros_tributos': self._sire_parse_float(cols[24]),
            'total_cp': self._sire_parse_float(cols[25]),
            'moneda': cols[26],
            'tipo_cambio': self._sire_parse_float(cols[27]),
            'fecha_emision_mod': self._sire_parse_date(cols[28]),
            'tipo_cp_mod': cols[29],
            'serie_cp_mod': cols[30],
            'nro_cp_mod': cols[31],
            'id_proyecto': cols[32],
            'tipo_nota': cols[33],
            'estado_cp': cols[34] if cols[34] in ('1', '2') else '3',
            'valor_gratuitas': self._sire_parse_float(cols[36]),
            'tipo_operacion': cols[37],
            'clu': cols[39],
        }

    def _sire_system_moves(self):
        date_from = fields.Date.to_date('%04d-%s-01' % (self.year, self.month))
        date_to = fields.Date.end_of(date_from, 'month')
        return self.env['account.move'].search([
            ('company_id', '=', self.company_id.id),
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('state', 'in', ('posted', 'cancel')),
            ('invoice_date', '>=', date_from),
            ('invoice_date', '<=', date_to),
            ('l10n_latam_document_type_id.code', 'not in', RVIE_EXCLUDED_DOC_TYPES),
        ], order='invoice_date, name')

    def _sire_system_line_vals(self, move):
        sign = self._sire_move_sign(move)
        cancelled = move.state == 'cancel'
        amounts = self._sire_amount_split(move)
        serie, folio = self._sire_serie_folio(move)
        doc_code = move.l10n_latam_document_type_id.code or ''
        rate = self._sire_move_rate(move)

        def amount(value):
            return 0.0 if cancelled else round(sign * value, 2)

        # NC de un comprobante de periodo anterior: los montos van a las
        # columnas de descuento; del mismo periodo, a las columnas normales.
        origin = move.reversed_entry_id
        discount_columns = (
            sign < 0 and origin and origin.invoice_date
            and origin.invoice_date.strftime('%Y%m') != '%04d%s' % (self.year, self.month))
        vals = {
            'car_sunat': self._sire_car_sunat(move, self.company_id.vat),
            'fecha_emision': move.invoice_date,
            'fecha_vencimiento': move.invoice_date_due or False,
            'tipo_cp': doc_code,
            'serie_cp': serie,
            'nro_cp': folio,
            'tipo_doc_identidad': move.partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code or '',
            'nro_doc_identidad': move.partner_id.vat or '',
            'razon_social': move.partner_id.name or '',
            'valor_exportacion': amount(amounts['export']),
            'bi_gravada': 0.0 if discount_columns else amount(amounts['taxed']),
            'dscto_bi': amount(amounts['taxed']) if discount_columns else 0.0,
            'igv_ipm': 0.0 if discount_columns else amount(amounts['igv']),
            'dscto_igv': amount(amounts['igv']) if discount_columns else 0.0,
            'mto_exonerado': amount(amounts['exonerated']),
            'mto_inafecto': amount(amounts['unaffected']),
            'isc': amount(amounts['isc']),
            'icbper': amount(amounts['icbper']),
            'otros_tributos': amount(amounts['other_taxes']),
            'total_cp': amount(abs(move.amount_total_signed)),
            'moneda': move.currency_id.name,
            'tipo_cambio': 0.0 if cancelled else rate,
            'valor_gratuitas': 0.0 if cancelled else round(amounts['free'], 2),
            'tipo_operacion': '' if doc_code == '07' else (
                getattr(move, 'l10n_pe_edi_operation_type', '') or ''),
            'estado_cp': '2' if cancelled else '1',
        }
        if doc_code in ('07', '08'):
            vals.update(self._sire_reversed_doc_vals(move))
            if doc_code == '07':
                vals['tipo_nota'] = getattr(move, 'l10n_pe_edi_refund_reason', '') or ''
        return vals

    def _sire_xlsx_headers(self):
        return [
            'RUC', 'Razón social', 'Periodo', 'CAR SUNAT', 'Fecha de emisión',
            'Fecha Vcto/Pago', 'Tipo CP/Doc.', 'Serie del CDP',
            'Nro CP o Doc. Nro Inicial (Rango)', 'Nro Final (Rango)',
            'Tipo Doc Identidad', 'Nro Doc Identidad', 'Apellidos Nombres/Razón Social',
            'Valor Facturado Exportación', 'BI Gravada', 'Dscto BI', 'IGV/IPM',
            'Dscto IGV/IPM', 'Mto Exonerado', 'Mto Inafecto', 'ISC', 'BI Grav IVAP',
            'IVAP', 'ICBPER', 'Otros Trib/Cargos', 'Total CP', 'Moneda',
            'Tipo de Cambio', 'Fecha Emisión Doc Modificado', 'Tipo CP Modificado',
            'Serie CP Modificado', 'Nro CP Modificado', 'ID Proyecto Operadores',
            'Tipo de Nota', 'Est. Comp.', 'Valor Op. Gratuitas', 'Tipo Operación', 'CLU',
        ]

    def _sire_xlsx_row(self, line):
        estado = dict(line._fields['estado_cp'].selection).get(line.estado_cp, '')
        return [
            self.company_id.vat or '', self.company_id.name or '', self._sire_period(),
            line.car_sunat or '', self._sire_fmt_date(line.fecha_emision),
            self._sire_fmt_date(line.fecha_vencimiento), line.tipo_cp or '',
            line.serie_cp or '', line.nro_cp or '', line.nro_final or '',
            line.tipo_doc_identidad or '', line.nro_doc_identidad or '',
            line.razon_social or '', line.valor_exportacion, line.bi_gravada,
            line.dscto_bi, line.igv_ipm, line.dscto_igv, line.mto_exonerado,
            line.mto_inafecto, line.isc, line.bi_ivap, line.ivap, line.icbper,
            line.otros_tributos, line.total_cp, line.moneda or '',
            self._sire_fmt_rate(line.tipo_cambio, line.moneda),
            self._sire_fmt_date(line.fecha_emision_mod), line.tipo_cp_mod or '',
            line.serie_cp_mod or '', line.nro_cp_mod or '', line.id_proyecto or '',
            line.tipo_nota or '', estado, line.valor_gratuitas,
            line.tipo_operacion or '', line.clu or '',
        ]

    def _sire_replacement_row(self, line):
        due_date = (self._sire_fmt_date(line.fecha_vencimiento)
                    if line.tipo_cp == '14' else '')
        return [
            self.company_id.vat or '',
            self.company_id.name or '',
            self._sire_period(),
            '',
            self._sire_fmt_date(line.fecha_emision),
            due_date,
            line.tipo_cp or '',
            line.serie_cp or '',
            line.nro_cp or '',
            line.nro_final or '',
            line.tipo_doc_identidad or '',
            line.nro_doc_identidad or '',
            line.razon_social or '',
            self._sire_fmt_amount(line.valor_exportacion),
            self._sire_fmt_amount(line.bi_gravada),
            self._sire_fmt_amount(line.dscto_bi),
            self._sire_fmt_amount(line.igv_ipm),
            self._sire_fmt_amount(line.dscto_igv),
            self._sire_fmt_amount(line.mto_exonerado),
            self._sire_fmt_amount(line.mto_inafecto),
            self._sire_fmt_amount(line.isc),
            self._sire_fmt_amount(line.bi_ivap),
            self._sire_fmt_amount(line.ivap),
            self._sire_fmt_amount(line.icbper),
            self._sire_fmt_amount(line.otros_tributos),
            self._sire_fmt_amount(line.total_cp),
            line.moneda or '',
            self._sire_fmt_rate(line.tipo_cambio, line.moneda),
            self._sire_fmt_date(line.fecha_emision_mod),
            line.tipo_cp_mod or '',
            line.serie_cp_mod or '',
            line.nro_cp_mod or '',
            line.id_proyecto or '',
            line.clu or '',
        ]


class L10nPeSireRvieLine(models.Model):
    _name = 'l10n_pe.sire.rvie.line'
    _inherit = 'l10n_pe.sire.line.mixin'
    _description = 'Línea SIRE RVIE'

    sire_id = fields.Many2one(
        'l10n_pe.sire.rvie', string='Periodo RVIE', required=True,
        ondelete='cascade', index=True)
    company_id = fields.Many2one(related='sire_id.company_id', store=True)

    valor_exportacion = fields.Float(string='Valor Facturado Exportación', digits=(16, 2))
    bi_gravada = fields.Float(string='BI Gravada', digits=(16, 2))
    dscto_bi = fields.Float(string='Dscto BI', digits=(16, 2))
    igv_ipm = fields.Float(string='IGV/IPM', digits=(16, 2))
    dscto_igv = fields.Float(string='Dscto IGV/IPM', digits=(16, 2))
    mto_exonerado = fields.Float(string='Mto Exonerado', digits=(16, 2))
    mto_inafecto = fields.Float(string='Mto Inafecto', digits=(16, 2))
    bi_ivap = fields.Float(string='BI Grav IVAP', digits=(16, 2))
    ivap = fields.Float(string='IVAP', digits=(16, 2))
    valor_gratuitas = fields.Float(string='Valor Op. Gratuitas', digits=(16, 2))
    id_proyecto = fields.Char(string='ID Proyecto Operadores')
    tipo_operacion = fields.Char(string='Tipo Operación')
    clu = fields.Char(string='CLU')
