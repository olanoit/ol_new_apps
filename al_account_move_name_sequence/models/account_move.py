# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    edi_series_id = fields.Many2one(
        'edi.invoice.series', string='Serie CPE',
        compute='_compute_edi_series_id', store=True, readonly=False,
        copy=False, check_company=True,
        domain="[('id', 'in', journal_edi_series_ids)]",
        help='Serie con la que se numera este comprobante. Por defecto, la '
             'primera serie publicada del diario que coincide con el tipo '
             'de documento.')
    journal_edi_series_ids = fields.Many2many(
        'edi.invoice.series', related='journal_id.edi_series_ids')

    @api.depends('journal_id', 'l10n_latam_document_type_id', 'state')
    def _compute_edi_series_id(self):
        """Al cambiar de diario (o de tipo de documento) la serie se
        revalida: si la elegida ya no es candidata del diario nuevo se
        limpia, y si el diario tiene UNA sola serie candidata se asigna
        automáticamente. Con varias candidatas se deja la elección al
        usuario."""
        for move in self:
            if move.state != 'draft':
                move.edi_series_id = move.edi_series_id
                continue
            # Cambio de diario/tipo de documento → la serie se limpia
            # siempre y solo se autoasigna cuando hay UNA candidata.
            candidates = move._al_candidate_edi_series()
            move.edi_series_id = candidates if len(candidates) == 1 else False

    def _al_candidate_edi_series(self):
        """Series válidas para este comprobante en su diario actual."""
        self.ensure_one()
        journal = self.journal_id
        if not (journal.use_name_sequence and journal.edi_series_ids):
            return self.env['edi.invoice.series']
        doc_code = self.l10n_latam_document_type_id.code
        series = journal.edi_series_ids.filtered(lambda s: s.state == 'publish')
        if doc_code in ('01', '03'):
            series = series.filtered(lambda s: s.edi_type_code == doc_code)
        elif doc_code in ('07', '08'):
            # NC/ND: manda la serie del documento de origen.
            origin = (self.reversed_entry_id
                      or getattr(self, 'debit_origin_id', self.env['account.move']))
            if origin and origin.edi_series_id:
                return origin.edi_series_id
        return series

    # ------------------------------------------------------------------
    # Resolución de la secuencia
    # ------------------------------------------------------------------
    def _al_get_series_sequence(self):
        """Secuencia de la serie CPE del comprobante, si aplica: el propio
        comprobante (01/03) usa la secuencia de la serie; las NC (07) y ND
        (08) usan la secuencia rectificativa de la serie del documento de
        origen (o de la serie propia como respaldo)."""
        self.ensure_one()
        doc_code = self.l10n_latam_document_type_id.code
        serie = self.edi_series_id
        if doc_code == '07':
            serie = (self.reversed_entry_id.edi_series_id or serie)
            return serie.credit_note_seq_id
        if doc_code == '08':
            origin = getattr(self, 'debit_origin_id', self.env['account.move'])
            serie = (origin.edi_series_id if origin else serie) or serie
            return serie.debit_note_seq_id
        return serie.invoice_seq_id

    def _al_uses_name_sequence(self):
        self.ensure_one()
        journal = self.journal_id
        if not journal.use_name_sequence:
            return False
        if journal.l10n_latam_use_documents:
            # Con documentos latam SOLO cuentan las series CPE: sin serie
            # resoluble, el comprobante numera de forma nativa.
            return bool(self._al_get_series_sequence())
        return bool(journal.name_sequence_id)

    def _al_get_name_sequence(self):
        self.ensure_one()
        journal = self.journal_id
        if journal.l10n_latam_use_documents:
            return self._al_get_series_sequence()
        if (self.move_type in ('out_refund', 'in_refund')
                and journal.refund_name_sequence_id):
            return journal.refund_name_sequence_id
        return journal.name_sequence_id

    @api.depends('posted_before', 'state', 'journal_id', 'date', 'move_type',
                 'origin_payment_id')
    def _compute_name(self):
        """Diarios con "Numerar por secuencia": el nombre sale de la
        ir.sequence (de la serie CPE o del diario) al publicar; el resto
        sigue el flujo nativo intacto (incluida la numeración latam). El
        nombre generado (p. ej. «F001-00000001») no lleva espacio, así que
        _compute_l10n_latam_document_number lo toma completo como número
        de documento serie-folio."""
        seq_moves = self.filtered(
            lambda m: m.state == 'posted'
            and (not m.name or m.name == '/')
            and m._al_uses_name_sequence())
        for move in seq_moves.sorted(lambda m: (m.date, m.ref or '', m._origin.id)):
            seq = move._al_get_name_sequence()
            # ir_sequence_date: aplica la fecha del asiento tanto al prefijo
            # con patrones de fecha como a los rangos de fecha de la secuencia.
            move.name = seq.with_context(ir_sequence_date=move.date).next_by_id()
        super(AccountMove, self - seq_moves)._compute_name()
        if seq_moves:
            # Sincroniza sequence_prefix/sequence_number almacenados, igual
            # que hace el compute nativo al terminar.
            seq_moves._inverse_name()

    def _constrains_date_sequence(self):
        # El chequeo nativo nombre↔fecha no aplica cuando la numeración la
        # controla una ir.sequence del usuario (su prefijo puede llevar
        # cualquier patrón).
        moves = self.filtered(lambda m: not m._al_uses_name_sequence())
        return super(AccountMove, moves)._constrains_date_sequence()

    def _is_end_of_seq_chain(self):
        """Sin aviso de renumeración al cancelar/eliminar en diarios con
        secuencia no_gap: la secuencia no reutiliza números, el hueco es
        deliberado."""
        seq_moves = self.filtered(
            lambda m: m._al_uses_name_sequence()
            and m._al_get_name_sequence().implementation == 'no_gap')
        others = self - seq_moves
        if seq_moves and not others:
            return False
        return super(AccountMove, others)._is_end_of_seq_chain()
