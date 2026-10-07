from odoo import _, fields, models

from odoo.exceptions import UserError

from .sire_api import SIRE_UPLOAD_ADJUSTMENT_ENDPOINT, SIRE_UPLOAD_ENDPOINT
from .sire_validation import AMOUNT_TOLERANCE, IGV_RATES, tax_mismatch

# Tipos de documento que no van al RCE (recibos por honorarios van al RHE)
RCE_EXCLUDED_DOC_TYPES = ('02', '91', '97', '98')
# Comprobantes donde el CAR usa el RUC del adquiriente (liquidaciones de compra, servicios públicos)
RCE_SELF_ISSUED_DOC_TYPES = ('46', '50', '51', '52', '53', '54')
# Tipos con fecha de vencimiento/pago obligatoria en el TXT de importación
RCE_DUE_DATE_DOC_TYPES = ('14', '46', '50', '51', '52', '53', '54')
#: DAM y DSI: la serie es el código de aduana y se informa el año (campo 9).
RCE_CUSTOMS_DOC_TYPES = ('50', '51', '52', '53', '54')


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

    operation_ids = fields.One2many(
        'l10n_pe.sire.operation', 'res_id', string='Operaciones con SUNAT', copy=False,
        domain=[('res_model', '=', 'l10n_pe.sire.rce')])
    invalid_line_ids = fields.One2many(
        'l10n_pe.sire.rce.line', 'sire_id', string='Observaciones', copy=False,
        domain=[('type_line', '=', 'system'), ('check_detail', '!=', False)])

    _period_uniq = models.Constraint(
        'unique (company_id, year, month)',
        'Ya existe un periodo RCE para esta compañía y este mes.')

    def _sire_book_type(self):
        return 'rce'

    def _sire_poll_cron_xmlid(self):
        return 'al_l10n_pe_sire.ir_cron_sire_rce_poll'

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
        return self.env['account.move'].search(
            self._sire_system_domain(('in_invoice', 'in_refund'), 'date') + [
                # Nota 2 del anexo 11: no se anotan los anulados en el RCE.
                ('state', '=', 'posted'),
                ('l10n_latam_document_type_id.code', 'not in', RCE_EXCLUDED_DOC_TYPES),
                # Los no domiciliados van a su propio registro (8.5).
                ('l10n_pe_sire_is_non_domiciled', '=', False),
            ], order='invoice_date, name')

    def _sire_system_line_vals(self, move):
        sign = self._sire_move_sign(move)
        cancelled = move.state == 'cancel'
        amounts = self._sire_amount_split(move)
        serie, folio = self._sire_serie_folio(move)
        doc_code = move.l10n_latam_document_type_id.code or ''
        # El contacto de la factura puede ser una persona de la empresa: el
        # documento y la razón social son los de la entidad comercial.
        partner = move.commercial_partner_id
        issuer_ruc = (self.company_id.root_id.vat if doc_code in RCE_SELF_ISSUED_DOC_TYPES
                      else partner.vat)
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
            'tipo_doc_identidad': self._sire_partner_doc_type(partner),
            'nro_doc_identidad': partner.vat or '',
            'razon_social': partner.name or '',
            # El destino (DG, DGNG, DNG) sale del grupo del impuesto. Nota 3
            # del anexo 11: el ISC de un ítem gravado va en su base; IVAP y
            # exportación, base al campo 21 e impuesto al 24.
            'bi_gravada_dg': amount(amounts['taxed'] + amounts['isc_taxed']),
            'igv_dg': amount(amounts['igv']),
            'bi_gravada_dgng': amount(amounts['taxed_dgng'] + amounts['isc_taxed_dgng']),
            'igv_dgng': amount(amounts['igv_dgng']),
            'bi_gravada_dng': amount(amounts['taxed_dng'] + amounts['isc_taxed_dng']),
            'igv_dng': amount(amounts['igv_dng']),
            'valor_adq_ng': amount(amounts['exonerated'] + amounts['unaffected']
                                   + amounts['ivap_base'] + amounts['export']
                                   + amounts['isc_untaxed']),
            # 22: solo el ISC deducible; el resto ya está en las bases.
            'isc': 0.0,
            'icbper': amount(amounts['icbper']),
            'otros_tributos': amount(amounts['other_taxes'] + amounts['ivap']),
            'total_cp': amount(self._sire_total(move)),
            'moneda': move.currency_id.name,
            'tipo_cambio': 0.0 if cancelled else rate,
            'clasif_bienes': move.l10n_pe_sire_goods_class or '',
            'detraccion': 'Si' if getattr(move, 'l10n_pe_detraction_applies', False) else 'No',
            'estado_cp': '2' if cancelled else '1',
        }
        if doc_code in RCE_CUSTOMS_DOC_TYPES:
            vals.update(self._sire_customs_parts(move))
        if doc_code in ('07', '08'):
            vals.update(self._sire_reversed_doc_vals(move))
            if doc_code == '07':
                vals['tipo_nota'] = move.l10n_pe_edi_refund_reason or ''
        return vals

    def _sire_customs_parts(self, move):
        """Aduana (campo 8), año (9) y número (10) de una DAM o DSI.

        «118-2024-10-012345» es aduana-año-régimen-número: cortar en el
        primer guion daba serie 118 y número 2024, sin año, y SUNAT rechaza
        la fila (el año es obligatorio en los tipos 50-54).
        """
        number = (move.l10n_latam_document_number or move.ref or '').replace(' ', '')
        parts = [part for part in number.split('-') if part]
        if len(parts) >= 3 and len(parts[1]) == 4 and parts[1].isdigit():
            return {'serie_cp': parts[0][:3], 'anio_dam': parts[1],
                    'nro_cp': parts[-1].lstrip('0') or parts[-1]}
        return {}

    # ------------------------------------------------------------------
    # Servicios del manual de Compras v22 (docs/sire/SERVICIOS_RCE.md)
    # ------------------------------------------------------------------

    def _sire_inconsistency_summary_request(self, token, summary_type):
        # 5.36: POST (en el RVIE es GET).
        return self._sire_request(
            'POST', token,
            '/libros/rvierce/resumen/web/resumeninconsistencias/%s' % self._sire_period(),
            params={'codTipoResumen': summary_type, 'codLibro': self._sire_upload_book_code()})

    def _sire_receipt_request(self, token, name):
        # 5.49: desde la v22 la constancia llega como arreglo de bytes.
        return self._sire_get(
            token, '/libros/rvierce/gestionlibro/web/registroslibros/constancia/constanciarecepcion',
            params={'nomConstanciaRecepcion': name})

    def _sire_preliminary_inconsistencies_path(self):
        # 5.42: el último tramo es el formato (Anexo IV: 0 = txt).
        return ('/libros/rvierce/casillas/inconsistenciaslibros/%s/reporteinconsistencia/0'
                % self._sire_period())

    def _sire_delete_proposal_lines(self, lines):
        # 5.15: DELETE con cuerpo.
        self._sire_check_dangerous()
        return self._sire_json_call(
            'delete_proposal', 'DELETE',
            '/libros/rce/propuesta/web/propuestarce/%s' % self._sire_period(),
            self._sire_lines_cp(self._sire_lines_of(lines)),
            detail=_('%s comprobantes.', len(lines)))

    def _sire_delete_preliminary_lines(self, lines):
        # 5.16
        self._sire_check_dangerous()
        return self._sire_json_call(
            'delete_preliminary', 'POST',
            '/libros/rce/preliminar/web/comprobanteslibroscompras/%s/eliminacomprobante'
            % self._sire_period(),
            self._sire_lines_cp(self._sire_lines_of(lines)),
            detail=_('%s comprobantes.', len(lines)))

    def action_sire_delete_registered_preliminary(self, only_non_domiciled=False):
        # 5.17: 1 = todo el preliminar, 2 = solo no domiciliados.
        self.ensure_one()
        self._sire_check_dangerous()
        scope = '2' if only_non_domiciled else '1'
        operation = self._sire_json_call(
            'delete_registered', 'PUT',
            '/libros/rce/preliminar/web/registroslibros/%s/%s/eliminapreliminar'
            % (self._sire_period(), scope),
            detail=_('Solo no domiciliados') if only_non_domiciled else _('Todo el preliminar'))
        if not only_non_domiciled:
            self.preliminary_registered = False
            self._sire_clear_submission()
        return operation

    def _sire_send_fiscal_credit(self, field, value):
        """5.11 reintegro (valorRCF), 5.12 crédito especial (valorCFE) y 5.13
        prorrata (factProrrata). La tabla habla de ``datosFV621``; los
        ejemplos, que son lo que responde «OK», envían ``registros``."""
        endpoint = ('grabacreditofiscalespecial' if field == 'valorCFE'
                    else 'grabacreditofiscal')
        labels = {'valorRCF': _('Reintegro del crédito fiscal'),
                  'valorCFE': _('Crédito fiscal especial'),
                  'factProrrata': _('Coeficiente de prorrata')}
        return self._sire_json_call(
            'fiscal_credit', 'PUT',
            '/libros/rce/propuesta/web/%s/%s' % (self._sire_period(), endpoint),
            {'registros': {field: value}},
            detail='%s: %s' % (labels[field], value))

    # ------------------------------------------------------------------
    # Complementos, nuevos CP y ajustes (docs/sire/ESTRUCTURAS_TXT.md)
    # ------------------------------------------------------------------

    def _sire_new_cp_identifier(self):
        # Tabla 13.2: RUC-CP-AAAAMM-NN, anexo 8 variante «incluir CP».
        return 'CP'

    def _sire_adjustment_row(self, line, car_orig):
        """Anexo 12 (8.4): la estructura del reemplazo con el CAR original en el campo 37."""
        row = self._sire_replacement_row(line)
        row[36] = car_orig
        return row

    def _sire_adjustment_ticket_required(self):
        # 5.18: la carga de ajustes del RCE responde «OK», sin ticket.
        return False

    @staticmethod
    def _sire_empty_row():
        """Fila del anexo 8 con los 37 campos vacíos (los 38-41 no se envían)."""
        return [''] * 37

    def _sire_upload_complement(self, lines):
        """Anexo 8 (A): completa o reubica datos de los CP propuestos con los del sistema.

        Por cada línea de la propuesta se envía su CAR y lo que la nota 5
        permite complementar (campos 15-20, 22, 27, 33-36), tomado de la
        línea del sistema con el mismo CAR.
        """
        self.ensure_one()
        rows = []
        for line in self._sire_lines_of(lines):
            system = self.system_line_ids.filtered(lambda l: l.car_sunat == line.car_sunat)[:1]
            if not system:
                raise UserError(_('El comprobante %s no está en el sistema: no hay datos con '
                                  'qué complementarlo.', '%s-%s' % (line.serie_cp, line.nro_cp)))
            base_proposal = line.bi_gravada_dg + line.bi_gravada_dgng + line.bi_gravada_dng
            base_system = system.bi_gravada_dg + system.bi_gravada_dgng + system.bi_gravada_dng
            if abs(base_proposal - base_system) > 1.0:
                raise UserError(_(
                    'En %(doc)s la base gravada del sistema (%(system).2f) no suma la de la '
                    'propuesta (%(proposal).2f): el complemento solo reubica, no cambia '
                    'importes. Use un ajuste posterior o el reemplazo.',
                    doc='%s-%s' % (line.serie_cp, line.nro_cp),
                    system=base_system, proposal=base_proposal))
            row = self._sire_empty_row()
            row[3] = line.car_sunat
            for index, field in ((14, 'bi_gravada_dg'), (15, 'igv_dg'), (16, 'bi_gravada_dgng'),
                                 (17, 'igv_dgng'), (18, 'bi_gravada_dng'), (19, 'igv_dng'),
                                 (21, 'isc')):
                row[index] = self._sire_fmt_amount(system[field])
            row[26] = self._sire_fmt_rate(system.tipo_cambio, system.moneda)
            row[32] = system.clasif_bienes or ''
            row[33] = system.id_proyecto or ''
            row[34] = system.porc_participacion or ''
            row[35] = system.imb or ''
            rows.append(row)
        name = self._sire_complement_name('RCECOM', self._sire_next_correlative('complement'))
        return self._sire_tus_upload('complement', name, rows, '54', SIRE_UPLOAD_ENDPOINT)

    def _sire_upload_include_exclude(self, lines, include):
        """Anexo 8 (C), tabla 22: 1 excluye un CP propuesto, 2 vuelve a incluirlo."""
        self.ensure_one()
        lines = self._sire_lines_of(lines)
        if not include and any(l.tipo_cp in ('07', '87') for l in lines):
            raise UserError(_('Las notas de crédito (07 y 87) no se pueden excluir de la propuesta.'))
        rows = []
        for line in lines:
            row = self._sire_empty_row()
            row[3] = line.car_sunat
            row[36] = '2' if include else '1'
            rows.append(row)
        name = self._sire_complement_name('RCEINEX', self._sire_next_correlative('include_exclude'))
        return self._sire_tus_upload('include_exclude', name, rows, '55', SIRE_UPLOAD_ENDPOINT)

    def _sire_send_exchange_rates(self, rates):
        """5.10 con el archivo del anexo 10 (RCETCA), en multipart y no por TUS."""
        self.ensure_one()
        self._sire_check_can_submit()
        usd_books = self.company_id.currency_id.name == 'USD'
        rows = [[self._sire_period(), self._sire_fmt_date(date), currency, '%.3f' % rate,
                 '%.3f' % rate if usd_books and currency == 'USD' else '']
                for date, currency, rate in rates]
        name = self._sire_complement_name('RCETCA', self._sire_next_correlative('exchange_rate'))
        content = '\n'.join('|'.join(row) for row in rows).encode('utf-8')
        token = self._sire_get_token(self.company_id)
        response = self._sire_request(
            'POST', token, '/libros/rce/propuesta/web/%s/%s/resumenfechatipocambio'
            % (self._sire_period(), self._sire_upload_book_code()),
            files={'archivo': (name, content, 'text/plain')})
        return self._sire_new_operation(
            'exchange_rate', ticket=self._sire_ticket_from(response), filename=name,
            content=content, detail=_('%s tipos de cambio enviados.', len(rows)))

    def _sire_previous_row(self, move, state='9'):
        """Anexo 13 (5.1): ajuste de un periodo anterior al SIRE (registro de compras PLE)."""
        period = self._sire_move_period_record(move)
        vals = period._sire_system_line_vals(move)
        serie, folio = period._sire_serie_folio(move)
        amount = self._sire_fmt_amount
        detraction_date = getattr(move, 'l10n_pe_detraction_date', False)
        return [
            '%s00' % period._sire_period(),
            self._sire_text(move.name, 40).replace('&', ''),
            'M1',
            self._sire_fmt_date(vals['fecha_emision']),
            self._sire_fmt_date(vals['fecha_vencimiento']) if vals['tipo_cp'] == '14' else '',
            vals['tipo_cp'], serie, '', folio, '',
            vals['tipo_doc_identidad'], vals['nro_doc_identidad'],
            self._sire_text(vals['razon_social'], 100),
            amount(vals['bi_gravada_dg']), amount(vals['igv_dg']),
            amount(vals['bi_gravada_dgng']), amount(vals['igv_dgng']),
            amount(vals['bi_gravada_dng']), amount(vals['igv_dng']),
            amount(vals['valor_adq_ng']), amount(vals['isc']), amount(vals['icbper']),
            amount(vals['otros_tributos']), amount(vals['total_cp']),
            vals['moneda'], self._sire_fmt_rate(vals['tipo_cambio'], vals['moneda']),
            self._sire_fmt_date(vals.get('fecha_emision_mod')),
            vals.get('tipo_cp_mod') or '', vals.get('serie_cp_mod') or '', '',
            vals.get('nro_cp_mod') or '',
            self._sire_fmt_date(detraction_date) if detraction_date else '',
            getattr(move, 'l10n_pe_detraction_number', '') or '',
            '', vals.get('clasif_bienes') or '', '',
            '', '', '', '', '', state,
        ]

    def _sire_upload_previous_adjustment(self, moves, state='9'):
        """5.24: ajustes de periodos anteriores al SIRE, referidos al último generado."""
        self.ensure_one()
        if self.state != 'done' and not self.preliminary_registered:
            raise UserError(_('Envíe los ajustes de periodos anteriores desde el último '
                              'periodo generado en el SIRE.'))
        correlative = self._sire_next_correlative('adjustment_previous')
        operation = self._sire_tus_upload(
            'adjustment_previous', self._sire_le_name('080400', '04', correlative),
            [self._sire_previous_row(move) for move in moves],
            '6', SIRE_UPLOAD_ADJUSTMENT_ENDPOINT)
        operation.adjustment_kind = 'adjustment_previous'
        return operation

    #: Envío de los ajustes cargados (5.19, 5.22, 5.25): ruta y fase por tipo.
    ADJUSTMENT_SEND = {
        'adjustment': ('registrarajustesposterioresrc', '9'),
        'adjustment_nd': ('registrarajustesposterioresrcnd', '10'),
        'adjustment_previous': ('registrarajustesposterioresparc', '9'),
    }

    def _sire_send_adjustment(self, operation):
        """Registra en SUNAT los ajustes posteriores ya cargados.

        5.19 (ajustes del periodo) lleva solo el periodo y el origen del
        envío en la ruta; 5.22 y 5.25 llevan además el número de ajuste
        posterior y el ticket de la carga. El cuerpo es el de los ejemplos
        del manual (la tabla dice «no aplica»).
        """
        self.ensure_one()
        self._sire_check_can_submit()
        kind = operation.adjustment_kind or operation.kind
        path, phase = self.ADJUSTMENT_SEND[kind]
        base = '/libros/rce/ajustesposteriores/web/comprobantesajuspost/%s' % self._sire_period()
        if kind == 'adjustment':
            endpoint = '%s/2/%s' % (base, path)
        else:
            if not operation.ticket:
                raise UserError(_('La carga no devolvió ticket; no se puede enviar.'))
            number = operation.adjustment_number or self._sire_find_adjustment_number(operation)
            if not number:
                raise UserError(_('Indique el número de ajuste posterior que muestra SUNAT '
                                  'en la operación y vuelva a enviar.'))
            operation.adjustment_number = number
            endpoint = '%s/%s/%s/%s/%s' % (base, number, self._sire_upload_book_code(),
                                          operation.ticket, path)
        body = {'controlProcesos': {'lisFases': [{'codFase': phase}]},
                'registrosLibros': {'indEnviadoAjuste': '1'}}
        sent = self._sire_json_call('adjustment_send', 'POST', endpoint, body,
                                    detail=operation.name)
        # sudo: historial de solo lectura para el contable (lo escribe el módulo).
        operation.sudo().adjustment_sent = True
        return sent

    def _sire_find_adjustment_number(self, operation):
        """Número de ajuste posterior de una carga, si SUNAT lo devuelve en 5.59.

        El manual no documenta la respuesta de ``listarcap``: se busca un
        registro con el ticket de la carga y un ``numAjustePosterior``.
        """
        token = self._sire_get_token(self.company_id)
        try:
            response = self._sire_get(
                token, '/libros/rce/ajustesposteriores/web/comprobantesajuspost/%s/listarcap'
                % self._sire_period(), params={'page': '1', 'perPage': '100'})
            data = response.json()
        except (UserError, ValueError):
            return ''

        def walk(node):
            if isinstance(node, dict):
                if node.get('numAjustePosterior') and (
                        not node.get('numTicket') or str(node.get('numTicket')) == operation.ticket):
                    return str(node['numAjustePosterior'])
                return next(filter(None, (walk(v) for v in node.values())), '')
            if isinstance(node, list):
                return next(filter(None, (walk(v) for v in node)), '')
            return ''
        return walk(data)

    def _sire_line_errors(self, line):
        errors = super()._sire_line_errors(line)
        if line.tipo_cp == '01' and line.tipo_doc_identidad != '6':
            errors.append(_('Una factura de compra exige el RUC del proveedor.'))
        if line.tipo_cp in RCE_DUE_DATE_DOC_TYPES and not line.fecha_vencimiento:
            errors.append(_('El tipo %s exige la fecha de vencimiento o pago.', line.tipo_cp))
        if line.tipo_cp in RCE_CUSTOMS_DOC_TYPES and not (
                (line.anio_dam or '').isdigit() and int(line.anio_dam) > 1981):
            errors.append(_(
                'La DAM o DSI (tipo %s) exige el año (campo 9): registre su '
                'número como aduana-año-régimen-número (p. ej. '
                '118-2024-10-012345).', line.tipo_cp))
        if line.estado_cp == '2':
            return errors
        # El IVAP va a los campos 21 y 24 (nota 3 del anexo 11), no a DG.
        if tax_mismatch(line.bi_gravada_dg, line.igv_dg, IGV_RATES) \
                or tax_mismatch(line.bi_gravada_dgng, line.igv_dgng, IGV_RATES) \
                or tax_mismatch(line.bi_gravada_dng, line.igv_dng, IGV_RATES):
            errors.append(_('El IGV/IPM no corresponde a la base gravada (18 % o 10 %).'))
        components = sum((
            line.bi_gravada_dg, line.igv_dg, line.bi_gravada_dgng, line.igv_dgng,
            line.bi_gravada_dng, line.igv_dng, line.valor_adq_ng, line.isc,
            line.icbper, line.otros_tributos))
        if abs(components - line.total_cp) > AMOUNT_TOLERANCE:
            errors.append(_('El total %(total).2f no es la suma de bases e impuestos '
                            '(%(sum).2f).', total=line.total_cp, sum=components))
        return errors

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
            self.company_id.root_id.vat or '',
            self._sire_text(self.company_id.root_id.name), self._sire_period(),
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
            self.company_id.root_id.vat or '',
            self._sire_text(self.company_id.root_id.name),
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
            self._sire_text(line.razon_social),
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

    def action_sire_complement(self):
        lines = self._sire_proposal_lines()
        return lines._sire_period_record()._sire_upload_complement(lines)

    def action_sire_exclude(self):
        lines = self._sire_proposal_lines()
        return lines._sire_period_record()._sire_upload_include_exclude(lines, include=False)

    def action_sire_include(self):
        lines = self._sire_proposal_lines()
        return lines._sire_period_record()._sire_upload_include_exclude(lines, include=True)

