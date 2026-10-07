# -*- coding: utf-8 -*-
import re

from odoo import api, fields, models

from .product_template import RCE_CLASSIFICATION

# Tabla 14 del Anexo 1 de la RS 040-2022/SUNAT: estado de validez del
# comprobante. Alimenta el campo 40 del formato RCE 8.4.
RCE_STATUS = [
    ('1', '1 - Activo'),
    ('2', '2 - Baja'),
    ('3', '3 - Revertido'),
    ('4', '4 - Anulado'),
    ('5', '5 - Autorizado (comprobante físico)'),
    ('6', '6 - No autorizado (comprobante físico)'),
]

# Tipos de comprobante que se revierten en lugar de darse de baja:
# liquidaciones de compra (04) y recibos por honorarios (02).
RCE_REVERSIBLE_DOC_TYPES = ('02', '04')


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _l10n_pe_cdr_rejected(self):
        """El comprobante tiene un CDR de rechazo de SUNAT (códigos 2000-3999).

        En v19 ``l10n_pe_edi`` deja el documento EDI «por enviar» con error
        bloqueante, igual que uno que todavía no se envió; solo el código
        del mensaje («2800|…») los distingue. Los códigos 0100-1999 son
        excepciones (no se recibió: se reenvía) y los 4000+ observaciones
        (aceptado).
        """
        self.ensure_one()
        if 'edi_document_ids' not in self._fields:
            return False
        for document in self.edi_document_ids:
            if document.state != 'to_send' or document.blocking_level != 'error' \
                    or not document.error:
                continue
            codes = re.findall(r'(?<!\d)(\d{4})\|', document.error)
            if any(2000 <= int(code) <= 3999 for code in codes):
                return True
        return False

    l10n_pe_rce_classification = fields.Selection(
        RCE_CLASSIFICATION,
        string='Clasificación RCE',
        compute='_compute_l10n_pe_rce_classification',
        store=True, readonly=False,
        help='Clasificación de los bienes y servicios adquiridos (campo 33 '
             'del RCE 8.4). Se propone desde los productos de la factura y '
             'puede corregirse a mano.')

    l10n_pe_rce_status = fields.Selection(
        RCE_STATUS,
        string='Estado RCE',
        compute='_compute_l10n_pe_rce_status',
        store=True, readonly=False,
        help='Estado de validez del comprobante ante SUNAT (campo 40 del RCE '
             '8.4), según la tabla 14. Se deduce del estado del asiento; '
             'puede corregirse a mano.')

    # ------------------------------------------------------------------
    # Clasificación (campo 33)
    # ------------------------------------------------------------------
    @api.depends('invoice_line_ids.product_id.l10n_pe_rce_classification',
                 'invoice_line_ids.price_subtotal')
    def _compute_l10n_pe_rce_classification(self):
        """Toma la clasificación del producto con mayor importe en la factura.

        SUNAT pide un único código por comprobante, no por línea; ante varias
        clasificaciones distintas gana la de mayor peso económico.

        Solo se propone en facturas de proveedor en borrador (o publicadas
        aún sin clasificación): cambiar la clasificación de un producto no
        debe reescribir comprobantes ya publicados (y quizá declarados) ni la
        corrección manual del usuario.
        """
        for move in self:
            if move.move_type not in ('in_invoice', 'in_refund'):
                move.l10n_pe_rce_classification = False
                continue
            if move.state != 'draft' and move.l10n_pe_rce_classification:
                # Publicado con valor: se conserva (pudo corregirse a mano o
                # declararse). Si el cálculo pendiente del alta se resuelve ya
                # publicado y vacío, sí se propone.
                move.l10n_pe_rce_classification = move.l10n_pe_rce_classification
                continue
            totals = {}
            for line in move.invoice_line_ids:
                code = line.product_id.product_tmpl_id.l10n_pe_rce_classification
                if code:
                    totals[code] = totals.get(code, 0.0) + abs(line.price_subtotal)
            move.l10n_pe_rce_classification = (
                max(totals, key=totals.get) if totals else False)

    # ------------------------------------------------------------------
    # Estado de validez (campo 40)
    # ------------------------------------------------------------------
    @api.depends('state', 'move_type', 'l10n_latam_document_type_id.code')
    def _compute_l10n_pe_rce_status(self):
        for move in self:
            if move.move_type not in ('in_invoice', 'in_refund'):
                move.l10n_pe_rce_status = False
                continue
            doc_code = move.l10n_latam_document_type_id.code or ''
            if move.state == 'cancel':
                # Las liquidaciones de compra y los recibos por honorarios se
                # revierten; el resto de comprobantes se dan de baja.
                move.l10n_pe_rce_status = (
                    '3' if doc_code in RCE_REVERSIBLE_DOC_TYPES else '2')
            else:
                move.l10n_pe_rce_status = '1'
