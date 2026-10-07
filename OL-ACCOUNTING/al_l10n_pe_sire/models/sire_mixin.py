import base64
import io
import logging
import zipfile
from datetime import datetime, timedelta

from werkzeug.urls import url_encode

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare

from .sire_validation import (
    CURRENCY_RE, DOC_TYPES_TABLE_10, GENERIC_NUMBER_RE, GENERIC_SERIE_RE,
    STRICT_NUMBER_RE, STRICT_NUMBERING_DOC_TYPES, STRICT_SERIE_RE, ruc_is_valid,
)

_logger = logging.getLogger(__name__)

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

#: Estados del ticket en que SUNAT ya no hará nada más.
TICKET_FINAL_STATES = ('00', '03', '04', '06')
TICKET_FAILED_STATES = ('00', '03')
#: Espera entre consultas automáticas de un ticket, en minutos: SUNAT
#: tarda de segundos a horas según la carga, así que se espera cada vez más.
SIRE_POLL_DELAYS = (2, 4, 8, 16, 32, 60)
#: Consultas antes de rendirse (unas 24 horas).
SIRE_POLL_MAX_ATTEMPTS = 30

# Afectaciones IGV (catálogo 07 SUNAT) por columna
AFFECTATION_TAXED = {'10'}
AFFECTATION_IVAP = {'17'}
AFFECTATION_EXONERATED = {'20'}
AFFECTATION_UNAFFECTED = {'30'}
AFFECTATION_EXPORT = {'40'}
#: Transferencias gratuitas (catálogo 07): gravadas 11-16, exonerada 21 e
#: inafectas 31-37. Van a «valor de las operaciones gratuitas», no a la base
#: exonerada o inafecta.
AFFECTATION_FREE = {'11', '12', '13', '14', '15', '16', '21',
                    '31', '32', '33', '34', '35', '36', '37'}

# Códigos de tributo SUNAT (catálogo 05, ``l10n_pe_edi_tax_code``). Clasificar
# por código y no por el nombre del grupo, que es traducible.
TAX_CODE_IGV = '1000'
TAX_CODE_IVAP = '1016'
TAX_CODE_ISC = '2000'
TAX_CODE_ICBPER = '7152'
TAX_CODE_FREE = '9996'
TAX_CODE_OTHER = '9999'
#: Tributos que se suman a la base de otro impuesto, no la determinan.
TAX_CODES_SURCHARGE = (TAX_CODE_ISC, TAX_CODE_ICBPER, TAX_CODE_OTHER)
#: Grupos de impuestos del plan peruano (``account.{compañía}_tax_group_*``)
#: que indican el destino de una compra gravada en el RCE: el IGV de
#: ``igv_g_ng`` va a DGNG y el de ``igv_ng`` a DNG; el resto, a DG.
TAX_GROUP_DESTINATIONS = {'igv_g_ng': 'dgng', 'igv_ng': 'dng'}


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
            ('submitted', 'Enviado a SUNAT'),
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

    # --- Envío a SUNAT: se acepta la propuesta o se reemplaza; nunca las
    # dos cosas, y de ahí que compartan ticket y estado. ---
    submission_type = fields.Selection(
        selection=[('accept', 'Propuesta aceptada'), ('replace', 'Propuesta reemplazada')],
        string='Envío', copy=False, readonly=True)
    submission_ticket = fields.Char(string='Ticket del envío', copy=False, readonly=True)
    submission_state = fields.Selection(
        selection=TICKET_STATES, string='Estado del envío', copy=False, readonly=True)
    # --- Consulta automática de tickets (cron con espera creciente) ---
    poll_next_date = fields.Datetime(
        string='Próxima consulta automática', copy=False, readonly=True, index=True)
    poll_attempts = fields.Integer(
        string='Consultas automáticas', copy=False, readonly=True)
    preliminary_registered = fields.Boolean(
        string='Preliminar registrado', copy=False, readonly=True,
        help='El preliminar quedó registrado en SUNAT; la generación del '
             'registro se completa en el portal.')

    # --- Resumen de la comparación: es lo primero que se mira al abrir un
    # periodo, y contarlo a ojo en una lista de miles de líneas no es una
    # opción. ---
    count_sire = fields.Integer(
        string='Comprobantes en la propuesta', compute='_compute_compare_counts')
    count_system = fields.Integer(
        string='Comprobantes en el sistema', compute='_compute_compare_counts')
    count_ok = fields.Integer(
        string='Correctas', compute='_compute_compare_counts')
    count_diff = fields.Integer(
        string='No cuadran', compute='_compute_compare_counts')
    count_only_sire = fields.Integer(
        string='Solo en SIRE', compute='_compute_compare_counts')
    count_only_system = fields.Integer(
        string='Solo en el sistema', compute='_compute_compare_counts')
    count_invalid = fields.Integer(
        string='Con observaciones', compute='_compute_compare_counts',
        help='Líneas del sistema que no pasan las validaciones de SUNAT.')

    @api.depends('sire_line_ids.compare_state', 'system_line_ids.compare_state',
                 'system_line_ids.check_detail')
    def _compute_compare_counts(self):
        for record in self:
            sire_lines = record.sire_line_ids
            system_lines = record.system_line_ids
            record.count_sire = len(sire_lines)
            record.count_system = len(system_lines)
            record.count_ok = len(sire_lines.filtered(lambda l: l.compare_state == '0'))
            record.count_diff = len(sire_lines.filtered(lambda l: l.compare_state == '1'))
            record.count_only_sire = len(sire_lines.filtered(lambda l: l.compare_state == '2'))
            record.count_only_system = len(
                system_lines.filtered(lambda l: l.compare_state == '3'))
            record.count_invalid = len(system_lines.filtered('check_detail'))

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

    def _sire_upload_book_code(self):
        """Código de libro de la carga masiva (080000 RCE / 140000 RVIE)."""
        raise NotImplementedError()

    def _sire_replacement_process_code(self):
        """Indicador de carga masiva del reemplazo (Anexo I del manual)."""
        raise NotImplementedError()

    def _sire_accept_endpoint(self):
        """Servicio de aceptación de la propuesta."""
        raise NotImplementedError()

    def _sire_preliminary_endpoint(self):
        """Servicio de registro del preliminar."""
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

    @api.constrains('year', 'month', 'company_id')
    def _check_unique_period(self):
        """Un periodo por libro y compañía.

        Dos registros del mismo mes acaban con dos comparaciones que no
        coinciden y nadie sabe cuál se declaró.
        """
        for record in self:
            duplicate = self.search([
                ('id', '!=', record.id),
                ('year', '=', record.year),
                ('month', '=', record.month),
                ('company_id', '=', record.company_id.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'Ya existe un periodo %(name)s para %(company)s.',
                    name=record.name, company=record.company_id.display_name))

    @api.constrains('year')
    def _check_year(self):
        for record in self:
            if not 2000 <= record.year <= 2099:
                raise ValidationError(_(
                    'El año %s no es un periodo tributario válido (AAAAMM).', record.year))

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

    def _sire_check_can_submit(self):
        """Solo quien puede modificar el periodo puede hablar con SUNAT.

        La llamada a la API se hace antes de escribir en el registro: sin
        esta comprobación, un usuario de solo lectura aceptaría la propuesta
        en SUNAT y solo después fallaría la escritura en Odoo.
        """
        self.check_access('write')

    def action_request_proposal(self):
        self.ensure_one()
        self._sire_check_can_submit()
        if self.download_manual:
            if not self.proposal_file:
                raise UserError(_('Cargue el TXT exportado desde SUNAT antes de confirmar.'))
            self.write({'state': 'downloaded', 'ticket_number': _('Carga manual')})
            return True
        token = self._sire_get_token(self.company_id)
        ticket = self._sire_request_proposal(
            token, self._sire_proposal_endpoint(), self._sire_period())
        self.write({'ticket_number': ticket, 'ticket_state': '01', 'state': 'requested'})
        self._sire_schedule_poll()
        return True

    def action_check_ticket(self):
        self.ensure_one()
        self._sire_check_can_submit()
        if not self.ticket_number:
            raise UserError(_('Primero solicite la propuesta.'))
        token = self._sire_get_token(self.company_id)
        code, filename = self._sire_ticket_status(token, self._sire_period(), self.ticket_number)
        self.write({
            'ticket_state': code,
            'ticket_filename': filename or self.ticket_filename,
        })
        return True

    def action_download_proposal(self):
        self.ensure_one()
        self._sire_check_can_submit()
        if self.ticket_state != '06':
            raise UserError(_('El ticket aún no está terminado (estado %s).', self.ticket_state or '-'))
        token = self._sire_get_token(self.company_id)
        content = self._sire_download_report(
            token, self._sire_period(), self.ticket_number,
            self._sire_upload_book_code())
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
        # El TXT exportado a mano desde SOL puede venir en latin-1.
        content = self._sire_decode(base64.b64decode(self.proposal_file)).strip('\n')
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
        self._sire_validate_system_lines()
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
        """Tipo de cambio del comprobante (0.0 si está en soles).

        El de la factura (``invoice_currency_rate``, a la fecha de emisión) y,
        en las notas, el del documento que modifican (nota 4 del anexo 11,
        nota 3 del anexo 2). Antes se dividía el total en soles entre el
        total en moneda extranjera: fallaba en notas y en gratuitas (total 0).
        """
        origin = move.reversed_entry_id or (
            move.debit_origin_id if 'debit_origin_id' in move._fields else False)
        if origin and origin.currency_id == move.currency_id:
            return self._sire_move_rate(origin)
        if move.currency_id == move.company_id.currency_id:
            return 0.0
        if move.invoice_currency_rate:
            return 1.0 / move.invoice_currency_rate
        if not move.amount_total:
            return 0.0
        return abs(move.amount_total_signed / move.amount_total)

    def _sire_withheld(self, move):
        """Retención del IGV (3 %) del comprobante, en soles: Odoo la resta
        de ``amount_total``, pero el total del CP es el íntegro."""
        group = self.env.ref(
            'account.%s_tax_group_igv_withholding' % move.company_id.root_id.id,
            raise_if_not_found=False)
        return abs(sum(line.balance for line in move.line_ids
                       if group and line.tax_line_id.tax_group_id == group))

    def _sire_total(self, move):
        return abs(move.amount_total_signed) + self._sire_withheld(move)

    def _sire_partner_doc_type(self, partner):
        """Tipo de documento (tabla 2) del contacto. El tipo «VAT» genérico
        de LATAM tiene código 0: con 11 u 8 dígitos se infiere RUC o DNI."""
        code = partner.l10n_latam_identification_type_id.l10n_pe_vat_code or ''
        vat = (partner.vat or '').strip()
        if code in ('', '0') and vat.isdigit():
            if len(vat) == 11:
                return '6'
            if len(vat) == 8:
                return '1'
        return code

    def _sire_system_domain(self, move_types, date_field):
        """Dominio común de los comprobantes del sistema del periodo.

        Los anulados se informan (estado 2) solo si llegaron a emitirse: un
        borrador cancelado nunca se publicó y no existe para SUNAT. Se
        excluyen, como en el PLE, los diarios marcados como ajenos a los
        libros electrónicos.
        """
        date_from = fields.Date.to_date('%04d-%s-01' % (self.year, self.month))
        date_to = fields.Date.end_of(date_from, 'month')
        return [
            # la compañía y sus sucursales: el registro es del RUC
            ('company_id', 'child_of', self.company_id.root_id.id),
            ('move_type', 'in', move_types),
            '|', ('state', '=', 'posted'),
            '&', ('state', '=', 'cancel'), ('posted_before', '=', True),
            (date_field, '>=', date_from),
            (date_field, '<=', date_to),
            ('journal_id.l10n_pe_exclude_from_books', '=', False),
            # Sin tipo de documento no es un comprobante (p. ej. diarios que no
            # usan documentos LATAM): antes entraba con el tipo vacío.
            ('l10n_latam_document_type_id', '!=', False),
        ]

    def _sire_move_sign(self, move):
        return -1 if move.move_type in ('in_refund', 'out_refund') else 1

    def _sire_amount_split(self, move):
        """Bases por afectación IGV e impuestos por grupo, en PEN, positivos.

        Claves: taxed, exonerated, unaffected, export, free, igv, isc,
        icbper, other_taxes.
        """
        result = dict.fromkeys(
            ('taxed', 'taxed_dgng', 'taxed_dng', 'exonerated', 'unaffected',
             'export', 'free', 'ivap_base', 'igv', 'igv_dgng', 'igv_dng', 'ivap',
             'isc', 'icbper', 'other_taxes', 'isc_taxed', 'isc_taxed_dgng',
             'isc_taxed_dng', 'isc_untaxed'), 0.0)
        rate = self._sire_move_rate(move) or 1.0
        destinations = self._sire_tax_group_destinations(move.company_id)
        # Con signo: una línea negativa (deducción de un anticipo, descuento)
        # resta de su columna en vez de sumarse.
        direction = move.direction_sign
        for line in move.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
            # El impuesto que define la afectación es el principal (IGV,
            # IVAP, exonerado…), no un recargo como el ICBPER o el ISC.
            tax = line.tax_ids.filtered(
                lambda t: t.l10n_pe_edi_tax_code not in TAX_CODES_SURCHARGE)[:1] \
                or line.tax_ids[:1]
            base = (line.balance * direction) if line.balance else line.price_subtotal * rate
            # La afectación de la línea manda (l10n_pe_edi la deja editar);
            # la del impuesto es solo su valor por defecto.
            reason = line.l10n_pe_edi_affectation_reason \
                or tax.l10n_pe_edi_affectation_reason
            if tax.l10n_pe_edi_tax_code == TAX_CODE_FREE or reason in AFFECTATION_FREE:
                subtotal = line.price_unit * (1 - (line.discount or 0.0) / 100.0) * line.quantity
                result['free'] += subtotal * rate
                continue
            if not tax:
                # Sin impuesto no hay base gravada: va a inafecto (RVIE) o a
                # adquisición no gravada (RCE), no a una base sin IGV.
                result['unaffected'] += base
                continue
            if tax.l10n_pe_edi_tax_code == TAX_CODE_IVAP or reason in AFFECTATION_IVAP:
                result['ivap_base'] += base
            elif reason in AFFECTATION_EXONERATED:
                result['exonerated'] += base
            elif reason in AFFECTATION_UNAFFECTED:
                result['unaffected'] += base
            elif reason in AFFECTATION_EXPORT:
                result['export'] += base
            else:
                suffix = destinations.get(tax.tax_group_id.id)
                result['taxed_%s' % suffix if suffix else 'taxed'] += base
        keys = {
            TAX_CODE_IGV: 'igv',
            TAX_CODE_IVAP: 'ivap',
            TAX_CODE_ISC: 'isc',
            TAX_CODE_ICBPER: 'icbper',
        }
        root = move.company_id.root_id
        skipped_groups = self.env['account.tax.group']
        for key_group in ('free_invoice', 'gra', 'igv_withholding'):
            skipped_groups |= self.env.ref(
                'account.%s_tax_group_%s' % (root.id, key_group),
                raise_if_not_found=False) or self.env['account.tax.group']
        for line in move.line_ids.filtered('tax_line_id'):
            tax = line.tax_line_id
            # Gratuitas (grupo «free»: IGV + resta de la base) y retención
            # del 3 %: no son tributos del comprobante. Antes caían en «otros
            # tributos» con −100 % del valor o −3 % del total.
            if tax.tax_group_id in skipped_groups \
                    or tax.l10n_pe_edi_tax_code == TAX_CODE_FREE:
                continue
            key = keys.get(tax.l10n_pe_edi_tax_code, 'other_taxes')
            suffix = destinations.get(tax.tax_group_id.id)
            if key == 'igv' and suffix:
                key = 'igv_%s' % suffix
            if key == 'isc':
                # RCE (nota 3 del anexo 11): el ISC de un ítem gravado va en
                # la base de su IGV; el de uno no gravado, al campo 21.
                igv_taxes = line.tax_ids.filtered(
                    lambda t: t.l10n_pe_edi_tax_code == TAX_CODE_IGV)
                if igv_taxes:
                    target = destinations.get(igv_taxes[:1].tax_group_id.id)
                    result['isc_taxed_%s' % target if target else 'isc_taxed'] += \
                        line.balance * direction
                else:
                    result['isc_untaxed'] += line.balance * direction
            result[key] += line.balance * direction
        return result

    @api.model
    def _sire_tax_group_destinations(self, company):
        """``{id del grupo de impuestos: 'dgng' | 'dng'}`` de la compañía."""
        destinations = {}
        # Los grupos del plan viven en la compañía raíz (no en la sucursal).
        for key, suffix in TAX_GROUP_DESTINATIONS.items():
            group = self.env.ref(
                'account.%s_tax_group_%s' % (company.root_id.id, key),
                raise_if_not_found=False)
            if group:
                destinations[group.id] = suffix
        return destinations

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
        """Cruza propuesta y sistema por CAR y marca cada línea.

        Las escrituras van agrupadas por resultado: un periodo con varios
        miles de comprobantes hacía dos ``write`` por línea, y eso son
        decenas de miles de consultas para una comparación que en memoria
        es inmediata.
        """
        self.ensure_one()
        fields_config = self._sire_compare_fields()
        all_lines = self.sire_line_ids | self.system_line_ids
        all_lines.write({'compare_state': False, 'diff_detail': False})

        system_by_car = {}
        duplicated = self.env[self.system_line_ids._name]
        for line in self.system_line_ids:
            if line.car_sunat in system_by_car:
                # Dos comprobantes del sistema con el mismo CAR: el
                # segundo no tiene con qué cruzarse y hay que verlo, no
                # descartarlo en silencio.
                duplicated |= line
                continue
            system_by_car[line.car_sunat] = line

        only_sire = self.env[self.sire_line_ids._name]
        matched_ok = self.env[self.sire_line_ids._name]
        by_diff = {}
        for sire_line in self.sire_line_ids:
            system_line = system_by_car.get(sire_line.car_sunat)
            if not system_line:
                only_sire |= sire_line
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
            if differences:
                by_diff.setdefault('\n'.join(differences), []).extend(
                    (sire_line.id, system_line.id))
            else:
                matched_ok |= sire_line | system_line

        if matched_ok:
            matched_ok.write({'compare_state': '0', 'diff_detail': False})
        if only_sire:
            only_sire.write({'compare_state': '2'})
        for detail, ids in by_diff.items():
            self.env[self.sire_line_ids._name].browse(ids).write({
                'compare_state': '1', 'diff_detail': detail})

        pending = self.system_line_ids.filtered(lambda l: not l.compare_state)
        if pending:
            pending.write({'compare_state': '3'})
        if duplicated:
            duplicated.write({
                'diff_detail': _('CAR SUNAT repetido en el sistema: solo la '
                                 'primera línea se cruzó con la propuesta.')})
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

    def _sire_replacement_zip(self):
        """(nombre del TXT, ZIP en bytes) del reemplazo de la propuesta.

        Lo comparten la descarga manual y el envío por API: el archivo que
        se sube tiene que ser exactamente el que el usuario puede revisar.
        """
        self.ensure_one()
        if not self.system_line_ids:
            raise UserError(_('Primero despliegue las líneas del sistema.'))
        ruc = self._sire_check_ruc(self.company_id.root_id)
        lines = self.system_line_ids.sorted(key=lambda l: (l.serie_cp or '', l.nro_cp or ''))
        content = '\n'.join('|'.join(self._sire_replacement_row(line)) for line in lines)
        # Indicador de moneda (M): 2 si la contabilidad se lleva en dólares.
        currency_flag = '2' if self.company_id.root_id.currency_id.name == 'USD' else '1'
        txt_name = 'LE%s%s00%s0211%s2.txt' % (
            ruc, self._sire_period(), self._sire_ple_book_code(), currency_flag)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(txt_name, content.encode('utf-8'))
        return txt_name, buffer.getvalue()

    def _sire_check_replacement_lines(self):
        """El reemplazo no sale con líneas que SUNAT rechazaría, ni por la
        API ni descargado para subirlo a mano."""
        invalid = self._sire_validate_system_lines()
        if invalid:
            details = '\n'.join(
                '• %s-%s: %s' % (line.serie_cp or '?', line.nro_cp or '?',
                                 line.check_detail.replace('\n', '; '))
                for line in invalid[:10])
            raise UserError(_(
                'Hay %(count)s líneas con observaciones; SUNAT rechazaría el '
                'reemplazo. Corríjalas en los comprobantes y vuelva a desplegar '
                'el sistema (pestaña «Observaciones»):\n%(details)s',
                count=len(invalid), details=details))

    def action_export_replacement(self):
        """TXT de importación SUNAT (reemplazo de la propuesta) en ZIP."""
        self.ensure_one()
        self._sire_check_replacement_lines()
        txt_name, payload = self._sire_replacement_zip()
        self.write({
            'export_file': base64.b64encode(payload),
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
    # Envío a SUNAT: aceptar o reemplazar, y registrar el preliminar
    # ------------------------------------------------------------------

    def _sire_check_submittable(self):
        self.ensure_one()
        if self.state not in ('compared', 'submitted'):
            raise UserError(_(
                'Compare la propuesta con el sistema antes de enviar nada a '
                'SUNAT: el envío decide qué queda registrado en el periodo.'))
        # Tras un envío fallido (procesado con errores) se puede corregir y
        # volver a enviar: antes el periodo quedaba bloqueado para siempre.
        if self.submission_ticket \
                and self.submission_state not in TICKET_FAILED_STATES:
            raise UserError(_(
                'Este periodo ya tiene un envío en curso (ticket %s). '
                'Consulte su estado antes de enviar otro.', self.submission_ticket))

    def action_accept_proposal(self):
        """Acepta la propuesta de SUNAT tal cual la entregó.

        Solo tiene sentido cuando la comparación no encontró diferencias;
        si las hay, aceptar equivale a dar por bueno lo que el sistema
        dice que está mal, así que se avisa.
        """
        self.ensure_one()
        self._sire_check_can_submit()
        self._sire_check_submittable()
        if self.count_diff or self.count_only_sire or self.count_only_system:
            raise UserError(_(
                'La comparación encontró diferencias (%(diff)s no cuadran, '
                '%(sire)s solo en SIRE, %(system)s solo en el sistema). '
                'Corríjalas o envíe un reemplazo en vez de aceptar la '
                'propuesta.',
                diff=self.count_diff, sire=self.count_only_sire,
                system=self.count_only_system))
        token = self._sire_get_token(self.company_id)
        ticket = self._sire_accept_proposal(token, self._sire_accept_endpoint())
        self.write({
            'submission_type': 'accept',
            'submission_ticket': ticket,
            'submission_state': '01',
            'state': 'submitted',
        })
        self._sire_schedule_poll()
        self._sire_log(_('Propuesta aceptada. Ticket %s.', ticket))
        return True

    def action_send_replacement(self):
        """Sube el TXT de reemplazo por la API en vez de a mano en SOL."""
        self.ensure_one()
        self._sire_check_can_submit()
        self._sire_check_submittable()
        self._sire_check_replacement_lines()
        txt_name, payload = self._sire_replacement_zip()
        zip_name = txt_name.replace('.txt', '.zip')
        token = self._sire_get_token(self.company_id)
        ticket = self._sire_upload(token, zip_name, payload, {
            'filename': zip_name,
            'filetype': 'application/zip',
            'numRuc': self._sire_check_ruc(self.company_id.root_id),
            'perTributario': self._sire_period(),
            'codOrigenEnvio': '2',                      # servicio web
            'codProceso': self._sire_replacement_process_code(),
            'codTipoCorrelativo': '01',                 # envíos masivos
            'nomArchivoImportacion': zip_name,
            'codLibro': self._sire_upload_book_code(),
        })
        self.write({
            'export_file': base64.b64encode(payload),
            'export_filename': zip_name,
            'submission_type': 'replace',
            'submission_ticket': ticket,
            'submission_state': '01',
            'state': 'submitted',
        })
        self._sire_schedule_poll()
        self._sire_log(_('Reemplazo enviado (%(file)s). Ticket %(ticket)s.',
                         file=zip_name, ticket=ticket))
        return True

    def action_check_submission(self):
        """Estado del ticket del envío (aceptación o reemplazo)."""
        self.ensure_one()
        self._sire_check_can_submit()
        if not self.submission_ticket:
            raise UserError(_('Este periodo no tiene ningún envío.'))
        token = self._sire_get_token(self.company_id)
        register = self._sire_ticket_register(
            token, self._sire_period(), self.submission_ticket)
        self.submission_state = self._sire_ticket_code(register)
        if self.submission_state in TICKET_FINAL_STATES:
            # Las inconsistencias que SUNAT encontró en el envío quedan
            # adjuntas al periodo: sin ellas, «procesado con errores» no
            # dice qué corregir.
            self._sire_attach_reports(token, register)
        return True

    def action_register_preliminary(self):
        """Registra el preliminar del periodo en SUNAT.

        Es el último paso que admite la API: la generación del registro
        se completa en el portal, y SUNAT no expone un servicio para
        hacerla desde fuera.
        """
        self.ensure_one()
        self._sire_check_can_submit()
        if not self.submission_ticket:
            raise UserError(_(
                'Acepte la propuesta o envíe el reemplazo antes de registrar '
                'el preliminar.'))
        if self.submission_state not in ('04', '06'):
            raise UserError(_(
                'El envío %(ticket)s aún no terminó bien en SUNAT (estado '
                '%(state)s): registre el preliminar cuando esté concluido.',
                ticket=self.submission_ticket,
                state=dict(TICKET_STATES).get(self.submission_state,
                                              self.submission_state or '-')))
        token = self._sire_get_token(self.company_id)
        self._sire_register_preliminary(token, self._sire_preliminary_endpoint())
        self.write({'preliminary_registered': True, 'state': 'done'})
        self._sire_log(_('Preliminar registrado en SUNAT.'))
        return True

    def _sire_log(self, body):
        """Deja constancia en el hilo del registro (RVIE y RCE son mail.thread)."""
        self.ensure_one()
        self.message_post(body=body)

    # ------------------------------------------------------------------
    # Validación de las líneas del sistema
    # ------------------------------------------------------------------

    def action_validate(self):
        """Revisa las líneas del sistema y avisa del resultado."""
        self.ensure_one()
        invalid = self._sire_validate_system_lines()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'warning' if invalid else 'success',
                'message': _('%s líneas con observaciones; revise la pestaña '
                             '«Observaciones».', len(invalid)) if invalid
                else _('Todas las líneas del sistema pasan las validaciones.'),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def _sire_validate_system_lines(self):
        """Escribe ``check_detail`` en cada línea del sistema; devuelve las que fallan.

        Agrupado por texto, como la comparación: una escritura por cada
        combinación de errores y no una por línea.
        """
        self.ensure_one()
        by_detail = {}
        for line in self.system_line_ids:
            detail = '\n'.join(self._sire_line_errors(line)) or False
            by_detail.setdefault(detail, []).append(line.id)
        Line = self.env[self.system_line_ids._name]
        for detail, ids in by_detail.items():
            Line.browse(ids).write({'check_detail': detail})
        return self.system_line_ids.filtered('check_detail')

    def _sire_period_bounds(self):
        date_from = fields.Date.to_date('%04d-%s-01' % (self.year, self.month))
        return date_from, fields.Date.end_of(date_from, 'month')

    def _sire_line_errors(self, line):
        """Reglas comunes a RVIE y RCE; cada libro añade las suyas."""
        errors = []
        doc = line.tipo_cp or ''
        if doc not in DOC_TYPES_TABLE_10:
            errors.append(_('Tipo de comprobante «%s» fuera de la tabla 10.', doc))
        if doc in STRICT_NUMBERING_DOC_TYPES:
            if not STRICT_SERIE_RE.match(line.serie_cp or ''):
                errors.append(_('La serie «%s» debe tener 4 caracteres alfanuméricos.',
                                line.serie_cp or ''))
            if not STRICT_NUMBER_RE.match(line.nro_cp or ''):
                errors.append(_('El número «%s» debe tener de 1 a 8 dígitos.',
                                line.nro_cp or ''))
        else:
            if line.serie_cp and not GENERIC_SERIE_RE.match(line.serie_cp):
                errors.append(_('La serie «%s» no es válida.', line.serie_cp))
            if not GENERIC_NUMBER_RE.match(line.nro_cp or ''):
                errors.append(_('El número «%s» debe ser numérico.', line.nro_cp or ''))
        date_from, date_to = self._sire_period_bounds()
        if not line.fecha_emision:
            errors.append(_('Falta la fecha de emisión.'))
        elif line.fecha_emision > date_to:
            errors.append(_('La fecha de emisión es posterior al periodo.'))
        id_type, id_number = line.tipo_doc_identidad or '', line.nro_doc_identidad or ''
        if id_number and not id_type:
            errors.append(_('Falta el tipo de documento de identidad.'))
        elif id_type == '6' and not ruc_is_valid(id_number):
            errors.append(_('El RUC %s no es válido (dígito verificador).', id_number or '—'))
        elif id_type == '1' and not (len(id_number) == 8 and id_number.isdigit()):
            errors.append(_('El DNI %s debe tener 8 dígitos.', id_number or '—'))
        if not CURRENCY_RE.match(line.moneda or ''):
            errors.append(_('Moneda «%s» no es un código ISO 4217.', line.moneda or ''))
        elif line.moneda != 'PEN' and line.estado_cp != '2' and not line.tipo_cambio:
            errors.append(_('Falta el tipo de cambio para %s.', line.moneda))
        if doc in ('07', '08', '87', '88') and line.estado_cp != '2' and not (
                line.tipo_cp_mod and line.serie_cp_mod and line.nro_cp_mod
                and line.fecha_emision_mod):
            errors.append(_('La nota no indica el comprobante que modifica.'))
        return errors

    # ------------------------------------------------------------------
    # Consulta automática de tickets
    # ------------------------------------------------------------------

    def _sire_poll_cron_xmlid(self):
        raise NotImplementedError()

    def _sire_schedule_poll(self, attempt=0):
        """Programa la próxima consulta automática del ticket pendiente."""
        delay = SIRE_POLL_DELAYS[min(attempt, len(SIRE_POLL_DELAYS) - 1)]
        next_date = fields.Datetime.now() + timedelta(minutes=delay)
        self.write({'poll_next_date': next_date, 'poll_attempts': attempt})
        cron = self.env.ref(self._sire_poll_cron_xmlid(), raise_if_not_found=False)
        if cron:
            # sudo: el contable no puede leer ir.cron, pero sí programar la
            # consulta de su propio ticket.
            cron_sudo = cron.sudo()
            cron_sudo._trigger(at=next_date)

    def _sire_stop_poll(self):
        self.write({'poll_next_date': False, 'poll_attempts': 0})

    def _sire_warn(self, message):
        """Deja el aviso en el hilo y una actividad para quien creó el periodo."""
        self._sire_log(message)
        self.activity_schedule(
            'mail.mail_activity_data_warning', summary=_('SIRE: revisar ticket'),
            note=message, user_id=(self.create_uid.active and self.create_uid.id) or self.env.uid)

    def _sire_poll_once(self):
        """Una consulta del ticket pendiente: termina, sigue esperando o falla."""
        self.ensure_one()
        if self.state == 'requested' and self.ticket_number and not self.download_manual:
            self.action_check_ticket()
            code = self.ticket_state
            if code == '06':
                self.action_download_proposal()
                self._sire_stop_poll()
                self._sire_log(_('Propuesta descargada automáticamente (ticket %s).',
                                 self.ticket_number))
                return
            # La exportación de la propuesta termina en 06; un 04 intermedio
            # no es el final (antes se dejaba de consultar sin descargarla).
            if code in TICKET_FAILED_STATES:
                self._sire_stop_poll()
                self._sire_warn(_('SUNAT terminó el ticket de la propuesta %(ticket)s '
                                  'sin entregarla (estado %(state)s).',
                                  ticket=self.ticket_number,
                                  state=dict(TICKET_STATES).get(code, code)))
                return
        elif self.submission_ticket and self.submission_state not in TICKET_FINAL_STATES:
            self.action_check_submission()
            code = self.submission_state
            if code in TICKET_FAILED_STATES:
                self._sire_stop_poll()
                self._sire_warn(_('SUNAT rechazó el envío %(ticket)s (estado %(state)s). '
                                  'Revise el detalle en SUNAT Operaciones en Línea.',
                                  ticket=self.submission_ticket,
                                  state=dict(TICKET_STATES).get(code, code)))
                return
            if code in TICKET_FINAL_STATES:
                self._sire_stop_poll()
                self._sire_log(_('SUNAT procesó el envío %s.', self.submission_ticket))
                return
        else:
            self._sire_stop_poll()
            return
        self._sire_poll_retry()

    def _sire_poll_retry(self, error=None):
        attempt = self.poll_attempts + 1
        if attempt >= SIRE_POLL_MAX_ATTEMPTS:
            self._sire_stop_poll()
            self._sire_warn(_('Se dejó de consultar el ticket tras %(count)s intentos%(error)s. '
                              'Consúltelo a mano.', count=attempt,
                              error=(': %s' % error) if error else ''))
            return
        self._sire_schedule_poll(attempt)

    @api.model
    def _cron_sire_poll_tickets(self):
        """Consulta los tickets cuya próxima consulta ya venció."""
        records = self.search([('poll_next_date', '<=', fields.Datetime.now())],
                              order='poll_next_date')
        cron = self.env['ir.cron']
        cron._commit_progress(remaining=len(records))
        for record in records:
            try:
                with self.env.cr.savepoint():
                    record._sire_poll_once()
            except Exception as error:  # noqa: BLE001 — un periodo no tumba el cron
                _logger.warning('SIRE %s: consulta del ticket fallida: %s', record.name, error)
                try:
                    with self.env.cr.savepoint():
                        record._sire_poll_retry(error=error)
                except Exception:  # noqa: BLE001
                    _logger.exception('SIRE %s: no se pudo reprogramar la consulta', record.name)
                    record._sire_stop_poll()
            if not cron._commit_progress(1):
                break

    # ------------------------------------------------------------------
    # Operaciones con SUNAT (historial, tickets y reportes)
    # ------------------------------------------------------------------

    def _sire_new_operation(self, kind, ticket='', filename=None, content=None,
                            detail=None, poll=None):
        """Registra una operación; con ticket, programa su consulta."""
        self.ensure_one()
        # sudo: el historial de operaciones es de solo lectura para el
        # contable; lo registra el módulo. Se devuelve en sudo para que el
        # que llama complete sus datos (tipo de ajuste, reportes).
        operation = self.env['l10n_pe.sire.operation'].sudo().create({
            'kind': kind,
            'res_model': self._name,
            'res_id': self.id,
            'company_id': self.company_id.id,
            'user_id': self.env.uid,
            'ticket': ticket or False,
            'ticket_state': '01' if ticket else False,
            'state': 'sent' if ticket else 'done',
            'file': base64.b64encode(content) if content else False,
            'filename': filename,
            'detail': detail,
        })
        if ticket and poll is not False:
            operation._schedule_poll()
        label = dict(self.env['l10n_pe.sire.operation']._fields['kind'].selection).get(kind)
        self._sire_log(_('%(kind)s: %(result)s', kind=label,
                         result=_('ticket %s', ticket) if ticket else (detail or _('hecho'))))
        return operation

    def _sire_attach_reports(self, token, register):
        """Descarga los archivos que SUNAT dejó en el ticket y los adjunta al periodo."""
        self.ensure_one()
        attachments = self.env['ir.attachment']
        existing = set(self.env['ir.attachment'].search([
            ('res_model', '=', self._name), ('res_id', '=', self.id),
        ]).mapped('name'))
        for report in register.get('archivoReporte') or []:
            name = report.get('nomArchivoReporte')
            if not name or name in existing:
                continue
            try:
                content = self._sire_download_file(token, report, self._sire_upload_book_code())
            except UserError as error:
                self._sire_log(_('No se pudo descargar el reporte %(name)s: %(error)s',
                                 name=name, error=error))
                continue
            attachments |= self.env['ir.attachment'].create({
                'name': name,
                'raw': content,
                'res_model': self._name,
                'res_id': self.id,
            })
        if attachments:
            self.message_post(
                body=_('Reportes de SUNAT del ticket %s.', register.get('numTicket') or ''),
                attachment_ids=attachments.ids)
        return attachments

    def _sire_clear_submission(self):
        """Tras eliminar en SUNAT el reemplazo o el preliminar, el periodo
        vuelve a «comparado» y admite un nuevo envío (antes quedaba
        bloqueado por el ticket del envío anterior)."""
        self.ensure_one()
        self.write({
            'submission_ticket': False,
            'submission_type': False,
            'submission_state': False,
            'state': 'compared' if self.state in ('submitted', 'done') else self.state,
        })
        self._sire_log(_('Envío anterior eliminado en SUNAT: el periodo admite '
                         'un nuevo envío.'))

    def _sire_operation_finished(self, operation):
        """Gancho al terminar un ticket de operación; por defecto, solo avisa."""
        if operation.state == 'error':
            self._sire_warn(_('SUNAT procesó con errores el ticket %(ticket)s (%(kind)s). '
                              'Revise los reportes adjuntos.', ticket=operation.ticket,
                              kind=dict(self.env['l10n_pe.sire.operation']._fields['kind'].selection).get(operation.kind)))
        else:
            self._sire_log(_('SUNAT terminó el ticket %(ticket)s (%(kind)s).',
                             ticket=operation.ticket,
                             kind=dict(self.env['l10n_pe.sire.operation']._fields['kind'].selection).get(operation.kind)))

    # ------------------------------------------------------------------
    # Otros
    # ------------------------------------------------------------------

    def action_reset(self):
        self.ensure_one()
        if self.submission_ticket:
            raise UserError(_(
                'El periodo ya se envió a SUNAT con el ticket %s. Rehacer las '
                'líneas aquí no deshace ese envío y dejaría el registro '
                'contando una cosa distinta de la declarada.',
                self.submission_ticket))
        self.sire_line_ids = [(5, 0, 0)]
        self.system_line_ids = [(5, 0, 0)]
        self.write({
            'export_file': False,
            'export_filename': False,
            'state': 'downloaded' if self.proposal_file else 'draft',
            'poll_next_date': False,
            'poll_attempts': 0,
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
    check_detail = fields.Text(
        string='Observaciones', readonly=True, copy=False,
        help='Reglas de SUNAT que la línea no cumple; se revisan al '
             'desplegar el sistema y antes de enviar el reemplazo.')
