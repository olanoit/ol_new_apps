from odoo import _, fields, models

from odoo.exceptions import UserError

from .sire_api import SIRE_UPLOAD_ADJUSTMENT_ENDPOINT
from .sire_validation import AMOUNT_TOLERANCE, IGV_RATES, IVAP_RATES, tax_mismatch

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

    operation_ids = fields.One2many(
        'l10n_pe.sire.operation', 'res_id', string='Operaciones con SUNAT', copy=False,
        domain=[('res_model', '=', 'l10n_pe.sire.rvie')])
    invalid_line_ids = fields.One2many(
        'l10n_pe.sire.rvie.line', 'sire_id', string='Observaciones', copy=False,
        domain=[('type_line', '=', 'system'), ('check_detail', '!=', False)])

    _period_uniq = models.Constraint(
        'unique (company_id, year, month)',
        'Ya existe un periodo RVIE para esta compañía y este mes.')

    def _sire_book_type(self):
        return 'rvie'

    def _sire_poll_cron_xmlid(self):
        return 'al_l10n_pe_sire.ir_cron_sire_rvie_poll'

    def _sire_ple_book_code(self):
        return '140400'

    def _sire_upload_book_code(self):
        return '140000'

    def _sire_replacement_process_code(self):
        # Anexo I del manual de servicios web: 3 = reemplazo de la
        # propuesta del RVIE (el 61 es el del RCE).
        return '3'

    def _sire_accept_endpoint(self):
        return ('/libros/rvie/propuesta/web/propuesta/%s/aceptapropuesta'
                % self._sire_period())

    def _sire_preliminary_endpoint(self):
        return ('/libros/rvierce/gestionlibro/web/registroslibros/%s/registrapreliminar'
                % self._sire_period())

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
        return self.env['account.move'].search(
            self._sire_system_domain(('out_invoice', 'out_refund'), 'invoice_date') + [
                ('l10n_latam_document_type_id.code', 'not in', RVIE_EXCLUDED_DOC_TYPES),
            ], order='invoice_date, name')

    def _sire_system_line_vals(self, move):
        sign = self._sire_move_sign(move)
        cancelled = move.state == 'cancel'
        amounts = self._sire_amount_split(move)
        serie, folio = self._sire_serie_folio(move)
        doc_code = move.l10n_latam_document_type_id.code or ''
        rate = self._sire_move_rate(move)
        partner = move.commercial_partner_id

        def amount(value):
            return 0.0 if cancelled else round(sign * value, 2)

        # El RVIE no distingue destinos: todo lo gravado va a la misma columna.
        taxed = amounts['taxed'] + amounts['taxed_dgng'] + amounts['taxed_dng']
        igv = amounts['igv'] + amounts['igv_dgng'] + amounts['igv_dng']

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
            'tipo_doc_identidad': partner.l10n_latam_identification_type_id.l10n_pe_vat_code or '',
            'nro_doc_identidad': partner.vat or '',
            'razon_social': partner.name or '',
            'valor_exportacion': amount(amounts['export']),
            'bi_gravada': 0.0 if discount_columns else amount(taxed),
            'dscto_bi': amount(taxed) if discount_columns else 0.0,
            'igv_ipm': 0.0 if discount_columns else amount(igv),
            'dscto_igv': amount(igv) if discount_columns else 0.0,
            'mto_exonerado': amount(amounts['exonerated']),
            'mto_inafecto': amount(amounts['unaffected']),
            'isc': amount(amounts['isc']),
            'bi_ivap': amount(amounts['ivap_base']),
            'ivap': amount(amounts['ivap']),
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

    # ------------------------------------------------------------------
    # Servicios del manual de Ventas v22 (docs/sire/SERVICIOS_RVIE.md)
    # ------------------------------------------------------------------

    def _sire_inconsistency_summary_request(self, token, summary_type):
        # 5.21: GET (en el RCE es POST).
        return self._sire_get(
            token, '/libros/rvierce/resumen/web/resumeninconsistencias/%s' % self._sire_period(),
            params={'codTipoResumen': summary_type, 'codLibro': self._sire_upload_book_code()})

    def _sire_receipt_request(self, token, name):
        # 5.26
        return self._sire_get(
            token, '/libros/rvierce/gestionlibro/web/registroslibros/constancia/archivo',
            params={'nomArchivo': name})

    def _sire_preliminary_inconsistencies_path(self):
        # 5.24: la plantilla lleva {numCas}, pero el ejemplo del manual no, y
        # añade el formato al final; se sigue el ejemplo.
        return ('/libros/rvierce/casillas/inconsistenciaslibros/%s/reporteinconsistencia/txt'
                % self._sire_period())

    @staticmethod
    def _sire_rate_text(rate):
        return '%.3f' % rate

    def _sire_send_exchange_rates(self, rates):
        """5.11: cuerpo JSON. La tabla pide dd/mm/aaaa y moneda numérica; el
        ejemplo del manual usa aaaa-mm-dd y el código ISO, y es lo que se envía."""
        payload = [{
            'fecEmision': date.strftime('%Y-%m-%d'),
            'codMoneda': currency,
            'mtoTipoCambio': self._sire_rate_text(rate),
        } for date, currency, rate in rates]
        return self._sire_json_call(
            'exchange_rate', 'POST',
            '/libros/rvie/propuesta/web/masivo/%s/guardacomplementomasivo' % self._sire_period(),
            payload, detail=_('%s tipos de cambio enviados.', len(payload)))

    def _sire_send_line_exchange_rate(self, line):
        """5.12: tipo de cambio de un comprobante de la propuesta."""
        return self._sire_json_call(
            'exchange_rate_one', 'PUT',
            '/libros/rvie/propuesta/web/propuesta/%s/complementoindividual' % self._sire_period(),
            {'codCar': line.car_sunat, 'codMoneda': line.moneda,
             'mtoTipoCambio': self._sire_rate_text(line.tipo_cambio)},
            detail='%s-%s' % (line.serie_cp, line.nro_cp))

    def _sire_withdraw_lines(self, lines):
        """5.10: exclusión definitiva e irreversible, un CAR por llamada."""
        self._sire_check_dangerous()
        for line in self._sire_lines_of(lines):
            self._sire_json_call(
                'withdraw', 'POST',
                '/libros/rvie/propuesta/web/propuesta/%s/retiracomprobante' % self._sire_period(),
                params={'codCar': line.car_sunat, 'codSituacion': '0'},
                detail='%s %s-%s' % (line.tipo_cp, line.serie_cp, line.nro_cp))
        return True

    def _sire_delete_proposal_lines(self, lines):
        # 5.13: solo comprobantes agregados por el contribuyente.
        self._sire_check_dangerous()
        return self._sire_json_call(
            'delete_proposal', 'POST',
            '/libros/rvie/propuesta/web/propuesta/%s/eliminacomprobante' % self._sire_period(),
            self._sire_lines_cp(self._sire_lines_of(lines)),
            detail=_('%s comprobantes.', len(lines)))

    def _sire_delete_preliminary_lines(self, lines):
        # 5.14
        self._sire_check_dangerous()
        return self._sire_json_call(
            'delete_preliminary', 'PUT',
            '/libros/rvierce/gestionlibro/web/registroslibros/%s/comprobantepreliminar'
            % self._sire_period(),
            self._sire_lines_cp(self._sire_lines_of(lines)),
            detail=_('%s comprobantes.', len(lines)))

    def action_sire_delete_replacement(self):
        # 5.15
        self.ensure_one()
        self._sire_check_dangerous()
        return self._sire_json_call(
            'delete_replacement', 'PUT',
            '/libros/rvierce/gestionlibro/web/registroslibros/%s/eliminarreemplazo'
            % self._sire_period(), params={'codLibro': self._sire_upload_book_code()})

    def action_sire_delete_registered_preliminary(self):
        # 5.36: ``id`` dejó de ser obligatorio en la v22.
        self.ensure_one()
        self._sire_check_dangerous()
        operation = self._sire_json_call(
            'delete_registered', 'PUT',
            '/libros/rvierce/gestionlibro/web/registroslibros/%s/eliminapreliminar'
            % self._sire_period(), {'codTipoRegistro': '14'},
            params={'codLibro': self._sire_upload_book_code()})
        self.preliminary_registered = False
        return operation

    # ------------------------------------------------------------------
    # Nuevos comprobantes y ajustes posteriores (docs/sire/ESTRUCTURAS_TXT.md)
    # ------------------------------------------------------------------

    def _sire_new_cp_identifier(self):
        # Tabla 6: RUC-CPF-AAAAMM-NN, anexo 2 (campos 1-33 del reemplazo).
        return 'CPF'

    def _sire_adjustment_row(self, line, car_orig):
        """Anexo 4 [R.S. 138-2023]: campos 1-33 y el CAR del anotado en el 41.

        Los campos 34 a 40 no se envían (los completa SUNAT), así que el CAR
        original va justo después del 33, como la CLU en el reemplazo.
        """
        row = self._sire_replacement_row(line)
        clu = row[33:]
        return row[:33] + [car_orig] + clu

    def _sire_previous_row(self, move, state):
        """Anexo 5.1: ajuste de un periodo anterior al SIRE (registro de ventas PLE)."""
        period = self._sire_move_period_record(move)
        vals = period._sire_system_line_vals(move)
        serie, folio = period._sire_serie_folio(move)
        currency = vals['moneda'] or 'PEN'
        rate = vals['tipo_cambio'] or 1.0
        return [
            '%s00' % period._sire_period(),
            self._sire_text(move.name, 40).replace('&', ''),
            'M1',
            self._sire_fmt_date(vals['fecha_emision']),
            self._sire_fmt_date(vals['fecha_vencimiento']) if vals['tipo_cp'] == '14' else '',
            vals['tipo_cp'], serie, folio, '',
            vals['tipo_doc_identidad'], vals['nro_doc_identidad'],
            self._sire_text(vals['razon_social'], 100),
            self._sire_fmt_amount(vals['valor_exportacion']),
            self._sire_fmt_amount(vals['bi_gravada']),
            self._sire_fmt_amount(vals['dscto_bi']),
            self._sire_fmt_amount(vals['igv_ipm']),
            self._sire_fmt_amount(vals['dscto_igv']),
            self._sire_fmt_amount(vals['mto_exonerado']),
            self._sire_fmt_amount(vals['mto_inafecto']),
            self._sire_fmt_amount(vals['isc']),
            self._sire_fmt_amount(vals['bi_ivap']),
            self._sire_fmt_amount(vals['ivap']),
            self._sire_fmt_amount(vals['icbper']),
            self._sire_fmt_amount(vals['otros_tributos']),
            self._sire_fmt_amount(vals['total_cp']),
            currency, '%.3f' % rate,
            self._sire_fmt_date(vals.get('fecha_emision_mod')),
            vals.get('tipo_cp_mod') or '', vals.get('serie_cp_mod') or '',
            vals.get('nro_cp_mod') or '',
            '', '', '', state,
        ]

    def _sire_upload_previous_adjustment(self, moves, state):
        """5.7: ajustes de periodos anteriores al SIRE, referidos al último generado."""
        self.ensure_one()
        if self.state != 'done' and not self.preliminary_registered:
            raise UserError(_('Envíe los ajustes de periodos anteriores desde el último '
                              'periodo generado en el SIRE.'))
        correlative = self._sire_next_correlative('adjustment_previous')
        operation = self._sire_tus_upload(
            'adjustment_previous', self._sire_le_name('140400', '04', correlative),
            [self._sire_previous_row(move, state) for move in moves],
            '7', SIRE_UPLOAD_ADJUSTMENT_ENDPOINT)
        operation.adjustment_kind = 'adjustment_previous'
        return operation

    def _sire_line_errors(self, line):
        errors = super()._sire_line_errors(line)
        date_from, dummy = self._sire_period_bounds()
        if line.fecha_emision and line.fecha_emision < date_from:
            errors.append(_('La fecha de emisión es anterior al periodo.'))
        if line.tipo_cp == '01' and line.tipo_doc_identidad != '6' \
                and not line.valor_exportacion:
            errors.append(_('Una factura exige el RUC del cliente (salvo exportación).'))
        if line.estado_cp == '2':
            return errors
        if tax_mismatch(line.bi_gravada, line.igv_ipm, IGV_RATES) \
                or tax_mismatch(line.dscto_bi, line.dscto_igv, IGV_RATES):
            errors.append(_('El IGV/IPM no corresponde a la base gravada (18 % o 10 %).'))
        if tax_mismatch(line.bi_ivap, line.ivap, IVAP_RATES):
            errors.append(_('El IVAP no corresponde a su base (4 %).'))
        components = sum((
            line.valor_exportacion, line.bi_gravada, line.dscto_bi, line.igv_ipm,
            line.dscto_igv, line.mto_exonerado, line.mto_inafecto, line.isc,
            line.bi_ivap, line.ivap, line.icbper, line.otros_tributos))
        if abs(components - line.total_cp) > AMOUNT_TOLERANCE:
            errors.append(_('El total %(total).2f no es la suma de bases e impuestos '
                            '(%(sum).2f).', total=line.total_cp, sum=components))
        return errors

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
        ] + ([line.clu] if line.clu else [])


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

    def action_sire_withdraw(self):
        """Exclusión definitiva e irreversible de facturas y notas de crédito (5.10)."""
        lines = self._sire_proposal_lines()
        return lines._sire_period_record()._sire_withdraw_lines(lines)

    def action_sire_send_exchange_rate(self):
        """Tipo de cambio de cada comprobante seleccionado, con el del sistema (5.12)."""
        lines = self._sire_proposal_lines()
        period = lines._sire_period_record()
        for line in lines:
            system = period.system_line_ids.filtered(lambda l: l.car_sunat == line.car_sunat)[:1]
            if not system.tipo_cambio:
                raise UserError(_('El comprobante %(doc)s no tiene tipo de cambio en el '
                                  'sistema.', doc='%s-%s' % (line.serie_cp, line.nro_cp)))
            period._sire_send_line_exchange_rate(system)
        return True

