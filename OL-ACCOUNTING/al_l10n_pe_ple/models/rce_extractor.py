# -*- coding: utf-8 -*-
"""Extracción de datos del RCE con el ORM.

Sustituye a ``_get_ple_report_data()`` de ``l10n_pe_reports``, que construye su
consulta a mano e inyecta el ``WHERE`` del ORM sobre un ``FROM`` escrito
literalmente: en cuanto el dominio necesita un JOIN, la consulta se rompe.
Ver ``docs/tecport/BUG_EE_RCE_SQL.md``.

Aquí todo se obtiene con ``search`` y agregación en Python: más lento sobre
volúmenes muy grandes, pero correcto y estable frente a cambios del ORM.
"""
from odoo import _, api, models
from odoo.exceptions import UserError

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

# Tipos de comprobante propios del registro de no domiciliados (8.5).
RCE_NON_DOMICILED_DOC_TYPES = ('00', '91', '97', '98')

# Tipos de comprobante que no forman parte del 8.4: los recibos por
# honorarios (02) van al RHE, y los del 8.5 no pueden salir también aquí
# (el '00' aparecía en los dos archivos).
RCE_EXCLUDED_DOC_TYPES = ('02',) + RCE_NON_DOMICILED_DOC_TYPES


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
        # Los grupos del plan viven en la compañía raíz: desde una sucursal
        # no se encontraban y todas las bases salían en cero.
        root = company.root_id
        for key in RCE_TAX_GROUPS:
            group = self.env.ref(
                'account.%s_tax_group_%s' % (root.id, key),
                raise_if_not_found=False)
            if group:
                groups[key] = group.id
        return groups

    # ------------------------------------------------------------------
    # Selección de comprobantes
    # ------------------------------------------------------------------
    @api.model
    def _ple_issued_domain(self):
        """Publicados, o anulados que llegaron a emitirse.

        Un borrador cancelado nunca existió para SUNAT; sí hay que informar
        (con su estado) el comprobante emitido y luego anulado. Solo cuentan
        los diarios que usan documentos LATAM, como en Enterprise.
        """
        return [
            '|', ('state', '=', 'posted'),
            '&', ('state', '=', 'cancel'), ('posted_before', '=', True),
            ('journal_id.l10n_latam_use_documents', '=', True),
        ]

    @api.model
    def _rce_move_domain(self, company, date_from, date_to,
                         non_domiciled=False):
        """Comprobantes de compra anotados en el periodo.

        El periodo del RCE es el de anotación (fecha contable), como en
        Enterprise y en el SIRE: una factura recibida tarde se anota en el
        mes en que se registra, no en el de su emisión.

        Solo comprobantes publicados: la nota 2 del anexo 11 (RS 040-2022)
        prohíbe anotar en el RCE los dados de baja, revertidos o anulados
        (la regla de anotarlos en cero es del RVIE). La separación entre el 8.4 y el 8.5 la marca el tipo de
        comprobante, no el país del proveedor: es el criterio de la norma y
        además evita depender de que el contacto tenga país informado.
        """
        domain = [
            # la compañía y sus sucursales (el libro es del RUC)
            ('company_id', 'child_of', company.root_id.id),
            ('move_type', 'in', ('in_invoice', 'in_refund')),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('state', '=', 'posted'),
            ('journal_id.l10n_latam_use_documents', '=', True),
        ]
        operator = 'in' if non_domiciled else 'not in'
        domain.append(
            ('l10n_latam_document_type_id.code', operator,
             RCE_NON_DOMICILED_DOC_TYPES if non_domiciled
             else RCE_EXCLUDED_DOC_TYPES))
        return domain + self._rce_excluded_journals_domain()

    @api.model
    def _rce_excluded_journals_domain(self):
        """Excluye los diarios marcados como ajenos a los libros electrónicos
        (campo de ``al_account_base``)."""
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
    def _rce_amounts(self, move, group_ids, isc_in_base=False):
        """Bases e impuestos del comprobante, en soles (moneda de la compañía).

        El registro lleva los importes convertidos con el T.C. y, aparte, la
        moneda y el T.C. (campos 26-27): así los declara la contabilidad real
        de referencia (13 223,10 USD → 46 214,73 con T.C. 3,495).

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
                if key == 'isc' and isc_in_base:
                    # RCE (nota 3 del anexo 11): el ISC de un ítem gravado va
                    # en la base del IGV de ese ítem (campos 15/17/19) y el de
                    # uno no gravado, en el campo 21; el campo 22 queda para
                    # el ISC deducible.
                    igv_keys = [by_id.get(tax.tax_group_id.id)
                                for tax in line.tax_ids]
                    igv_keys = [k for k in igv_keys
                                if k in ('igv', 'igv_g_ng', 'igv_ng')]
                    target = igv_keys[0] if igv_keys else 'exo'
                    amounts['base_%s' % target] += sign * line.balance
                    continue
                if key:
                    amounts['tax_%s' % key] += sign * line.balance
                # El ISC lleva ``include_base_amount``: su apunte tiene el IGV en
                # ``tax_ids`` y sumaba su importe a la base gravada. En el RVIE
                # la base no incluye el ISC (anexo 112-2021, nota 4).
                continue
            # Apunte base: aporta la base imponible a cada grupo que lo grava.
            # Los impuestos de grupo (p. ej. «gratuito»: IGV + transferencia)
            # se aplanan: el grupo padre es del IGV y sumaba la venta gratuita
            # a la base gravada.
            for tax in line.tax_ids.flatten_taxes_hierarchy():
                key = by_id.get(tax.tax_group_id.id)
                if key:
                    amounts['base_%s' % key] += sign * line.balance
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
        """Tipo de cambio del comprobante (moneda de la compañía por unidad).

        - Notas de crédito y débito: el del documento que modifican (anexo
          040-2022, nota 4; RVIE, nota 3).
        - Resto: la tasa almacenada de la factura (``invoice_currency_rate``,
          a la fecha de emisión). Antes se dividía el total en soles entre el
          total en moneda extranjera: fallaba en notas, en comprobantes
          gratuitos (total 0, sin T.C.) y por redondeo en importes pequeños.
        """
        origin = move.reversed_entry_id or move.debit_origin_id
        if origin and origin.currency_id == move.currency_id:
            return self._rce_exchange_rate(origin)
        if move.currency_id == move.company_currency_id:
            return 0.0
        if move.invoice_currency_rate:
            return 1.0 / move.invoice_currency_rate
        if not move.amount_total:
            return 0.0
        return abs(move.amount_total_signed / move.amount_total)

    @api.model
    def _rce_total(self, move):
        """Importe total en soles, negativo si es abono.

        La retención del IGV (3 %) no reduce el total del comprobante: Odoo la
        resta de ``amount_total``, pero el XML y el registro llevan el
        importe íntegro."""
        sign = -1 if move.move_type in ('in_refund', 'out_refund') else 1
        group = self.env.ref(
            'account.%s_tax_group_igv_withholding' % move.company_id.root_id.id,
            raise_if_not_found=False)
        withheld = abs(sum(
            line.balance for line in move.line_ids
            if group and line.tax_line_id.tax_group_id == group))
        return sign * (abs(move.amount_total_signed) + withheld)

    # ------------------------------------------------------------------
    # Registro de ventas (RVIE)
    # ------------------------------------------------------------------
    @api.model
    def _ple_check_modified_documents(self, moves, book):
        """Las notas (07/08/87/88) exigen los datos del comprobante que
        modifican (campos 28-32 del 8.4, 29-32 del 14.4); sin ellos SUNAT
        rechaza la línea. Se bloquea el TXT con la lista para corregirlas;
        el Excel de revisión no se bloquea: sirve justo para encontrarlas."""
        orphans = moves.filtered(
            lambda move: move.l10n_latam_document_type_id.code
            in ('07', '08', '87', '88')
            and not (move.reversed_entry_id or move.debit_origin_id))
        if orphans:
            raise UserError(_(
                'Estas notas de crédito o débito no están enlazadas al '
                'comprobante que modifican (registro %(book)s) y SUNAT las '
                'rechazaría. Regístrelas desde la factura de origen '
                '(«Nota de crédito» / «Nota de débito»):\n%(moves)s',
                book=book,
                moves='\n'.join('· %s' % name for name in orphans.mapped(
                    'display_name')[:30])))

    @api.model
    def _rvie_moves(self, company, date_from, date_to):
        """Comprobantes de venta del periodo, incluidos los anulados.

        La nota 4 del anexo 2 de la RS 112-2021 obliga a anotar los
        comprobantes anulados o con CDR no aceptado con importe cero, no a
        excluirlos del registro.
        """
        return self.env['account.move'].search([
            # la compañía y sus sucursales (el libro es del RUC)
            ('company_id', 'child_of', company.root_id.id),
            ('move_type', 'in', ('out_invoice', 'out_refund', 'out_receipt')),
            ('invoice_date', '>=', date_from),
            ('invoice_date', '<=', date_to),
        ] + self._ple_issued_domain() + self._rce_excluded_journals_domain(),
            order='invoice_date, name')
