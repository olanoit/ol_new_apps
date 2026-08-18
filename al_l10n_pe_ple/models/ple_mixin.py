# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.exceptions import UserError

# Nº exacto de campos por formato según el Anexo 2 de SUNAT
# (docs/ple/Estructura del PLE.xls). Los campos de libre utilización
# posteriores al campo "Estado" no se emiten (sin palotes).
PLE_EXPECTED_FIELDS = {
    '010100': 19, '010200': 15,
    '030100': 5, '030200': 8, '030300': 9, '030400': 9, '030500': 9,
    '030600': 12, '030700': 13, '030800': 12, '030900': 9,
    '031100': 10, '031200': 9, '031300': 10, '031400': 8, '031500': 12,
    '031601': 6, '031602': 8, '031700': 19, '031800': 5, '031900': 16,
    '032000': 5, '032400': 5, '032500': 5,
    '040100': 10,
    '050100': 21, '050200': 21, '050300': 8, '050400': 8,
    '060100': 21,
    '070100': 37, '070300': 15, '070400': 11,
    '080100': 42, '080200': 36, '080300': 32,
    '090100': 22, '090200': 21,
    '100100': 6, '100200': 8, '100300': 13, '100400': 7,
    '120100': 19, '130100': 27,
    '140100': 35, '140200': 26,
    # RCE (SIRE) — RS 040-2022/SUNAT, anexos 8 y 9.
    # Ver docs/tecport/ESTRUCTURA_RCE_8_4_8_5.md
    '080400': 41, '080500': 35,
    # RVIE (SIRE) — RS 000112-2021/SUNAT, anexo 2. La nota 7 excluye del
    # archivo los campos 34 a 40, de ahí los 33.
    # Ver docs/tecport/ESTRUCTURA_RVIE_14_4.md
    '140400': 33,
}

# Libros anuales: el nombre de archivo consigna MM=00
PLE_ANNUAL_BOOKS = ('07', '10')

# Formatos del RCE (SIRE). Su nombre de archivo lleva el indicador de
# generación «2» (generado por el SIRE) en lugar del «1» del PLE, y el
# código de oportunidad (posiciones 28-29) tiene su propia tabla.
PLE_SIRE_BOOKS = ('080400', '080500')

# Código de oportunidad de presentación del RCE (Tabla 13, posiciones 28-29)
RCE_OPPORTUNITY_NON_DOMICILED = '00'   # RC no domiciliados informado
RCE_OPPORTUNITY_ACCEPT = '01'          # cuando acepta la propuesta
RCE_OPPORTUNITY_REPLACE = '02'         # cuando reemplaza la propuesta
RCE_OPPORTUNITY_ADJUSTMENT = '03'      # cuando realiza ajustes posteriores

# Caracteres prohibidos dentro de un campo (reglas generales del PLE)
PLE_FORBIDDEN_CHARS = '|/\\'


class L10nPePleMixin(models.AbstractModel):
    """Motor común de los Libros Electrónicos PLE de SUNAT.

    Centraliza las Reglas Generales del Anexo 2: nomenclatura del archivo
    (33 caracteres), serialización de líneas con separador ``|``, formatos de
    fecha/importe y validación del número de campos por formato.
    """
    _name = 'l10n_pe.ple.mixin'
    _description = 'PLE SUNAT - motor común'

    # ------------------------------------------------------------------
    # Nomenclatura
    # ------------------------------------------------------------------
    @api.model
    def _ple_ruc(self, company):
        ruc = (company.vat or '').strip()
        if len(ruc) != 11 or not ruc.isdigit():
            raise UserError(_(
                'La compañía %s no tiene configurado un RUC válido de 11 '
                'dígitos (NIF).', company.display_name))
        return ruc

    @api.model
    def _ple_currency_flag(self, company):
        # 1 = Soles, 2 = US dólares
        return '2' if company.currency_id.name == 'USD' else '1'

    @api.model
    def _ple_filename(self, company, book_code, year, month=0, day=0,
                      opportunity='00', operations='1', has_data=True,
                      extension='.txt', sequence=''):
        """Nombre oficial: LE RUC(11) AAAA MM DD LLLLLL CC O I M G [NN] .txt

        ``month``/``day`` en 0 emiten «00» (libros anuales / distintos al
        libro 3). ``opportunity`` (CC) aplica al libro 3 y, con su propia
        tabla, a los formatos del RCE. El 3.23 (notas a los EEFF) se
        presenta en PDF: ``extension='.pdf'``.

        Para los formatos del RCE (8.4 y 8.5) el indicador de la posición 33
        es «2» (generado por el SIRE) en lugar de «1», y ``sequence`` añade
        el correlativo NN de los ajustes posteriores.
        """
        if book_code not in PLE_EXPECTED_FIELDS and book_code != '032300':
            raise UserError(_('Código de formato PLE desconocido: %s', book_code))
        if book_code[:2] in PLE_ANNUAL_BOOKS:
            month = 0
        generator = '2' if book_code in PLE_SIRE_BOOKS else '1'
        return 'LE%s%04d%02d%02d%s%s%s%s%s%s%s%s' % (
            self._ple_ruc(company), year, month, day, book_code, opportunity,
            operations, '1' if has_data else '0',
            self._ple_currency_flag(company), generator, sequence, extension,
        )

    # ------------------------------------------------------------------
    # Formatos de campo
    # ------------------------------------------------------------------
    @api.model
    def _ple_amount(self, value, decimals=2):
        """Importe sin separador de miles; negativos como ``-#.##``."""
        value = value or 0.0
        text = '%.*f' % (decimals, value)
        # normaliza el «-0.00»
        if float(text) == 0.0:
            text = '%.*f' % (decimals, 0.0)
        return text

    @api.model
    def _ple_rate(self, value):
        """Tipo de cambio ``#.###`` (3 decimales)."""
        return self._ple_amount(value, decimals=3)

    @api.model
    def _ple_date(self, value):
        """Fecha ``DD/MM/AAAA``; vacío si no hay valor."""
        return value.strftime('%d/%m/%Y') if value else ''

    @api.model
    def _ple_text(self, value, maxlen, default=''):
        """Texto saneado: sin ``| / \\`` ni saltos de línea, truncado."""
        text = (value or default).strip()
        for char in PLE_FORBIDDEN_CHARS:
            text = text.replace(char, '-')
        text = ' '.join(text.split())
        return text[:maxlen]

    # ------------------------------------------------------------------
    # Serialización y validación
    # ------------------------------------------------------------------
    @api.model
    def _ple_line(self, book_code, values):
        """Une los campos con ``|`` validando la estructura del formato."""
        expected = PLE_EXPECTED_FIELDS.get(book_code)
        if expected and len(values) != expected:
            raise UserError(_(
                'Estructura PLE inválida para %(code)s: se generaron '
                '%(got)d campos y el Anexo 2 exige %(expected)d.',
                code=book_code, got=len(values), expected=expected))
        return '|'.join(str(v) for v in values)

    @api.model
    def _ple_content(self, book_code, lines):
        """Contenido del TXT (CRLF, igual que ``l10n_pe_reports`` EE)."""
        if not lines:
            return b''
        joined = '\r\n'.join(
            self._ple_line(book_code, values) for values in lines)
        return (joined + '\r\n').encode()

    @api.model
    def _ple_check_structure(self, book_code, line):
        """Valida una línea ya serializada (usado por los tests)."""
        expected = PLE_EXPECTED_FIELDS.get(book_code)
        return expected is not None and len(line.split('|')) == expected
