from odoo import fields, models

# Tipos de documento que no van al RCE (recibos por honorarios van al RHE)
RCE_EXCLUDED_DOC_TYPES = ('02', '91', '97', '98')
# Comprobantes donde el CAR usa el RUC del adquiriente (liquidaciones de compra, servicios públicos)
RCE_SELF_ISSUED_DOC_TYPES = ('46', '50', '51', '52', '53', '54')
# Tipos con fecha de vencimiento/pago obligatoria en el TXT de importación
RCE_DUE_DATE_DOC_TYPES = ('14', '46', '50', '51', '52', '53', '54')


class L10nPeSireRce(models.Model):
    """Periodo del Registro de Compras Electrónico (RCE)."""
    _name = 'l10n_pe.sire.rce'
    _inherit = ['l10n_pe.sire.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'SIRE — Registro de Compras Electrónico'
    _order = 'year desc, month desc, id desc'

    sire_line_ids = fields.One2many(
        'l10n_pe.sire.rce.line', 'sire_id', string='Líneas SIRE', copy=False,
        domain=[('type_line', '=', 'sire')])
    system_line_ids = fields.One2many(
        'l10n_pe.sire.rce.line', 'sire_id', string='Líneas del sistema', copy=False,
        domain=[('type_line', '=', 'system')])
    diff_line_ids = fields.One2many(
        'l10n_pe.sire.rce.line', 'sire_id', string='Diferencias', copy=False,
        domain=[('compare_state', 'in', ('1', '2', '3'))])

    def _sire_book_type(self):
        return 'rce'

    def _sire_ple_book_code(self):
        return '080400'

    def _sire_upload_book_code(self):
        return '080000'

    def _sire_replacement_process_code(self):
        # Anexo I del manual de servicios web: 61 = reemplazo de la
        # propuesta del RCE (el 3 es el del RVIE).
        return '61'

    def _sire_accept_endpoint(self):
        return ('/libros/rce/propuesta/web/registroslibros/%s/aceptarpropuesta'
                % self._sire_period())

    def _sire_preliminary_endpoint(self):
        return ('/libros/rce/preliminar/web/registroslibros/%s/registrapreliminares'
                % self._sire_period())

    def _sire_proposal_endpoint(self):
        return ('/libros/rce/propuesta/web/propuesta/%s/exportacioncomprobantepropuesta'
                % self._sire_period())

    def _sire_min_columns(self):
        return 41

    def _sire_parse_row(self, cols):
        return {
            'car_sunat': cols[3],
            'fecha_emision': self._sire_parse_date(cols[4]),
            'fecha_vencimiento': self._sire_parse_date(cols[5]),
            'tipo_cp': cols[6],
            'serie_cp': cols[7],
            'anio_dam': cols[8],
            'nro_cp': cols[9].lstrip('0'),
            'nro_final': cols[10],
            'tipo_doc_identidad': cols[11],
            'nro_doc_identidad': cols[12],
            'razon_social': cols[13],
            'bi_gravada_dg': self._sire_parse_float(cols[14]),
            'igv_dg': self._sire_parse_float(cols[15]),
            'bi_gravada_dgng': self._sire_parse_float(cols[16]),
            'igv_dgng': self._sire_parse_float(cols[17]),
            'bi_gravada_dng': self._sire_parse_float(cols[18]),
            'igv_dng': self._sire_parse_float(cols[19]),
            'valor_adq_ng': self._sire_parse_float(cols[20]),
            'isc': self._sire_parse_float(cols[21]),
            'icbper': self._sire_parse_float(cols[22]),
            'otros_tributos': self._sire_parse_float(cols[23]),
            'total_cp': self._sire_parse_float(cols[24]),
            'moneda': cols[25],
            'tipo_cambio': self._sire_parse_float(cols[26]),
            'fecha_emision_mod': self._sire_parse_date(cols[27]),
            'tipo_cp_mod': cols[28],
            'serie_cp_mod': cols[29],
            'cod_dam': cols[30],
            'nro_cp_mod': cols[31],
            'clasif_bienes': cols[32],
            'id_proyecto': cols[33],
            'porc_participacion': cols[34],
            'imb': cols[35],
            'car_orig': cols[36],
            'detraccion': 'Si' if cols[37] == 'D' else 'No',
            'tipo_nota': cols[38],
            'estado_cp': cols[39] if cols[39] in ('1', '2') else '3',
            'incal': cols[40],
        }

    def _sire_system_moves(self):
        date_from = fields.Date.to_date('%04d-%s-01' % (self.year, self.month))
        date_to = fields.Date.end_of(date_from, 'month')
        return self.env['account.move'].search([
            ('company_id', '=', self.company_id.id),
            ('move_type', 'in', ('in_invoice', 'in_refund')),
            ('state', 'in', ('posted', 'cancel')),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('l10n_latam_document_type_id.code', 'not in', RCE_EXCLUDED_DOC_TYPES),
        ], order='invoice_date, name')

    def _sire_system_line_vals(self, move):
        sign = self._sire_move_sign(move)
        cancelled = move.state == 'cancel'
        amounts = self._sire_amount_split(move)
        serie, folio = self._sire_serie_folio(move)
        doc_code = move.l10n_latam_document_type_id.code or ''
        issuer_ruc = (self.company_id.vat if doc_code in RCE_SELF_ISSUED_DOC_TYPES
                      else move.partner_id.vat)
        rate = self._sire_move_rate(move)

        def amount(value):
            return 0.0 if cancelled else round(sign * value, 2)

        vals = {
            'car_sunat': self._sire_car_sunat(move, issuer_ruc),
            'fecha_emision': move.invoice_date,
            'fecha_vencimiento': move.invoice_date_due or False,
            'tipo_cp': doc_code,
            'serie_cp': serie,
            'nro_cp': folio,
            'tipo_doc_identidad': move.partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code or '',
            'nro_doc_identidad': move.partner_id.vat or '',
            'razon_social': move.partner_id.name or '',
            'bi_gravada_dg': amount(amounts['taxed']),
            'igv_dg': amount(amounts['igv']),
            'valor_adq_ng': amount(amounts['exonerated'] + amounts['unaffected']),
            'isc': amount(amounts['isc']),
            'icbper': amount(amounts['icbper']),
            'otros_tributos': amount(amounts['other_taxes']),
            'total_cp': amount(abs(move.amount_total_signed)),
            'moneda': move.currency_id.name,
            'tipo_cambio': 0.0 if cancelled else rate,
            'clasif_bienes': move.l10n_pe_sire_goods_class or '',
            'detraccion': 'Si' if getattr(move, 'l10n_pe_detraction_applies', False) else 'No',
            'estado_cp': '2' if cancelled else '1',
        }
        if doc_code == '07':
            vals.update(self._sire_reversed_doc_vals(move))
            vals['tipo_nota'] = getattr(move, 'l10n_pe_edi_refund_reason', '') or ''
        return vals

    def _sire_xlsx_headers(self):
        return [
            'RUC', 'Razón social', 'Periodo', 'CAR SUNAT', 'Fecha de emisión',
            'Fecha Vcto/Pago', 'Tipo CP/Doc.', 'Serie del CDP', 'Año',
            'Nro CP o Doc. Nro Inicial (Rango)', 'Nro Final (Rango)',
            'Tipo Doc Identidad', 'Nro Doc Identidad', 'Apellidos Nombres/Razón Social',
            'BI Gravado DG', 'IGV/IPM DG', 'BI Gravado DGNG', 'IGV/IPM DGNG',
            'BI Gravado DNG', 'IGV/IPM DNG', 'Valor Adq. NG', 'ISC', 'ICBPER',
            'Otros Trib/Cargos', 'Total CP', 'Moneda', 'Tipo de Cambio',
            'Fecha Emisión Doc Modificado', 'Tipo CP Modificado', 'Serie CP Modificado',
            'COD. DAM O DSI', 'Nro CP Modificado', 'Clasif de Bss y Sss',
            'ID Proyecto Operadores', 'PorcPart', 'IMB', 'CAR Orig/Ind E o I',
            'Detracción', 'Tipo de Nota', 'Est. Comp.', 'Incal',
        ]

    def _sire_xlsx_row(self, line):
        estado = dict(line._fields['estado_cp'].selection).get(line.estado_cp, '')
        return [
            self.company_id.vat or '', self.company_id.name or '', self._sire_period(),
            line.car_sunat or '', self._sire_fmt_date(line.fecha_emision),
            self._sire_fmt_date(line.fecha_vencimiento), line.tipo_cp or '',
            line.serie_cp or '', line.anio_dam or '', line.nro_cp or '',
            line.nro_final or '', line.tipo_doc_identidad or '',
            line.nro_doc_identidad or '', line.razon_social or '',
            line.bi_gravada_dg, line.igv_dg, line.bi_gravada_dgng, line.igv_dgng,
            line.bi_gravada_dng, line.igv_dng, line.valor_adq_ng, line.isc,
            line.icbper, line.otros_tributos, line.total_cp, line.moneda or '',
            self._sire_fmt_rate(line.tipo_cambio, line.moneda),
            self._sire_fmt_date(line.fecha_emision_mod), line.tipo_cp_mod or '',
            line.serie_cp_mod or '', line.cod_dam or '', line.nro_cp_mod or '',
            line.clasif_bienes or '', line.id_proyecto or '',
            line.porc_participacion or '', line.imb or '', line.car_orig or '',
            line.detraccion or '', line.tipo_nota or '', estado, line.incal or '',
        ]

    def _sire_replacement_row(self, line):
        due_date = (self._sire_fmt_date(line.fecha_vencimiento)
                    if line.tipo_cp in RCE_DUE_DATE_DOC_TYPES else '')
        return [
            self.company_id.vat or '',
            self.company_id.name or '',
            self._sire_period(),
            '',
            self._sire_fmt_date(line.fecha_emision),
            due_date,
            line.tipo_cp or '',
            line.serie_cp or '',
            line.anio_dam or '',
            line.nro_cp or '',
            line.nro_final or '',
            line.tipo_doc_identidad or '',
            line.nro_doc_identidad or '',
            line.razon_social or '',
            self._sire_fmt_amount(line.bi_gravada_dg),
            self._sire_fmt_amount(line.igv_dg),
            self._sire_fmt_amount(line.bi_gravada_dgng),
            self._sire_fmt_amount(line.igv_dgng),
            self._sire_fmt_amount(line.bi_gravada_dng),
            self._sire_fmt_amount(line.igv_dng),
            self._sire_fmt_amount(line.valor_adq_ng),
            self._sire_fmt_amount(line.isc),
            self._sire_fmt_amount(line.icbper),
            self._sire_fmt_amount(line.otros_tributos),
            self._sire_fmt_amount(line.total_cp),
            line.moneda or '',
            self._sire_fmt_rate(line.tipo_cambio, line.moneda),
            self._sire_fmt_date(line.fecha_emision_mod),
            line.tipo_cp_mod or '',
            line.serie_cp_mod or '',
            line.cod_dam or '',
            line.nro_cp_mod or '',
            line.clasif_bienes or '',
            line.id_proyecto or '',
            line.porc_participacion or '',
            line.imb or '',
            line.car_orig or '',
        ]


class L10nPeSireRceLine(models.Model):
    _name = 'l10n_pe.sire.rce.line'
    _inherit = 'l10n_pe.sire.line.mixin'
    _description = 'Línea SIRE RCE'

    sire_id = fields.Many2one(
        'l10n_pe.sire.rce', string='Periodo RCE', required=True,
        ondelete='cascade', index=True)
    company_id = fields.Many2one(related='sire_id.company_id', store=True)

    anio_dam = fields.Char(string='Año (DAM o DSI)')
    bi_gravada_dg = fields.Float(string='BI Gravado DG', digits=(16, 2))
    igv_dg = fields.Float(string='IGV/IPM DG', digits=(16, 2))
    bi_gravada_dgng = fields.Float(string='BI Gravado DGNG', digits=(16, 2))
    igv_dgng = fields.Float(string='IGV/IPM DGNG', digits=(16, 2))
    bi_gravada_dng = fields.Float(string='BI Gravado DNG', digits=(16, 2))
    igv_dng = fields.Float(string='IGV/IPM DNG', digits=(16, 2))
    valor_adq_ng = fields.Float(string='Valor Adq. NG', digits=(16, 2))
    cod_dam = fields.Char(string='Cod DAM o DSI')
    clasif_bienes = fields.Char(string='Clasif de Bss y Sss')
    id_proyecto = fields.Char(string='ID Proyecto Operadores')
    porc_participacion = fields.Char(string='PorcPart')
    imb = fields.Char(string='IMB')
    car_orig = fields.Char(string='CAR Orig/Ind E o I')
    detraccion = fields.Char(string='Detracción')
