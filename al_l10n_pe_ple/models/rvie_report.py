# -*- coding: utf-8 -*-
"""RVIE 14.4 — Registro de Ventas e Ingresos Electrónico.

Enterprise 19 ya emite este formato (handler ``…14.1…``, número de reporte
``14040002``), pero con **dos campos de más** y sobre el mismo motor de
consulta roto que el RCE. Ver ``docs/tecport/BUG_EE_RCE_SQL.md``.

La estructura del archivo es la del **Anexo N.º 2 de la RS N.° 000112-2021/SUNAT**,
cuya nota 7 es explícita:

    «Cuando el generador complementa la Propuesta del RVIE deberá remitir
    información de los campos del 1 al 33 y del 41 al 57. La estructura no
    considerará los campos del 34 al 40.»

Los campos 41 a 57 son de libre utilización y, si no se usan, «no incluya ni la
información ni los palotes». El archivo queda por tanto en **33 campos**.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .ple_mixin import PLE_EXPECTED_FIELDS

# Notas de crédito y débito: cuando modifican un comprobante de un periodo
# anterior, su base e IGV se informan como descuento (campos 16 y 18).
RVIE_CREDIT_NOTE_DOC_TYPES = ('07', '87')

# Comprobantes que exigen fecha de vencimiento o de pago (campo 6).
RVIE_DUE_DATE_DOC_TYPES = ('14',)

RVIE_BOOK_CODE = '140400'
# El número de campos vive en ``PLE_EXPECTED_FIELDS`` (ple_mixin).


class L10nPeRvie144(models.AbstractModel):
    """RVIE 14.4 — Registro de Ventas e Ingresos (33 campos)."""
    _inherit = 'l10n_pe.tax.ple.14.1.report.handler'

    def export_to_txt(self, options):
        common = self.env['l10n_pe.rce.common']
        extractor = self.env['l10n_pe.rce.extractor']
        company = self.env.company
        date_from = fields.Date.to_date(options['date']['date_from'])
        date_to = fields.Date.to_date(options['date']['date_to'])
        period = '%04d%02d' % (date_from.year, date_from.month)

        group_ids = extractor._rce_tax_group_ids(company)
        moves = extractor._rvie_moves(company, date_from, date_to)
        rows = [
            self._l10n_pe_rvie_row(move, period, date_from, common, extractor,
                                   group_ids)
            for move in moves
        ]

        content = self._l10n_pe_rvie_serialize(rows)
        return {
            'file_name': common._rce_filename(
                company, RVIE_BOOK_CODE, date_from, opportunity='02',
                has_data=bool(rows)),
            'file_content': content,
            'file_type': 'txt',
        }

    @api.model
    def _l10n_pe_rvie_serialize(self, rows):
        """Serializa validando que cada línea tenga los 33 campos."""
        out = []
        for row in rows:
            if len(row) != PLE_EXPECTED_FIELDS[RVIE_BOOK_CODE]:
                raise UserError(_(
                    'Estructura RVIE inválida: se generaron %(got)d campos y '
                    'la norma exige %(expected)d.',
                    got=len(row), expected=PLE_EXPECTED_FIELDS[RVIE_BOOK_CODE]))
            out.append('|'.join(str(value) for value in row) + '|')
        return ('\r\n'.join(out) + '\r\n').encode() if out else b''

    def _l10n_pe_rvie_row(self, move, period, date_from, common, extractor,
                          group_ids):
        """Construye los 33 campos de una línea del RVIE 14.4."""
        doc_code = move.l10n_latam_document_type_id.code or ''
        serie, folio = extractor._rce_serie_folio(move)
        partner_type, partner_vat, partner_name = \
            extractor._rce_partner_document(move)
        mod_date, mod_type, mod_serie, mod_folio = \
            extractor._rce_modified_document(move)
        amounts = extractor._rce_amounts(move, group_ids)
        currency = move.currency_id.name or ''

        # Nota 4 del anexo: los comprobantes anulados o con CDR no aceptado se
        # anotan con importe cero, no se excluyen del registro.
        cancelled = move.state == 'cancel'

        # Una nota de crédito que modifica un comprobante de un periodo
        # anterior se informa como descuento (campos 16 y 18), no como base
        # negativa del periodo.
        as_discount = bool(
            doc_code in RVIE_CREDIT_NOTE_DOC_TYPES
            and mod_date and mod_date < date_from and not cancelled)

        def amount(*keys):
            if cancelled:
                return common._rce_amount(0.0)
            return common._rce_amount(sum(amounts.get(key, 0.0) for key in keys))

        zero = common._rce_amount(0.0)

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
            if doc_code in RVIE_DUE_DATE_DOC_TYPES else '',
            # 7-10 · comprobante
            doc_code,
            serie,
            folio.lstrip('0'),
            '',                                    # 10 nº final del rango
            # 11-13 · cliente
            partner_type,
            partner_vat,
            common._rce_text(partner_name, 1500),
            # 14 · exportación
            amount('base_exp'),
            # 15-18 · gravadas y sus descuentos
            zero if as_discount else amount('base_igv'),
            amount('base_igv') if as_discount else zero,
            zero if as_discount else amount('tax_igv'),
            amount('tax_igv') if as_discount else zero,
            # 19-25 · resto de importes
            amount('base_exo'),
            amount('base_ina'),
            amount('tax_isc'),
            amount('base_ivap'),
            amount('tax_ivap'),
            amount('tax_icbper'),
            amount('tax_other'),
            # 26 · total
            common._rce_amount(0.0 if cancelled else extractor._rce_total(move)),
            # 27-28 · moneda
            currency,
            common._rce_rate(extractor._rce_exchange_rate(move), currency),
            # 29-32 · documento modificado
            common._rce_date(mod_date),
            mod_type,
            mod_serie,
            mod_folio.lstrip('0'),
            # 33 · contratos de colaboración empresarial
            '',
        ]
