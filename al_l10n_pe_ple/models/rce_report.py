# -*- coding: utf-8 -*-
"""Completa los formatos del RCE que genera ``l10n_pe_reports`` (Enterprise).

Enterprise 19 ya emite el **RCE 8.4** (handler ``…8.1…``, número de reporte
``08040002``) y el **RCE 8.5** (handler ``…8.2…``, ``08050000``) con los campos
oficiales en el orden correcto, pero deja fuera parte de la información:

* emite dos campos de más al final del 8.4 —fecha y número de la constancia de
  detracción— que pertenecían al PLE 8.1 clásico y no existen en la norma;
* deja siempre vacíos los campos 33 a 41 (clasificación, operadores, detracción,
  tipo de nota, estado del comprobante…);
* fija el indicador de moneda del nombre de archivo a soles.

Aquí se corrige todo eso serializando la línea según la estructura oficial y
obteniendo los datos con ``l10n_pe.rce.extractor`` (ORM), porque el motor de
consulta de Enterprise falla con un error de SQL:
ver ``docs/tecport/BUG_EE_RCE_SQL.md``.

Fuente: RS N.° 040-2022/SUNAT, anexos 8 y 9.
Ver ``docs/tecport/ESTRUCTURA_RCE_8_4_8_5.md``.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .ple_mixin import PLE_EXPECTED_FIELDS

# Campos del 8.4 que exigen consignar la fecha de vencimiento o de pago
# (campo 6). Tabla 11 del Anexo 1.
RCE_DUE_DATE_DOC_TYPES = ('14', '46', '50', '51', '52', '53', '54')

# Tipos de comprobante que representan una DAM o DSI: la serie lleva el código
# de aduana y se informa el año de emisión.
RCE_CUSTOMS_DOC_TYPES = ('50', '52')

# Tipos de comprobante que modifican otro documento (notas y anulaciones).
RCE_MODIFYING_DOC_TYPES = ('07', '08', '87', '88', '97', '98')

# El número oficial de campos vive en ``PLE_EXPECTED_FIELDS`` (ple_mixin),
# junto al del resto de formatos: una sola fuente de verdad.


class L10nPeRceCommon(models.AbstractModel):
    """Utilidades compartidas por los dos formatos del RCE."""
    _name = 'l10n_pe.rce.common'
    _description = 'RCE — utilidades comunes de serialización'

    # ------------------------------------------------------------------
    # Formato de campo
    # ------------------------------------------------------------------
    @api.model
    def _rce_amount(self, value):
        """Importe con 2 decimales, sin separador de miles y sin «-0.00»."""
        value = value or 0.0
        text = '%.2f' % value
        return '0.00' if float(text) == 0.0 else text

    @api.model
    def _rce_rate(self, value, currency_name):
        """Tipo de cambio ``#.###``; vacío cuando la operación es en soles."""
        if not value or currency_name == 'PEN':
            return ''
        return '%.3f' % abs(value)

    @api.model
    def _rce_date(self, value):
        return value.strftime('%d/%m/%Y') if value else ''

    @api.model
    def _rce_text(self, value, maxlen):
        """Texto saneado: sin pipes ni saltos de línea, truncado a ``maxlen``."""
        text = (value or '').replace('|', ' ').replace('\n', ' ')
        return ' '.join(text.split())[:maxlen]

    # ------------------------------------------------------------------
    # Serialización
    # ------------------------------------------------------------------
    @api.model
    def _rce_serialize(self, book_code, rows):
        """Une los campos con ``|`` y cierra cada línea con un pipe.

        Valida el número de campos contra la estructura oficial: un archivo
        con columnas de menos o de más es rechazado por SUNAT, así que es
        preferible fallar aquí que en la presentación.
        """
        expected = PLE_EXPECTED_FIELDS[book_code]
        out = []
        for row in rows:
            if len(row) != expected:
                raise UserError(_(
                    'Estructura RCE inválida para el formato %(code)s: se '
                    'generaron %(got)d campos y la norma exige %(expected)d.',
                    code=book_code, got=len(row), expected=expected))
            out.append('|'.join(str(value) for value in row) + '|')
        return ('\r\n'.join(out) + '\r\n').encode() if out else b''

    @api.model
    def _rce_filename(self, company, book_code, date_from, opportunity,
                      has_data, operations='1'):
        """Nombre oficial del registro (Tabla 13 del Anexo 1).

        ``LE`` + RUC(11) + ``AAAA`` + ``MM`` + ``00`` + libro(6) +
        oportunidad(2) + operaciones(1) + contenido(1) + moneda(1) +
        generador(1). El indicador de generador es ``2`` («generado por el
        SIRE») en todos los formatos del RCE.
        """
        ruc = (company.vat or '').strip()
        if len(ruc) != 11 or not ruc.isdigit():
            raise UserError(_(
                'La compañía %s no tiene un RUC válido de 11 dígitos.',
                company.display_name))
        currency_flag = '2' if company.currency_id.name == 'USD' else '1'
        return 'LE%s%04d%02d00%s%s%s%s%s2' % (
            ruc, date_from.year, date_from.month, book_code, opportunity,
            operations, '1' if has_data else '0', currency_flag)


class L10nPeRce84(models.AbstractModel):
    """RCE 8.4 — Registro de Compras (41 campos)."""
    _inherit = 'l10n_pe.tax.ple.8.1.report.handler'

    def export_to_txt(self, options):
        common = self.env['l10n_pe.rce.common']
        extractor = self.env['l10n_pe.rce.extractor']
        company = self.env.company
        date_from = fields.Date.to_date(options['date']['date_from'])
        date_to = fields.Date.to_date(options['date']['date_to'])
        period = '%04d%02d' % (date_from.year, date_from.month)

        group_ids = extractor._rce_tax_group_ids(company)
        moves = extractor._rce_moves(company, date_from, date_to)
        rows = [
            self._l10n_pe_rce_84_row(move, period, common, extractor, group_ids)
            for move in moves
        ]

        content = common._rce_serialize('080400', rows)
        return {
            'file_name': common._rce_filename(
                company, '080400', date_from, opportunity='02',
                has_data=bool(rows)),
            'file_content': content,
            'file_type': 'txt',
        }

    def _l10n_pe_rce_84_row(self, move, period, common, extractor, group_ids):
        """Construye los 41 campos de una línea del 8.4."""
        doc_code = move.l10n_latam_document_type_id.code or ''
        serie, folio = extractor._rce_serie_folio(move)
        partner_type, partner_vat, partner_name = \
            extractor._rce_partner_document(move)
        mod_date, mod_type, mod_serie, mod_folio = \
            extractor._rce_modified_document(move)
        amounts = extractor._rce_amounts(move, group_ids)
        is_customs = doc_code in RCE_CUSTOMS_DOC_TYPES
        customs_code = _leading_digits(serie, 3)
        currency = move.currency_id.name or ''
        cancelled = move.state == 'cancel'

        def amount(*keys):
            """Suma de los importes indicados; cero en comprobantes anulados."""
            if cancelled:
                return common._rce_amount(0.0)
            return common._rce_amount(sum(amounts.get(key, 0.0) for key in keys))

        return [
            # 1-3 · identificación del generador y periodo
            (move.company_id.vat or '').strip(),
            common._rce_text(move.company_id.name, 1500),
            period,
            # 4 · CAR: lo asigna SUNAT
            '',
            # 5-6 · fechas
            common._rce_date(move.invoice_date),
            common._rce_date(move.invoice_date_due)
            if doc_code in RCE_DUE_DATE_DOC_TYPES else '',
            # 7-11 · comprobante
            doc_code,
            customs_code if is_customs else serie,
            str(move.invoice_date.year) if (is_customs and move.invoice_date) else '',
            folio.lstrip('0'),
            '',                                    # 11 nº final del rango
            # 12-14 · proveedor
            partner_type,
            partner_vat,
            common._rce_text(partner_name, 1500),
            # 15-20 · bases e IGV por destino
            amount('base_igv'),
            amount('tax_igv'),
            amount('base_igv_g_ng'),
            amount('tax_igv_g_ng'),
            amount('base_igv_ng'),
            amount('tax_igv_ng'),
            # 21-25 · resto de importes
            amount('base_exo', 'base_ina', 'base_gra'),
            amount('tax_isc'),
            amount('tax_icbper'),
            amount('tax_other'),
            common._rce_amount(0.0 if cancelled else extractor._rce_total(move)),
            # 26-27 · moneda
            currency,
            common._rce_rate(extractor._rce_exchange_rate(move), currency),
            # 28-32 · documento modificado
            common._rce_date(mod_date),
            mod_type,
            mod_serie,
            customs_code if is_customs else '',
            mod_folio.lstrip('0'),
            # 33-37 · información complementaria
            move.l10n_pe_rce_classification or '',
            '',                                    # 34 operadores / partícipes
            '',                                    # 35 % de participación
            '',                                    # 36 IMB
            '',                                    # 37 CAR original / indicador
            # 38-41 · marcas
            'D' if self._l10n_pe_rce_has_detraction(move) else '',
            self._l10n_pe_rce_note_type(move, doc_code),
            move.l10n_pe_rce_status or '',
            '',                                    # 41 inconsistencias (SUNAT)
        ]

    # ------------------------------------------------------------------
    # Campos que dependen de otros módulos de la localización
    # ------------------------------------------------------------------
    @api.model
    def _l10n_pe_rce_has_detraction(self, move):
        """Campo 38. Se apoya en ``al_l10n_pe_detraction`` si está instalado."""
        return bool(move._fields.get('l10n_pe_detraction_applies')
                    and move.l10n_pe_detraction_applies)

    @api.model
    def _l10n_pe_rce_note_type(self, move, doc_code):
        """Campo 39: tipo de nota, solo en comprobantes que modifican otro."""
        if doc_code not in RCE_MODIFYING_DOC_TYPES:
            return ''
        reason = move._fields.get('l10n_pe_edi_refund_reason')
        return (move.l10n_pe_edi_refund_reason or '') if reason else ''


class L10nPeRce85(models.AbstractModel):
    """RCE 8.5 — Registro de Compras, operaciones con sujetos no domiciliados.

    35 campos (anexo 9 de la RS 040-2022). Los campos 25 a 29 y 31 —renta
    bruta, deducción, renta neta, tasa, impuesto retenido y exoneración— son
    opcionales en la norma y se emiten vacíos: dependen de una liquidación de
    renta de no domiciliados que Odoo no modela.
    """
    _inherit = 'l10n_pe.tax.ple.8.2.report.handler'

    def export_to_txt(self, options):
        common = self.env['l10n_pe.rce.common']
        extractor = self.env['l10n_pe.rce.extractor']
        company = self.env.company
        date_from = fields.Date.to_date(options['date']['date_from'])
        date_to = fields.Date.to_date(options['date']['date_to'])
        period = '%04d%02d' % (date_from.year, date_from.month)

        group_ids = extractor._rce_tax_group_ids(company)
        moves = extractor._rce_moves(company, date_from, date_to,
                                     non_domiciled=True)
        rows = [
            self._l10n_pe_rce_85_row(move, period, common, extractor, group_ids)
            for move in moves
        ]

        content = common._rce_serialize('080500', rows)
        return {
            'file_name': common._rce_filename(
                company, '080500', date_from, opportunity='00',
                has_data=bool(rows)),
            'file_content': content,
            'file_type': 'txt',
        }

    def _l10n_pe_rce_85_row(self, move, period, common, extractor, group_ids):
        """Construye los 35 campos de una línea del 8.5."""
        serie, folio = extractor._rce_serie_folio(move)
        amounts = extractor._rce_amounts(move, group_ids)
        partner = move.partner_id.commercial_partner_id
        country = partner.country_id
        currency = move.currency_id.name or ''
        cancelled = move.state == 'cancel'

        # El crédito fiscal de una operación con no domiciliados se sustenta en
        # otro documento (DUA, liquidación de compra o formulario de pago).
        credit_doc = move.l10n_pe_dua_invoice_id
        credit_serie, credit_folio = (
            extractor._rce_serie_folio(credit_doc) if credit_doc else ('', ''))

        def amount(*keys):
            if cancelled:
                return common._rce_amount(0.0)
            return common._rce_amount(sum(amounts.get(key, 0.0) for key in keys))

        return [
            # 1-3 · periodo, CAR y fecha
            period,
            '',                                    # 2 CAR: lo asigna SUNAT
            common._rce_date(move.invoice_date),
            # 4-6 · comprobante del no domiciliado
            move.l10n_latam_document_type_id.code or '',
            serie,
            folio.lstrip('0'),
            # 7-9 · importes
            amount('base_igv', 'base_igv_g_ng', 'base_igv_ng',
                   'base_exo', 'base_ina', 'base_gra'),
            amount('tax_other'),
            common._rce_amount(0.0 if cancelled else extractor._rce_total(move)),
            # 10-13 · documento que sustenta el crédito fiscal
            credit_doc.l10n_latam_document_type_id.code or '' if credit_doc else '',
            credit_serie,
            str(credit_doc.invoice_date.year)
            if (credit_doc and credit_doc.invoice_date) else '',
            credit_folio.lstrip('0'),
            # 14 · retención de IGV
            amount('tax_ret'),
            # 15-16 · moneda
            currency,
            common._rce_rate(extractor._rce_exchange_rate(move), currency),
            # 17-20 · sujeto no domiciliado
            country.l10n_pe_code or '',
            common._rce_text(partner.name, 100),
            common._rce_text(partner.street, 100),
            common._rce_text(partner.vat, 15),
            # 21-24 · beneficiario efectivo
            '',                                    # 21 identificación
            '',                                    # 22 razón social
            '',                                    # 23 país
            '',                                    # 24 vinculación económica
            # 25-29 · liquidación de la renta (no modelada en Odoo)
            '', '', '', '', '',
            # 30-34 · régimen aplicable
            country.l10n_pe_agreement_code or '',
            '',                                    # 31 exoneración aplicada
            move.l10n_pe_usage_type_id.code or '',
            move.l10n_pe_service_modality or '',
            '',                                    # 34 artículo 76 de la LIR
            # 35 · CAR del comprobante en ajustes posteriores
            '',
        ]


def _leading_digits(text, size):
    """Primeros ``size`` dígitos de una cadena (código de aduana de la DAM)."""
    digits = ''.join(char for char in (text or '') if char.isdigit())
    return digits[:size]
