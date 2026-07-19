import base64
import io
import zipfile
from datetime import datetime

from werkzeug.urls import url_encode

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare

MONTH_SELECTION = [
    ('01', 'Enero'), ('02', 'Febrero'), ('03', 'Marzo'), ('04', 'Abril'),
    ('05', 'Mayo'), ('06', 'Junio'), ('07', 'Julio'), ('08', 'Agosto'),
    ('09', 'Setiembre'), ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre'),
]

TICKET_STATES = [
    ('00', 'Fallo'),
    ('01', 'Solicitado'),
    ('02', 'Validando archivo'),
    ('03', 'Procesado con errores'),
    ('04', 'Concluido'),
    ('05', 'En proceso'),
    ('06', 'Terminado'),
]

# Afectaciones IGV (catálogo 07 SUNAT) por columna
AFFECTATION_TAXED = {'10', '17'}
AFFECTATION_EXONERATED = {'20', '21'}
AFFECTATION_UNAFFECTED = {'30', '31', '32', '33', '34', '35', '36', '37'}
AFFECTATION_EXPORT = {'40'}


class L10nPeSireMixin(models.AbstractModel):
    """Flujo común de un periodo SIRE (RVIE o RCE).

    Los modelos concretos definen los One2many ``sire_line_ids`` /
    ``system_line_ids`` / ``diff_line_ids`` y los métodos ``_sire_*``
    específicos del libro (endpoint, parseo y mapeo del sistema).
    """
    _name = 'l10n_pe.sire.mixin'
    _inherit = 'l10n_pe.sire.api'
    _description = 'Periodo SIRE'

    name = fields.Char(string='Nombre', compute='_compute_name', store=True)
    year = fields.Integer(
        string='Año', required=True, tracking=True, copy=False,
        default=lambda self: fields.Date.context_today(self).year)
    month = fields.Selection(
        selection=MONTH_SELECTION, string='Mes', required=True,
        tracking=True, copy=False,
        default=lambda self: '%02d' % fields.Date.context_today(self).month)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    state = fields.Selection(
        string='Estado',
        selection=[
            ('draft', 'Borrador'),
            ('requested', 'Propuesta solicitada'),
            ('downloaded', 'Propuesta descargada'),
            ('sire_loaded', 'SIRE desplegado'),
            ('system_loaded', 'Sistema desplegado'),
            ('compared', 'Comparado'),
            ('done', 'Realizado'),
        ], default='draft', tracking=True, copy=False)
    download_manual = fields.Boolean(
        string='Carga manual', copy=False,
        help='Cargar a mano el TXT exportado desde SUNAT Operaciones en Línea '
             'en lugar de usar la API.')
    ticket_number = fields.Char(string='Ticket de propuesta', copy=False)
    ticket_filename = fields.Char(string='Archivo del reporte', copy=False)
    ticket_state = fields.Selection(
        selection=TICKET_STATES, string='Estado del ticket', copy=False, readonly=True)
    proposal_file = fields.Binary(string='TXT propuesta SIRE', copy=False)
    proposal_filename = fields.Char(copy=False)
    export_file = fields.Binary(string='Archivo generado', copy=False)
    export_filename = fields.Char(copy=False)

    # ------------------------------------------------------------------
    # A definir por cada libro
    # ------------------------------------------------------------------

    def _sire_book_type(self):
        raise NotImplementedError()

    def _sire_book_label(self):
        return dict(rce='RCE', rvie='RVIE')[self._sire_book_type()]

    def _sire_ple_book_code(self):
        """Código de libro del nombre de archivo oficial (080400/140400)."""
        raise NotImplementedError()

    def _sire_proposal_endpoint(self):
        raise NotImplementedError()

    def _sire_min_columns(self):
        raise NotImplementedError()

    def _sire_parse_row(self, cols):
        """Mapea una fila del TXT de la propuesta a valores de línea."""
        raise NotImplementedError()

    def _sire_system_moves(self):
        raise NotImplementedError()

    def _sire_system_line_vals(self, move):
        raise NotImplementedError()

    def _sire_xlsx_headers(self):
        raise NotImplementedError()

    def _sire_xlsx_row(self, line):
        raise NotImplementedError()

    def _sire_replacement_row(self, line):
        """Fila (lista de str) del TXT de reemplazo/importación SUNAT."""
        raise NotImplementedError()

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    @api.depends('year', 'month')
    def _compute_name(self):
        for record in self:
            record.name = '%s-%s-%s' % (record._sire_book_label(), record.month or '', record.year or '')

    def _sire_period(self):
        self.ensure_one()
        return '%04d%s' % (self.year, self.month)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_done(self):
        if any(record.state == 'done' for record in self):
            raise UserError(_('No puede eliminar un periodo en estado Realizado.'))

    @api.model
    def _sire_parse_date(self, value):
        value = (value or '').strip()
        if not value:
            return False
        try:
            return datetime.strptime(value, '%d/%m/%Y').date()
        except ValueError:
            return False

    @api.model
    def _sire_parse_float(self, value):
        try:
            return float((value or '0').strip() or 0)
        except ValueError:
            return 0.0

    @api.model
    def _sire_fmt_date(self, value):
        return value.strftime('%d/%m/%Y') if value else ''

    @api.model
    def _sire_fmt_amount(self, value):
        return '%.2f' % (value or 0.0)

    @api.model
    def _sire_fmt_rate(self, value, currency_name):
        """TC a 5 caracteres (#.###); vacío en soles o sin tipo de cambio."""
        if not value or currency_name in (False, '', 'PEN'):
            return ''
        text = '%.3f' % value
        return '' if text in ('1.000', '0.000') else text

    def _sire_download_export(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/?' + url_encode({
                'model': self._name,
                'id': self.id,
                'filename_field': 'export_filename',
                'field': 'export_file',
                'download': 'true',
            }),
            'target': 'new',
        }

    # ------------------------------------------------------------------
    # Flujo API
    # ------------------------------------------------------------------

    def action_request_proposal(self):
        self.ensure_one()
        if self.download_manual:
            if not self.proposal_file:
                raise UserError(_('Cargue el TXT exportado desde SUNAT antes de confirmar.'))
            self.write({'state': 'downloaded', 'ticket_number': _('Carga manual')})
            return True
        token = self._sire_get_token(self.company_id)
        ticket = self._sire_request_proposal(
            token, self._sire_proposal_endpoint(), self._sire_period())
        self.write({'ticket_number': ticket, 'ticket_state': '01', 'state': 'requested'})
        return True

    def action_check_ticket(self):
        self.ensure_one()
        if not self.ticket_number:
            raise UserError(_('Primero solicite la propuesta.'))
        token = self._sire_get_token(self.company_id)
        code, filename = self._sire_ticket_status(token, self._sire_period(), self.ticket_number)
        self.write({
            'ticket_state': code if code in dict(TICKET_STATES) else '00',
            'ticket_filename': filename or self.ticket_filename,
        })
        return True

    def action_download_proposal(self):
        self.ensure_one()
        if self.ticket_state != '06':
            raise UserError(_('El ticket aún no está terminado (estado %s).', self.ticket_state or '-'))
        token = self._sire_get_token(self.company_id)
        content = self._sire_download_report(
            token, self._sire_period(), self.ticket_number, self.ticket_filename)
        self.write({
            'proposal_file': content,
            'proposal_filename': 'Propuesta_%s_%s.txt' % (
                self._sire_book_type(), self._sire_period()),
            'state': 'downloaded',
        })
        return True

    # ------------------------------------------------------------------
    # Despliegue
    # ------------------------------------------------------------------

    def action_load_sire(self):
        self.ensure_one()
        if not self.proposal_file:
            raise UserError(_('No hay archivo de propuesta SIRE para desplegar.'))
        content = base64.b64decode(self.proposal_file).decode('utf-8').strip('\n')
        commands = [(5, 0, 0)]
        min_cols = self._sire_min_columns()
        for index, row in enumerate(content.split('\n')[1:], start=2):
            row = row.strip('\r')
            if not row.strip():
                continue
            cols = row.split('|')
            if len(cols) < min_cols:
                raise UserError(_(
                    'La línea %(line)s del TXT tiene %(count)s columnas; se esperaban '
                    'al menos %(expected)s.', line=index, count=len(cols), expected=min_cols))
            vals = self._sire_parse_row(cols)
            vals.update(type_line='sire')
            commands.append((0, 0, vals))
        self.sire_line_ids = commands
        self.state = 'sire_loaded'
        return True

    def action_load_system(self):
        self.ensure_one()
        commands = [(5, 0, 0)]
        for move in self._sire_system_moves():
            vals = self._sire_system_line_vals(move)
            vals.update(type_line='system', move_id=move.id)
            commands.append((0, 0, vals))
        self.system_line_ids = commands
        self.state = 'system_loaded'
        return True

    # ------------------------------------------------------------------
    # Datos del sistema: helpers comunes
    # ------------------------------------------------------------------

    def _sire_serie_folio(self, move):
        number = move.l10n_latam_document_number or move.name or ''
        parts = number.split('-')
        serie = parts[0] if parts else ''
        folio = parts[1].lstrip('0') if len(parts) > 1 else ''
        return serie, folio

    def _sire_car_sunat(self, move, issuer_ruc):
        """CAR sintético: RUC(11) + tipo CP(2) + serie(4) + número(10)."""
        serie, folio = self._sire_serie_folio(move)
        ruc = (issuer_ruc or '').strip()
        ruc = ruc[-11:] if len(ruc) > 11 else ruc.zfill(11)
        code = move.l10n_latam_document_type_id.code or ''
        return '%s%s%s%s' % (ruc, code.zfill(2), serie.zfill(4), folio.zfill(10))

    def _sire_move_rate(self, move):
        """Tipo de cambio implícito del asiento (0.0 si está en soles)."""
        if move.currency_id == move.company_id.currency_id or not move.amount_total:
            return 0.0
        return abs(move.amount_total_signed / move.amount_total)

    def _sire_move_sign(self, move):
        return -1 if move.move_type in ('in_refund', 'out_refund') else 1

    def _sire_amount_split(self, move):
        """Bases por afectación IGV e impuestos por grupo, en PEN, positivos.

        Claves: taxed, exonerated, unaffected, export, free, igv, isc,
        icbper, other_taxes.
        """
        result = dict.fromkeys(
            ('taxed', 'exonerated', 'unaffected', 'export', 'free',
             'igv', 'isc', 'icbper', 'other_taxes'), 0.0)
        rate = self._sire_move_rate(move) or 1.0
        for line in move.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
            tax = line.tax_ids[:1]
            base = abs(line.balance) or abs(line.price_subtotal) * rate
            if tax.l10n_pe_edi_tax_code == '9996':
                subtotal = line.price_unit * (1 - (line.discount or 0.0) / 100.0) * line.quantity
                result['free'] += subtotal * rate
                continue
            reason = tax.l10n_pe_edi_affectation_reason
            if reason in AFFECTATION_EXONERATED:
                result['exonerated'] += base
            elif reason in AFFECTATION_UNAFFECTED:
                result['unaffected'] += base
            elif reason in AFFECTATION_EXPORT:
                result['export'] += base
            else:
                result['taxed'] += base
        for line in move.line_ids.filtered('tax_line_id'):
            group = (line.tax_line_id.tax_group_id.name or '').upper()
            amount = abs(line.balance)
            if 'ICBPER' in group or 'ICBPER' in (line.tax_line_id.name or '').upper():
                result['icbper'] += amount
            elif 'ISC' in group:
                result['isc'] += amount
            elif 'IGV' in group or 'IVAP' in group:
                result['igv'] += amount
            else:
                result['other_taxes'] += amount
        return result

    def _sire_reversed_doc_vals(self, move):
        """Datos del comprobante modificado (para notas de crédito/débito)."""
        origin = move.reversed_entry_id
        if not origin and 'debit_origin_id' in move._fields:
            origin = move.debit_origin_id
        if not origin:
            return {}
        serie, folio = self._sire_serie_folio(origin)
        return {
            'fecha_emision_mod': origin.invoice_date,
            'tipo_cp_mod': origin.l10n_latam_document_type_id.code or '',
            'serie_cp_mod': serie,
            'nro_cp_mod': folio,
        }

    # ------------------------------------------------------------------
    # Comparación
    # ------------------------------------------------------------------

    def _sire_compare_fields(self):
        fields_config = self.env['l10n_pe.sire.compare.field'].search([
            ('book_type', '=', self._sire_book_type()),
        ])
        if not fields_config:
            raise UserError(_(
                'No hay campos de comparación configurados para %s.',
                self._sire_book_label()))
        return fields_config

    def _sire_values_equal(self, field, value_sire, value_system):
        if field.type == 'float':
            return float_compare(value_sire or 0.0, value_system or 0.0, precision_digits=2) == 0
        if field.type == 'date':
            return (value_sire or False) == (value_system or False)
        return str(value_sire or '').strip() == str(value_system or '').strip()

    def action_compare(self):
        self.ensure_one()
        fields_config = self._sire_compare_fields()
        all_lines = self.sire_line_ids | self.system_line_ids
        all_lines.write({'compare_state': False, 'diff_detail': False})
        system_by_car = {}
        for line in self.system_line_ids:
            system_by_car.setdefault(line.car_sunat, line)
        for sire_line in self.sire_line_ids:
            system_line = system_by_car.get(sire_line.car_sunat)
            if not system_line:
                sire_line.compare_state = '2'
                continue
            differences = []
            for config in fields_config:
                field = sire_line._fields.get(config.field_name)
                if not field:
                    continue
                value_sire = sire_line[config.field_name]
                value_system = system_line[config.field_name]
                if not self._sire_values_equal(field, value_sire, value_system):
                    differences.append('%s: SIRE=%s / Sistema=%s' % (
                        config.name,
                        self._sire_display_value(field, value_sire),
                        self._sire_display_value(field, value_system)))
            values = {
                'compare_state': '1' if differences else '0',
                'diff_detail': '\n'.join(differences),
            }
            sire_line.write(values)
            system_line.write(values)
        for system_line in self.system_line_ids:
            if not system_line.compare_state:
                system_line.compare_state = '3'
        self.state = 'compared'
        return True

    @api.model
    def _sire_display_value(self, field, value):
        if field.type == 'float':
            return '%.2f' % (value or 0.0)
        if field.type == 'date':
            return self._sire_fmt_date(value)
        return value or ''

    # ------------------------------------------------------------------
    # Exportables
    # ------------------------------------------------------------------

    def action_export_replacement(self):
        """TXT de importación SUNAT (reemplazo de la propuesta) en ZIP."""
        self.ensure_one()
        if not self.system_line_ids:
            raise UserError(_('Primero despliegue las líneas del sistema.'))
        self._sire_check_ruc(self.company_id)
        lines = self.system_line_ids.sorted(key=lambda l: (l.serie_cp or '', l.nro_cp or ''))
        content = '\n'.join('|'.join(self._sire_replacement_row(line)) for line in lines)
        txt_name = 'LE%s%s00%s021112.txt' % (
            self.company_id.vat, self._sire_period(), self._sire_ple_book_code())
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(txt_name, content.encode('utf-8'))
        self.write({
            'export_file': base64.b64encode(buffer.getvalue()),
            'export_filename': txt_name.replace('.txt', '.zip'),
        })
        return self._sire_download_export()

    def action_export_xlsx(self):
        self.ensure_one()
        import xlsxwriter  # noqa: PLC0415 — dependencia opcional declarada en el manifest

        headers = self._sire_xlsx_headers()
        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        style_sire = workbook.add_format({
            'bold': True, 'font_color': '#FFFFFF', 'bg_color': '#1F4E79',
            'align': 'center', 'valign': 'vcenter', 'text_wrap': True, 'border': 1})
        style_system = workbook.add_format({
            'bold': True, 'font_color': '#FFFFFF', 'bg_color': '#8064A2',
            'align': 'center', 'valign': 'vcenter', 'text_wrap': True, 'border': 1})
        cell = workbook.add_format({'valign': 'vcenter'})

        def write_sheet(title, lines, header_style):
            sheet = workbook.add_worksheet(title)
            for col, header in enumerate(headers):
                sheet.write(0, col, header, header_style)
            sheet.autofilter(0, 0, 0, len(headers) - 1)
            sheet.set_row(0, 30)
            sheet.set_column(0, len(headers) - 1, 18)
            ordered = lines.sorted(key=lambda l: (l.serie_cp or '', l.nro_cp or ''))
            for row_index, line in enumerate(ordered, start=1):
                for col_index, value in enumerate(self._sire_xlsx_row(line)):
                    sheet.write(row_index, col_index, value, cell)

        write_sheet('SIRE', self.sire_line_ids, style_sire)
        write_sheet('Sistema', self.system_line_ids, style_system)
        workbook.close()
        self.write({
            'export_file': base64.b64encode(buffer.getvalue()),
            'export_filename': '%s_%s_%s.xlsx' % (self._sire_book_label(), self.month, self.year),
        })
        return self._sire_download_export()

    # ------------------------------------------------------------------
    # Otros
    # ------------------------------------------------------------------

    def action_reset(self):
        self.ensure_one()
        self.sire_line_ids = [(5, 0, 0)]
        self.system_line_ids = [(5, 0, 0)]
        self.write({
            'export_file': False,
            'export_filename': False,
            'state': 'downloaded' if self.proposal_file else 'draft',
        })
        return True

    def action_done(self):
        self.write({'state': 'done'})
        return True


class L10nPeSireLineMixin(models.AbstractModel):
    """Campos comunes de una línea SIRE/Sistema (RVIE y RCE)."""
    _name = 'l10n_pe.sire.line.mixin'
    _description = 'Línea SIRE'
    _order = 'serie_cp, nro_cp, id'

    type_line = fields.Selection(
        selection=[('sire', 'SIRE'), ('system', 'Sistema')],
        string='Origen', required=True, readonly=True)
    compare_state = fields.Selection(
        selection=[
            ('0', 'Correcto'),
            ('1', 'No cuadran'),
            ('2', 'Solo en SIRE'),
            ('3', 'Solo en Sistema'),
        ], string='Comparación', readonly=True, copy=False)
    diff_detail = fields.Text(string='Diferencias', readonly=True, copy=False)
    move_id = fields.Many2one('account.move', string='Comprobante', readonly=True)

    car_sunat = fields.Char(string='CAR SUNAT')
    fecha_emision = fields.Date(string='Fecha de emisión')
    fecha_vencimiento = fields.Date(string='Fecha Vcto/Pago')
    tipo_cp = fields.Char(string='Tipo CP/Doc.')
    serie_cp = fields.Char(string='Serie del CDP')
    nro_cp = fields.Char(string='Nro CP')
    nro_final = fields.Char(string='Nro Final')
    tipo_doc_identidad = fields.Char(string='Tipo Doc Identidad')
    nro_doc_identidad = fields.Char(string='Nro Doc Identidad')
    razon_social = fields.Char(string='Razón social')
    isc = fields.Float(string='ISC', digits=(16, 2))
    icbper = fields.Float(string='ICBPER', digits=(16, 2))
    otros_tributos = fields.Float(string='Otros Trib/Cargos', digits=(16, 2))
    total_cp = fields.Float(string='Total CP', digits=(16, 2))
    moneda = fields.Char(string='Moneda')
    tipo_cambio = fields.Float(string='Tipo de cambio', digits=(12, 3))
    fecha_emision_mod = fields.Date(string='Fecha emisión doc. modificado')
    tipo_cp_mod = fields.Char(string='Tipo CP modificado')
    serie_cp_mod = fields.Char(string='Serie CP modificado')
    nro_cp_mod = fields.Char(string='Nro CP modificado')
    tipo_nota = fields.Char(string='Tipo de nota')
    estado_cp = fields.Selection(
        selection=[('1', 'Aceptado'), ('2', 'Anulado'), ('3', 'Desconocido')],
        string='Estado CP')
    incal = fields.Char(string='Inconsistencias')
