import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

#: Formato SUNAT del documento en el kardex (Tabla 10, serie y número).
DOC_TYPE_RE = re.compile(r'^\d{2}$')
SERIE_RE = re.compile(r'^[A-Za-z0-9]{1,20}$')
NUMBER_RE = re.compile(r'^\d{1,20}$')
DOC_FIELDS = ('l10n_pe_kardex_doc_type', 'l10n_pe_kardex_serie', 'l10n_pe_kardex_number')


def split_serie_number(number):
    """``F001-00000123`` → (``F001``, ``00000123``): serie sin guiones; el número
    conserva sus ceros, como en el kardex y el PLE de inventarios."""
    matches = list(re.finditer(r'\d+', number or ''))
    if not matches:
        return '', ''
    last = matches[-1]
    serie = re.sub(r'[^A-Za-z0-9]', '', number[:last.start()])
    folio = last.group()[-20:]
    return serie[-20:], folio if int(folio) else ''


class StockMove(models.Model):
    """Documento del movimiento para el kardex SUNAT (formatos 12.1 y 13.1).

    Se guarda **por movimiento** (no por transferencia): una entrega puede
    facturarse en varias facturas y una devolución lleva su nota de crédito.
    Se llena solo al publicar el comprobante o al validar el movimiento; lo
    que el usuario corrige a mano queda marcado y nunca se sobrescribe.
    """
    _inherit = 'stock.move'

    l10n_pe_kardex_doc_type = fields.Char(
        string='Tipo de documento (kardex)', size=2, copy=False,
        help='Tabla 10 SUNAT: 01 factura, 03 boleta, 07 nota de crédito, 09 guía de remisión…')
    l10n_pe_kardex_serie = fields.Char(string='Serie (kardex)', size=20, copy=False)
    l10n_pe_kardex_number = fields.Char(string='Número (kardex)', size=20, copy=False)
    l10n_pe_kardex_invoice_id = fields.Many2one(
        'account.move', string='Comprobante (kardex)', copy=False, index='btree_not_null')
    l10n_pe_kardex_doc_manual = fields.Boolean(
        string='Documento corregido a mano', copy=False,
        help='El documento lo indicó un usuario: el llenado automático no lo cambia.')

    # ------------------------------------------------------------------
    # Validaciones de formato SUNAT
    # ------------------------------------------------------------------
    @api.constrains(*DOC_FIELDS)
    def _check_l10n_pe_kardex_document(self):
        for move in self:
            doc_type, serie, number = (move[f] for f in DOC_FIELDS)
            if doc_type and not DOC_TYPE_RE.match(doc_type):
                raise ValidationError(_('El tipo de documento del kardex debe tener 2 dígitos '
                                        '(Tabla 10 SUNAT): «%s».', doc_type))
            if serie and not SERIE_RE.match(serie):
                raise ValidationError(_('La serie del kardex admite hasta 20 letras o dígitos, '
                                        'sin espacios ni símbolos: «%s».', serie))
            if number and not (NUMBER_RE.match(number) and int(number) > 0):
                raise ValidationError(_('El número del kardex debe ser un entero positivo de '
                                        'hasta 20 dígitos: «%s».', number))
            if any((doc_type, serie, number)) and not (doc_type and number):
                raise ValidationError(_('Indique al menos el tipo y el número del documento.'))

    def write(self, vals):
        # Lo que escribe un usuario en los campos del documento es una corrección
        # manual; el llenado automático escribe con el contexto propio.
        if (set(DOC_FIELDS) & set(vals) and 'l10n_pe_kardex_doc_manual' not in vals
                and not self.env.context.get('l10n_pe_kardex_auto')):
            vals = dict(vals, l10n_pe_kardex_doc_manual=any(vals.get(f) for f in DOC_FIELDS))
        return super().write(vals)

    # ------------------------------------------------------------------
    # Llenado automático
    # ------------------------------------------------------------------
    def _l10n_pe_kardex_is_return(self):
        """Devolución: vuelve al cliente o al proveedor el sentido del movimiento original."""
        self.ensure_one()
        if self.origin_returned_move_id:
            return True
        if self.sale_line_id:
            return self.location_dest_id.usage != 'customer'
        if self.purchase_line_id:
            return self.location_dest_id.usage == 'supplier'
        return False

    def _l10n_pe_kardex_invoice_types(self):
        self.ensure_one()
        returned = self._l10n_pe_kardex_is_return()
        if self.sale_line_id:
            return ('out_refund',) if returned else ('out_invoice',)
        if self.purchase_line_id:
            return ('in_refund',) if returned else ('in_invoice',)
        return ()

    def _l10n_pe_kardex_pairs(self):
        """{movimiento: comprobante} emparejados en orden por línea de pedido.

        Primera entrega con la primera factura, segunda con la segunda…; así
        una entrega facturada en partes no hereda siempre la primera factura,
        y una devolución toma su nota de crédito y no la factura original.
        """
        pairs = {}
        groups = {}
        # Solo los movimientos que entran o salen del inventario valorizado:
        # en almacenes de 2 o 3 pasos el «pick» (existencias → salida) también
        # lleva la línea de venta y se tomaba por devolución.
        for move in self.filtered(lambda m: m.state == 'done' and (m.is_in or m.is_out)):
            line = move.sale_line_id or move.purchase_line_id
            if not line:
                continue
            key = (line, move._l10n_pe_kardex_invoice_types())
            groups.setdefault(key, self.browse())
            groups[key] |= move
        for (line, types), moves in groups.items():
            all_moves = (line.move_ids.filtered(
                lambda m: m.state == 'done' and (m.is_in or m.is_out)
                and m._l10n_pe_kardex_invoice_types() == types)
                | moves).sorted(lambda m: (m.date, m.id))
            # Una factura revertida por nota de crédito ya no sustenta la
            # entrega: la que vale es la que se emitió después.
            invoices = line.invoice_lines.move_id.filtered(
                lambda inv: inv.state == 'posted' and inv.move_type in types
                and inv.payment_state != 'reversed').sorted('id')
            if not invoices:
                continue
            for index, move in enumerate(all_moves):
                if move in moves:
                    pairs[move] = invoices[min(index, len(invoices) - 1)]
        return pairs

    def _l10n_pe_kardex_pos_invoice(self):
        """Factura o boleta del pedido del punto de venta (si el módulo está instalado).

        Las ventas del PdV no tienen línea de venta: sin esto el kardex las
        informaba con el nombre interno de la transferencia.
        """
        self.ensure_one()
        picking = self.picking_id
        if 'pos_order_id' not in picking._fields or not picking.pos_order_id:
            return self.env['account.move']
        invoice = picking.pos_order_id.account_move
        return invoice if invoice.state == 'posted' else self.env['account.move']

    def _l10n_pe_kardex_fill_documents(self, force=False):
        """Llena el documento de los movimientos hechos.

        - ``force=False``: solo los vacíos.
        - ``force=True``: recalcula también los automáticos.
        En ningún caso toca los corregidos a mano.
        """
        moves = self.filtered(lambda m: m.state == 'done' and not m.l10n_pe_kardex_doc_manual
                              and m.company_id.country_code == 'PE')
        if not force:
            moves = moves.filtered(lambda m: not m.l10n_pe_kardex_doc_type)
        if not moves:
            return self.browse()
        pairs = moves._l10n_pe_kardex_pairs()
        has_guide = 'l10n_latam_document_number' in self.env['stock.picking']._fields
        filled = self.browse()
        for move in moves:
            invoice = pairs.get(move) or move._l10n_pe_kardex_pos_invoice()
            if invoice:
                number = invoice.l10n_latam_document_number or invoice.ref or invoice.name
                doc_type = invoice.l10n_latam_document_type_id.code or '00'
            elif has_guide and move.picking_id.l10n_latam_document_number:
                number, doc_type, invoice = move.picking_id.l10n_latam_document_number, '09', False
            else:
                if force and move.l10n_pe_kardex_doc_type:
                    # El comprobante que tenía se anuló o pasó a borrador: no
                    # puede seguir en el kardex.
                    move.with_context(l10n_pe_kardex_auto=True).write(
                        dict.fromkeys(DOC_FIELDS + ('l10n_pe_kardex_invoice_id',), False))
                    filled |= move
                continue
            serie, folio = split_serie_number(number)
            if not folio:
                continue
            move.with_context(l10n_pe_kardex_auto=True).write({
                'l10n_pe_kardex_doc_type': doc_type.zfill(2)[-2:],
                'l10n_pe_kardex_serie': serie or False,
                'l10n_pe_kardex_number': folio,
                'l10n_pe_kardex_invoice_id': invoice.id if invoice else False,
            })
            filled |= move
        return filled

    def _action_done(self, cancel_backorder=False):
        moves = super()._action_done(cancel_backorder=cancel_backorder)
        # Factura antes que entrega (p. ej. compra facturada al pedir).
        moves._l10n_pe_kardex_fill_documents(force=True)
        return moves

    # ------------------------------------------------------------------
    # Acciones masivas (Inventario ▸ Informes ▸ Movimientos)
    # ------------------------------------------------------------------
    def action_l10n_pe_kardex_fill_empty(self):
        filled = self._l10n_pe_kardex_fill_documents(force=False)
        return self._l10n_pe_kardex_notify(_('%s movimientos completados.', len(filled)))

    def action_l10n_pe_kardex_refresh(self):
        filled = self._l10n_pe_kardex_fill_documents(force=True)
        return self._l10n_pe_kardex_notify(_(
            '%s movimientos recalculados; los corregidos a mano no se tocaron.', len(filled)))

    def action_l10n_pe_kardex_reset_manual(self):
        """Quita la marca manual y vuelve a llenar desde el comprobante."""
        manual = self.filtered('l10n_pe_kardex_doc_manual')
        manual.with_context(l10n_pe_kardex_auto=True).write({
            'l10n_pe_kardex_doc_manual': False, 'l10n_pe_kardex_doc_type': False,
            'l10n_pe_kardex_serie': False, 'l10n_pe_kardex_number': False,
            'l10n_pe_kardex_invoice_id': False})
        manual._l10n_pe_kardex_fill_documents(force=True)
        return self._l10n_pe_kardex_notify(_('%s movimientos vuelven al llenado automático.',
                                             len(manual)))

    def _l10n_pe_kardex_notify(self, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'type': 'success', 'message': message,
                       'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'}},
        }


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        invoices = posted.filtered(lambda m: m.is_invoice(include_receipts=False)
                                   and m.company_id.country_code == 'PE')
        if invoices:
            lines = invoices.invoice_line_ids
            moves = lines.sale_line_ids.move_ids | lines.purchase_line_id.move_ids
            if 'pos_order_ids' in self._fields:
                moves |= invoices.pos_order_ids.picking_ids.move_ids
            # Comprobante antes que la guía: recalcula los automáticos (no los manuales).
            moves._l10n_pe_kardex_fill_documents(force=True)
        return posted


    def button_draft(self):
        res = super().button_draft()
        self._l10n_pe_kardex_refresh_linked_moves()
        return res

    def button_cancel(self):
        res = super().button_cancel()
        self._l10n_pe_kardex_refresh_linked_moves()
        return res

    def _l10n_pe_kardex_refresh_linked_moves(self):
        """Un comprobante que deja de estar publicado no sustenta ya sus
        movimientos: se recalculan (los corregidos a mano no se tocan)."""
        moves = self.env['stock.move'].search([
            ('l10n_pe_kardex_invoice_id', 'in', self.ids),
            ('l10n_pe_kardex_doc_manual', '=', False)])
        moves._l10n_pe_kardex_fill_documents(force=True)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    l10n_pe_kardex_country_code = fields.Char(related='company_id.country_code')

    def action_l10n_pe_kardex_document(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Documento del kardex'),
            'res_model': 'l10n_pe.kardex.document.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_picking_id': self.id},
        }
