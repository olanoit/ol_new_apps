# -*- coding: utf-8 -*-
"""Extracción de datos del RCE con el ORM.

Sustituye a ``_get_ple_report_data()`` de ``l10n_pe_reports``, que construye su
consulta a mano e inyecta el ``WHERE`` del ORM sobre un ``FROM`` escrito
literalmente: en cuanto el dominio necesita un JOIN, la consulta se rompe.
Ver ``docs/tecport/BUG_EE_RCE_SQL.md``.

Aquí todo se obtiene con ``search`` y agregación en Python: más lento sobre
volúmenes muy grandes, pero correcto y estable frente a cambios del ORM.
"""
from odoo import api, models

# Grupos de impuestos de la localización peruana, por XMLID
# ``account.{company_id}_tax_group_{clave}``.
RCE_TAX_GROUPS = (
    'igv',        # gravadas destinadas a operaciones gravadas
    'igv_g_ng',   # gravadas destinadas a gravadas y no gravadas
    'igv_ng',     # gravadas destinadas a no gravadas
    'exo',        # exoneradas
    'ina',        # inafectas
    'exp',        # exportación
    'gra',        # gratuitas
    'isc',        # impuesto selectivo al consumo
    'icbper',     # impuesto a las bolsas de plástico
    'other',      # otros tributos y cargos
    'ivap',       # IVAP
    'ret',        # retenciones
)

# Tipos de comprobante que no forman parte del RCE: los recibos por honorarios
# van al RHE, y 91/97/98 corresponden a operaciones con no domiciliados (8.5).
RCE_EXCLUDED_DOC_TYPES = ('91', '97', '98')

# Tipos de comprobante propios del registro de no domiciliados (8.5).
RCE_NON_DOMICILED_DOC_TYPES = ('00', '91', '97', '98')


class L10nPeRceExtractor(models.AbstractModel):
    _name = 'l10n_pe.rce.extractor'
    _description = 'RCE — extracción de comprobantes e importes'

    # ------------------------------------------------------------------
    # Grupos de impuestos
    # ------------------------------------------------------------------
    @api.model
    def _rce_tax_group_ids(self, company):
        """``{clave: id}`` de los grupos de impuestos peruanos de la compañía."""
        groups = {}
        for key in RCE_TAX_GROUPS:
            group = self.env.ref(
                'account.%s_tax_group_%s' % (company.id, key),
                raise_if_not_found=False)
            if group:
                groups[key] = group.id
        return groups

    # ------------------------------------------------------------------
    # Selección de comprobantes
    # ------------------------------------------------------------------
    @api.model
    def _rce_move_domain(self, company, date_from, date_to,
                         non_domiciled=False):
        """Comprobantes de compra del periodo.

        Se incluyen los anulados: SUNAT exige informarlos con su estado, no
        omitirlos. La separación entre el 8.4 y el 8.5 la marca el tipo de
        comprobante, no el país del proveedor: es el criterio de la norma y
        además evita depender de que el contacto tenga país informado.
        """
        domain = [
            ('company_id', '=', company.id),
            ('move_type', 'in', ('in_invoice', 'in_refund')),
            ('state', 'in', ('posted', 'cancel')),
            ('invoice_date', '>=', date_from),
            ('invoice_date', '<=', date_to),
        ]
        operator = 'in' if non_domiciled else 'not in'
        domain.append(
            ('l10n_latam_document_type_id.code', operator,
             RCE_NON_DOMICILED_DOC_TYPES if non_domiciled
             else RCE_EXCLUDED_DOC_TYPES))
        return domain + self._rce_excluded_journals_domain()

    @api.model
    def _rce_excluded_journals_domain(self):
        """Excluye los diarios marcados como ajenos a los libros electrónicos.

        Depende de ``al_account_base``; si el campo no existe, no filtra nada.
        """
        if 'l10n_pe_exclude_from_books' not in self.env['account.journal']._fields:
            return []
        return [('journal_id.l10n_pe_exclude_from_books', '=', False)]

    @api.model
    def _rce_moves(self, company, date_from, date_to, non_domiciled=False):
        return self.env['account.move'].search(
            self._rce_move_domain(company, date_from, date_to, non_domiciled),
            order='invoice_date, name')

    # ------------------------------------------------------------------
    # Importes por grupo de impuesto
    # ------------------------------------------------------------------
    @api.model
    def _rce_amounts(self, move, group_ids):
        """Bases e impuestos del comprobante, en su propia moneda.

        Devuelve un diccionario con una entrada ``base_<clave>`` y otra
        ``tax_<clave>`` por cada grupo de impuestos peruano. Los importes se
        emiten siempre en positivo para facturas y en negativo para abonos,
        con independencia de si el comprobante es de compra o de venta.
        """
        by_id = {gid: key for key, gid in group_ids.items()}
        # En una venta el ingreso se anota al haber, luego hay que invertir
        # el signo contable para informar importes positivos.
        sign = -1 if move.move_type in ('out_invoice', 'out_refund',
                                        'out_receipt') else 1
        amounts = {}
        for key in group_ids:
            amounts['base_%s' % key] = 0.0
            amounts['tax_%s' % key] = 0.0

        for line in move.line_ids:
            if line.display_type in ('line_section', 'line_subsection',
                                     'line_note'):
                continue
            # Apunte de impuesto: aporta la cuota del grupo al que pertenece.
            if line.tax_line_id:
                key = by_id.get(line.tax_line_id.tax_group_id.id)
                if key:
                    amounts['tax_%s' % key] += sign * line.amount_currency
            # Apunte base: aporta la base imponible a cada grupo que lo grava.
            for tax in line.tax_ids:
                key = by_id.get(tax.tax_group_id.id)
                if key:
                    amounts['base_%s' % key] += sign * line.amount_currency
        return amounts

    # ------------------------------------------------------------------
    # Datos del comprobante
    # ------------------------------------------------------------------
    @api.model
    def _rce_serie_folio(self, move):
        """(serie, número) a partir del número de documento LATAM."""
        name = (move.l10n_latam_document_number or move.name or '').strip()
        name = name.replace(' ', '')
        if '-' in name:
            serie, _, folio = name.partition('-')
            return serie, folio
        return '', name

    @api.model
    def _rce_partner_document(self, move):
        """(código de tipo de documento, número, nombre) del proveedor."""
        partner = move.partner_id.commercial_partner_id
        return (
            partner.l10n_latam_identification_type_id.l10n_pe_vat_code or '',
            partner.vat or '',
            partner.name or '',
        )

    @api.model
    def _rce_modified_document(self, move):
        """(fecha, tipo, serie, número) del comprobante que se modifica."""
        origin = move.reversed_entry_id or move.debit_origin_id
        if not origin:
            return False, '', '', ''
        serie, folio = self._rce_serie_folio(origin)
        return (
            origin.invoice_date,
            origin.l10n_latam_document_type_id.code or '',
            serie,
            folio,
        )

    @api.model
    def _rce_exchange_rate(self, move):
        """Tipo de cambio aplicado al comprobante."""
        if move.currency_id == move.company_currency_id:
            return 0.0
        if not move.amount_total:
            return 0.0
        return abs(move.amount_total_signed / move.amount_total)

    @api.model
    def _rce_total(self, move):
        """Importe total en la moneda del comprobante, negativo si es abono."""
        sign = -1 if move.move_type in ('in_refund', 'out_refund') else 1
        return sign * move.amount_total

    # ------------------------------------------------------------------
    # Registro de ventas (RVIE)
    # ------------------------------------------------------------------
    @api.model
    def _rvie_moves(self, company, date_from, date_to):
        """Comprobantes de venta del periodo, incluidos los anulados.

        La nota 4 del anexo 2 de la RS 112-2021 obliga a anotar los
        comprobantes anulados o con CDR no aceptado con importe cero, no a
        excluirlos del registro.
        """
        return self.env['account.move'].search([
            ('company_id', '=', company.id),
            ('move_type', 'in', ('out_invoice', 'out_refund', 'out_receipt')),
            ('state', 'in', ('posted', 'cancel')),
            ('invoice_date', '>=', date_from),
            ('invoice_date', '<=', date_to),
        ] + self._rce_excluded_journals_domain(), order='invoice_date, name')
