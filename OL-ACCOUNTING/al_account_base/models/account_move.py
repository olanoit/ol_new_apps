# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Glosa peruana (descripción del asiento para el PLE / libros).
    l10n_pe_gloss = fields.Char(string='Glosa', copy=False)

    # Comprobante que modifica una nota de crédito o débito cuando el original
    # no está en Odoo (p. ej. una factura de antes de la implementación): el
    # PLE (8.4 y 14.4) y el SIRE lo informan en las columnas del documento
    # modificado. Con el original enlazado, mandan los datos de ese original.
    l10n_pe_origin_document_type_id = fields.Many2one(
        'l10n_latam.document.type', string='Tipo del comprobante modificado', copy=False,
        domain="[('country_id.code', '=', 'PE')]")
    l10n_pe_origin_serie = fields.Char(string='Serie del comprobante modificado', copy=False)
    l10n_pe_origin_number = fields.Char(string='Número del comprobante modificado', copy=False)
    l10n_pe_origin_date = fields.Date(string='Fecha del comprobante modificado', copy=False)
    l10n_pe_is_note = fields.Boolean(string='Es nota', compute='_compute_l10n_pe_note_origin')
    l10n_pe_origin_linked = fields.Boolean(
        string='Original enlazado', compute='_compute_l10n_pe_note_origin')

    @api.depends('move_type', 'l10n_latam_document_type_id', 'reversed_entry_id')
    def _compute_l10n_pe_note_origin(self):
        for move in self:
            document_type = move.l10n_latam_document_type_id
            move.l10n_pe_is_note = move.move_type in ('out_refund', 'in_refund') or \
                document_type.internal_type in ('credit_note', 'debit_note')
            move.l10n_pe_origin_linked = bool(move._l10n_pe_origin_move())

    def _l10n_pe_origin_move(self):
        """Comprobante de Odoo que modifica la nota (o vacío)."""
        self.ensure_one()
        origin = self.reversed_entry_id
        if not origin and 'debit_origin_id' in self._fields:
            origin = self.debit_origin_id
        return origin

    def _l10n_pe_customs_total(self):
        """Total de una DAM o DSI (tipos 50-54): base + IGV/IPM + otros.

        La factura de Odoo solo debe a la Aduana derechos e impuestos; el
        valor en aduana va contra una cuenta puente (línea base con IGV y su
        compensación sin impuesto), así que ``amount_total`` no es el total
        del comprobante. El ad valorem ya está dentro de la base; los «otros
        derechos» (si el registro de la DUA los marca) se suman aparte."""
        self.ensure_one()
        lines = self.invoice_line_ids.filtered(lambda line: line.display_type == 'product')
        base = sum(abs(line.balance) for line in lines if line.tax_ids)
        if 'l10n_pe_dua_line_kind' in lines._fields:
            base += sum(abs(line.balance) for line in lines
                        if line.l10n_pe_dua_line_kind == 'other' and not line.tax_ids)
        return base + sum(abs(line.balance) for line in self.line_ids if line.tax_line_id)

    def _l10n_pe_modified_document(self):
        """Datos del comprobante que modifica la nota, para el PLE y el SIRE:
        ``{'date', 'type', 'serie', 'number', 'move'}``. Del original enlazado
        si existe; si no, de los campos escritos en la nota. Vacío si no hay
        ninguno de los dos."""
        self.ensure_one()
        origin = self._l10n_pe_origin_move()
        if origin:
            name = (origin.l10n_latam_document_number or origin.name or '').replace(' ', '')
            serie, _sep, number = name.partition('-') if '-' in name else ('', '', name)
            return {
                'date': origin.invoice_date,
                'type': origin.l10n_latam_document_type_id.code or '',
                'serie': serie,
                'number': number,
                'move': origin,
            }
        if self.l10n_pe_origin_document_type_id and self.l10n_pe_origin_number:
            return {
                'date': self.l10n_pe_origin_date,
                'type': self.l10n_pe_origin_document_type_id.code or '',
                'serie': (self.l10n_pe_origin_serie or '').strip().upper(),
                'number': self.l10n_pe_origin_number.strip(),
                'move': self.browse(),
            }
        return {}

    def l10n_pe_is_pe(self):
        """Es un comprobante de una compañía peruana."""
        self.ensure_one()
        return self.country_code == 'PE'

    def _l10n_pe_customer_retention(self):
        """IGV que retendrá el cliente agente de retención sobre esta venta, en
        la moneda del comprobante (R.S. 037-2002/SUNAT): el 3 % del total si
        el comprobante supera S/ 700. No se retiene si la operación está
        sujeta a detracción, si no tiene IGV, si el cliente no es agente o si
        la compañía es agente de retención o buen contribuyente (art. 5).

        El «Monto neto pendiente de pago» de la factura no incluye esta
        retención (R.S. 193-2020/SUNAT, numeral 2.1): lo usan el comprobante
        impreso, las cuotas del XML y el factoring. Los datos del padrón, de
        la detracción y de la tasa vienen de otros módulos de la suite si
        están instalados (sin ellos no hay retención que estimar)."""
        self.ensure_one()
        if self.move_type != 'out_invoice' or self.state == 'cancel':
            return 0.0
        doc_type = 'l10n_latam_document_type_id' in self._fields and \
            self.l10n_latam_document_type_id.code
        if doc_type and doc_type not in ('01', '08'):
            return 0.0  # facturas y notas de débito
        company = self.company_id
        if not getattr(self.commercial_partner_id, 'is_retention_agent', False):
            return 0.0
        if getattr(company, 'l10n_pe_retention_agent', False) \
                or getattr(company.partner_id, 'is_retention_agent', False) \
                or getattr(company.partner_id, 'is_good_taxpayer', False):
            return 0.0
        if self.currency_id.is_zero(self.amount_tax):
            return 0.0
        if 'l10n_pe_detraction_applies' in self._fields and self.l10n_pe_detraction_applies:
            return 0.0
        if hasattr(self, '_l10n_pe_edi_get_spot') and self._l10n_pe_edi_get_spot():
            return 0.0
        minimum = getattr(company, 'l10n_pe_retention_min_amount', 0.0) or 700.0
        if company.currency_id.compare_amounts(abs(self.amount_total_signed), minimum) <= 0:
            return 0.0
        rate = getattr(company, 'l10n_pe_retention_rate', 0.0) or 3.0
        return self.currency_id.round(abs(self.amount_total) * rate / 100.0)

    def _l10n_pe_retention_split(self, amounts):
        """Reparte la retención del cliente entre las cuotas (en proporción a
        cada una; el redondeo cae en la última) y devuelve las cuotas netas.
        El comprobante impreso y el XML usan este mismo reparto."""
        self.ensure_one()
        retention = self._l10n_pe_customer_retention()
        total = sum(amounts)
        if not retention or not amounts or self.currency_id.is_zero(total):
            return list(amounts)
        shares = [self.currency_id.round(retention * amount / total) for amount in amounts[:-1]]
        shares.append(self.currency_id.round(retention - sum(shares)))
        return [self.currency_id.round(amount - share) for amount, share in zip(amounts, shares)]
