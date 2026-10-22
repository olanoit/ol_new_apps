import re
import unicodedata
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

RECORD_TYPES = [('header', 'Cabecera'), ('detail', 'Detalle'), ('footer', 'Pie')]
KINDS = [
    ('constant', 'Constante'),
    ('text', 'Texto'),
    ('number', 'Número'),
    ('amount', 'Importe'),
    ('date', 'Fecha'),
    ('time', 'Hora'),
    ('currency', 'Moneda'),
    ('filler', 'Relleno'),
]
#: Datos que el motor sabe escribir (archivo de deudores) o leer (respuesta).
KEYS = [
    # Cabecera y detalle del archivo de deudores
    ('account_branch', 'Sucursal de la cuenta'),
    ('account_number', 'Número de cuenta'),
    ('account_full', 'Cuenta completa'),
    ('currency', 'Moneda'),
    ('company_name', 'Nombre de la empresa'),
    ('company_vat', 'RUC de la empresa'),
    ('file_date', 'Fecha del archivo'),
    ('record_count', 'Cantidad de registros'),
    ('total_amount', 'Importe total'),
    ('total_min_amount', 'Importe mínimo total'),
    ('file_mode', 'Tipo de archivo (reemplazo/actualización)'),
    ('file_version', 'Versión del envío del día'),
    ('service_code', 'Código de servicio'),
    ('depositor_code', 'Código del depositante'),
    ('depositor_name', 'Nombre del depositante'),
    ('return_info', 'Información de retorno (documento)'),
    ('issue_date', 'Fecha de emisión'),
    ('due_date', 'Fecha de vencimiento'),
    ('block_date', 'Fecha de bloqueo (último día de cobro)'),
    ('amount', 'Importe a cobrar'),
    ('late_amount', 'Importe de mora'),
    ('min_amount', 'Importe mínimo'),
    ('update_type', 'Tipo de actualización (A/M/E)'),
    ('document_number', 'Número de documento'),
    ('depositor_vat', 'Documento de identidad'),
    ('depositor_id_type', 'Tipo de documento de identidad (código SUNAT)'),
    # Respuesta del banco
    ('payment_date', 'Fecha de pago'),
    ('payment_time', 'Hora de pago'),
    ('paid_amount', 'Importe pagado'),
    ('paid_total', 'Total pagado'),
    ('operation_number', 'Número de operación'),
    ('branch', 'Agencia o canal'),
    ('channel', 'Medio de atención'),
    ('payment_type', 'Forma de pago'),
    ('reference', 'Referencia'),
    ('ignore', 'No se usa'),
]


class L10nPeBankCollectionLayout(models.Model):
    """Formato de un archivo de recaudación: registros de ancho fijo con sus
    campos. Escribe el archivo de deudores y lee la respuesta del banco con la
    misma definición, así que un cambio en la ficha técnica del banco se
    corrige aquí, sin programar."""
    _name = 'l10n_pe.bank.collection.layout'
    _description = 'Formato de recaudación bancaria'
    _order = 'bank_id, file_type, name'

    name = fields.Char(string='Formato', required=True)
    active = fields.Boolean(default=True)
    bank_id = fields.Many2one('res.bank', string='Banco')
    file_type = fields.Selection([('debtors', 'Archivo de deudores'), ('response', 'Respuesta del banco')],
                                 string='Archivo', required=True)
    record_length = fields.Integer(
        string='Longitud del registro', default=250,
        help='Cada línea se completa con espacios hasta esta longitud; 0 para no completar.')
    line_separator = fields.Selection([('crlf', 'CRLF (Windows)'), ('lf', 'LF')], string='Fin de línea',
                                      default='crlf', required=True)
    final_newline = fields.Boolean(string='Fin de línea tras el último registro')
    encoding = fields.Selection([('ascii', 'ASCII'), ('latin-1', 'Latin-1'), ('utf-8', 'UTF-8')],
                                string='Codificación', default='ascii', required=True,
                                help='En ASCII, las tildes y la ñ se cambian por su letra simple.')
    filename = fields.Char(string='Nombre del archivo', default='CREP_%(date)s.txt',
                           help='%(date)s = fecha AAAAMMDD; %(currency)s = código de la moneda; '
                                '%(service)s = código de servicio o clase del convenio.')
    currency_map = fields.Char(string='Códigos de moneda', default='PEN=0,USD=1',
                               help='Código que usa el banco para cada moneda, separados por comas.')
    replace_code = fields.Char(string='Código de reemplazo', default='R',
                               help='Valor del tipo de archivo cuando el envío reemplaza toda la base.')
    update_code = fields.Char(string='Código de actualización', default='A',
                              help='Valor del tipo de archivo cuando el envío solo agrega o modifica.')
    blank_chars = fields.Char(
        string='Caracteres a espacios',
        help='Caracteres que el banco no acepta en los textos y se cambian por un espacio.')
    field_ids = fields.One2many('l10n_pe.bank.collection.layout.field', 'layout_id', string='Campos', copy=True)
    note = fields.Text(string='Notas')

    @api.constrains('field_ids', 'record_length')
    def _check_fields(self):
        for layout in self:
            for record_type in ('header', 'detail', 'footer'):
                fields_ = layout.field_ids.filtered(lambda f: f.record_type == record_type).sorted('start')
                end = 0
                for field in fields_:
                    if field.start <= end:
                        raise ValidationError(_('%(layout)s: el campo «%(field)s» se superpone con el anterior.',
                                                layout=layout.name, field=field.name))
                    end = field.start + field.length - 1
                    if layout.record_length and end > layout.record_length:
                        raise ValidationError(_('%(layout)s: el campo «%(field)s» pasa la longitud del registro.',
                                                layout=layout.name, field=field.name))

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------

    def _currency_code(self, currency):
        return _parse_map(self.currency_map).get(currency.name, '')

    def _format_record(self, record_type, values):
        """Una línea de ancho fijo con los ``values`` (clave del campo → valor)."""
        self.ensure_one()
        line = ''
        for field in self.field_ids.filtered(lambda f: f.record_type == record_type).sorted('start'):
            line = line.ljust(field.start - 1)
            line += field._format(values.get(field.key), self)
        if self.record_length:
            line = line.ljust(self.record_length)[:self.record_length]
        return line

    def _build_file(self, header, details, footer=None):
        """Contenido del archivo (bytes) con la cabecera, los detalles y el pie."""
        self.ensure_one()
        records = []
        if self.field_ids.filtered(lambda f: f.record_type == 'header'):
            records.append(self._format_record('header', header))
        records += [self._format_record('detail', values) for values in details]
        if self.field_ids.filtered(lambda f: f.record_type == 'footer'):
            records.append(self._format_record('footer', footer or header))
        separator = '\r\n' if self.line_separator == 'crlf' else '\n'
        content = separator.join(records) + (separator if self.final_newline else '')
        return content.encode(self.encoding, errors='replace')

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------

    def _record_type_of(self, line):
        """Tipo de registro de una línea según sus constantes (p. ej. «DD»)."""
        self.ensure_one()
        for record_type in ('detail', 'header', 'footer'):
            constants = self.field_ids.filtered(lambda f: f.record_type == record_type and f.kind == 'constant')
            if constants and all(line[f.start - 1:f.start - 1 + f.length] == (f.value or '') for f in constants):
                return record_type
        return False

    def _parse_file(self, data):
        """Lee el archivo (bytes) y devuelve (cabecera, [detalles]) como diccionarios."""
        self.ensure_one()
        for encoding in (self.encoding, 'utf-8', 'latin-1'):
            try:
                text = data.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        header, details = {}, []
        for number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            record_type = self._record_type_of(line)
            if not record_type:
                raise UserError(_('Línea %(number)s: no corresponde al formato «%(layout)s».',
                                  number=number, layout=self.name))
            values = {'_line': number, '_raw': line}
            for field in self.field_ids.filtered(lambda f: f.record_type == record_type and f.key
                                                 and f.key != 'ignore'):
                values[field.key] = field._parse(line[field.start - 1:field.start - 1 + field.length], number)
            if record_type == 'detail':
                details.append(values)
            else:
                # Los totales pueden venir en la cabecera o en el pie.
                header.update({k: v for k, v in values.items() if not k.startswith('_') or not header})
        return header, details


class L10nPeBankCollectionLayoutField(models.Model):
    _name = 'l10n_pe.bank.collection.layout.field'
    _description = 'Campo del formato de recaudación'
    _order = 'record_type, start'

    layout_id = fields.Many2one('l10n_pe.bank.collection.layout', required=True, ondelete='cascade', index=True)
    record_type = fields.Selection(RECORD_TYPES, string='Registro', required=True, default='detail')
    name = fields.Char(string='Campo', required=True)
    start = fields.Integer(string='Desde', required=True, help='Posición inicial, empezando en 1.')
    length = fields.Integer(string='Longitud', required=True)
    end = fields.Integer(string='Hasta', compute='_compute_end')
    kind = fields.Selection(KINDS, string='Tipo', required=True, default='text')
    key = fields.Selection(KEYS, string='Dato')
    value = fields.Char(string='Valor fijo', help='Para las constantes y el relleno (carácter).')
    decimals = fields.Integer(string='Decimales', default=2, help='Implícitos: 1234 con 2 decimales es 12.34.')
    date_format = fields.Char(string='Formato de fecha', default='%Y%m%d')
    mapping = fields.Char(string='Equivalencias',
                          help='Valor de Odoo = valor del banco, separados por comas (p. ej. 6=R,1=L). Al leer '
                               'la respuesta se aplica al revés.')
    align = fields.Selection([('left', 'Izquierda'), ('right', 'Derecha')], string='Alineación',
                             compute='_compute_align', store=True, readonly=False)
    pad = fields.Char(string='Relleno con', size=1, compute='_compute_align', store=True, readonly=False)

    @api.depends('start', 'length')
    def _compute_end(self):
        for field in self:
            field.end = field.start + field.length - 1 if field.length else field.start

    @api.depends('kind')
    def _compute_align(self):
        for field in self:
            numeric = field.kind in ('number', 'amount')
            field.align = 'right' if numeric else 'left'
            field.pad = '0' if numeric else ' '

    @api.constrains('start', 'length', 'kind', 'value')
    def _check_values(self):
        for field in self:
            if field.start < 1 or field.length < 1:
                raise ValidationError(_('El campo «%s» necesita posición y longitud positivas.', field.name))
            if field.kind == 'constant' and len(field.value or '') != field.length:
                raise ValidationError(_('La constante «%s» debe tener exactamente su longitud.', field.name))

    def _format(self, value, layout):
        """Texto de ancho fijo del campo."""
        self.ensure_one()
        length, pad = self.length, self.pad or ' '
        if self.kind == 'constant':
            text = self.value or ''
        elif self.kind == 'filler':
            return (self.value or ' ')[:1] * length
        elif self.kind == 'amount':
            cents = Decimal(str(value or 0)).scaleb(self.decimals).quantize(Decimal(1), rounding=ROUND_HALF_UP)
            text = str(abs(int(cents)))
        elif self.kind == 'number':
            text = re.sub(r'\D', '', str(value or ''))
        elif self.kind in ('date', 'time'):
            text = value.strftime(self.date_format if self.kind == 'date' else '%H%M%S') if value else ''
        elif self.kind == 'currency':
            text = layout._currency_code(value) if value else ''
        else:
            text = str(value or '')
        if self.mapping and self.kind not in ('constant', 'filler'):
            text = _parse_map(self.mapping).get(text, text)
        if self.kind == 'text':
            for char in layout.blank_chars or '':
                text = text.replace(char, ' ')
        if layout.encoding == 'ascii':
            text = _to_ascii(text)
        if len(text) > length and self.kind in ('amount', 'number') and len(text.lstrip('0') or '0') <= length:
            text = text.lstrip('0') or '0'  # ceros a la izquierda que no caben (código 000000 en 3)
        if len(text) > length:
            if self.kind in ('amount', 'number'):
                raise UserError(_('El valor %(value)s no cabe en el campo «%(field)s» (%(length)s posiciones).',
                                  value=text, field=self.name, length=length))
            text = text[:length]
        return text.rjust(length, pad) if self.align == 'right' else text.ljust(length, pad)

    def _parse(self, text, line_number):
        """Valor Python del campo leído de la línea."""
        self.ensure_one()
        raw = text.strip()
        try:
            if self.kind == 'amount':
                digits = re.sub(r'\D', '', raw)
                return float(Decimal(digits or '0').scaleb(-self.decimals))
            if self.kind == 'date':
                return datetime.strptime(raw, self.date_format).date() if raw.strip('0') else False
            if self.kind == 'time':
                return raw
            if self.kind == 'currency':
                codes = dict(item.split('=', 1)[::-1] for item in
                             (self.layout_id.currency_map or '').replace(' ', '').split(',') if '=' in item)
                return codes.get(raw, raw)
            if self.kind == 'number':
                raw = raw.lstrip('0') or ('0' if raw else '')
        except ValueError as error:
            raise UserError(_('Línea %(number)s, campo «%(field)s»: valor «%(value)s» no válido (%(error)s).',
                              number=line_number, field=self.name, value=raw, error=error)) from error
        if self.mapping:
            reverse = {bank: odoo for odoo, bank in _parse_map(self.mapping).items()}
            raw = reverse.get(raw, raw)
        return raw


def _parse_map(text):
    """«a=b,c=d» → {'a': 'b', 'c': 'd'}."""
    pairs = (item.split('=', 1) for item in (text or '').split(',') if '=' in item)
    return {key.strip(): value.strip() for key, value in pairs}


def _to_ascii(text):
    """Cada carácter a su letra ASCII (á → a, ñ → n) o a un espacio, sin
    cambiar la longitud: los bancos piden ASCII y las posiciones son fijas."""
    result = []
    for char in text:
        plain = unicodedata.normalize('NFKD', char).encode('ascii', 'ignore').decode('ascii')
        result.append(plain[:1] or ' ')
    return ''.join(result)
