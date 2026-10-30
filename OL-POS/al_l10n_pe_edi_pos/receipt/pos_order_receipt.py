# -*- coding: utf-8 -*-
from odoo import models

# Mismas etiquetas que el TPV (static/src/overrides/pos_order.js).
PE_DOC_LABELS = {
    '01': 'FACTURA ELECTRÓNICA',
    '03': 'BOLETA DE VENTA ELECTRÓNICA',
    '07': 'NOTA DE CRÉDITO ELECTRÓNICA',
    '08': 'NOTA DE DÉBITO ELECTRÓNICA',
}
PE_ID_LABELS = {'6': 'RUC', '1': 'DNI', '4': 'C.E.', '7': 'Pasaporte'}


class PosOrderReceipt(models.AbstractModel):
    """Ticket CPE dibujado en el servidor: mismos datos que
    GeneratePrinterData.generateReceiptData del navegador
    (static/src/app/utils/generate_printer_data.js)."""
    _inherit = 'pos.order.receipt'

    def _l10n_pe_receipt_active(self):
        return (self.company_id.country_code == 'PE' and self.config_id.l10n_pe_cpe_enabled
                and self.l10n_pe_doc_type != 'recibo')

    def _l10n_pe_receipt_doc_label(self):
        code = self.account_move.l10n_latam_document_type_id.code
        if code in PE_DOC_LABELS:
            return PE_DOC_LABELS[code]
        return PE_DOC_LABELS['01' if self.l10n_pe_doc_type == 'factura' else '03']

    def _l10n_pe_receipt_line_records(self):
        """Líneas del ticket; otros módulos las filtran como en el TPV."""
        return self.lines

    def _l10n_pe_receipt_lines(self):
        fmt = self._order_receipt_format_currency
        return [{
            'qty': int(line.qty) if float(line.qty).is_integer() else line.qty,
            'name': line.full_product_name or line.product_id.display_name,
            'discount': line.discount or False,
            'note': line.customer_note or False,
            'unit': fmt(line.price_subtotal_incl / line.qty if line.qty else line.price_unit),
            'total': fmt(line.price_subtotal_incl),
        } for line in self._l10n_pe_receipt_line_records()]

    def _l10n_pe_receipt_extra_payments(self):
        """Pagos que no son líneas de pago del TPV: [(nombre, importe)]."""
        return []

    def _l10n_pe_receipt_notes(self):
        return []

    def _l10n_pe_receipt_totals(self, move):
        fmt = self._order_receipt_format_currency
        rows = []

        def add(label, amount):
            if amount:
                rows.append({'label': label, 'amount': fmt(amount)})

        if move.state == 'posted':
            add('Op. gravadas', move.l10n_pe_edi_amount_base)
            add('Op. exoneradas', move.l10n_pe_edi_amount_exonerated)
            add('Op. inafectas', move.l10n_pe_edi_amount_unaffected)
            add('Op. exportación', move.l10n_pe_edi_amount_export)
            add('Op. gratuitas', move.l10n_pe_edi_amount_free)
            add('ISC', move.l10n_pe_edi_amount_isc)
            add('IVAP', move.l10n_pe_edi_amount_ivap)
            add('ICBPER', move.l10n_pe_edi_amount_icbper)
            add('Otros tributos', move.l10n_pe_edi_amount_others)
            rows.append({'label': move.l10n_pe_pos_igv_label or 'IGV', 'amount': fmt(move.l10n_pe_edi_amount_igv)})
            rows.append({'label': 'IMPORTE TOTAL', 'amount': fmt(move.amount_total), 'total': True})
            return rows
        add('Op. gravadas', self.amount_total - self.amount_tax)
        rows.append({'label': 'IGV', 'amount': fmt(self.amount_tax)})
        rows.append({'label': 'IMPORTE TOTAL', 'amount': fmt(self.amount_total), 'total': True})
        return rows

    def order_receipt_generate_data(self, basic_receipt=False):
        data = super().order_receipt_generate_data(basic_receipt)
        if not self._l10n_pe_receipt_active():
            return data
        fmt = self._order_receipt_format_currency
        move = self.account_move
        issued = move.state == 'posted'
        partner = self.partner_id.commercial_partner_id if self.partner_id else self.partner_id
        company = self.company_id
        doc_label = self._l10n_pe_receipt_doc_label()
        payments = [{'name': line.payment_method_id.name, 'amount': fmt(line.amount)}
                    for line in self.payment_ids if line.amount > 0]
        payments += [{'name': name, 'amount': fmt(amount)}
                     for name, amount in self._l10n_pe_receipt_extra_payments()]
        data['conditions']['al_pe_cpe'] = True
        data['extra_data']['al_pe'] = {
            'company_name': company.name,
            'company_vat': company.vat,
            'company_street': company.street or '',
            'company_phone': company.phone or '',
            'issued': issued,
            'doc_label': doc_label,
            'doc_label_lower': doc_label.lower(),
            'doc_number': move.l10n_latam_document_number if issued else '',
            'partner_name': self.partner_id.name or 'CLIENTE VARIOS',
            'partner_vat_label': PE_ID_LABELS.get(partner.l10n_pe_sunat_id_code, 'Doc.'),
            'partner_vat': partner.l10n_pe_sunat_id_value or partner.vat or '',
            'partner_street': self.partner_id.street or '',
            'date': data['extra_data']['formated_date_order'],
            'currency_label': 'DÓLARES AMERICANOS' if self.currency_id.name == 'USD' else 'SOLES',
            'lines': self._l10n_pe_receipt_lines(),
            'totals': self._l10n_pe_receipt_totals(move),
            'words': move.l10n_pe_pos_amount_text if issued else False,
            'payments': payments,
            'change': fmt(abs(self.amount_return)) if self.amount_return else False,
            'cashier': data['extra_data'].get('cashier_name') or False,
            'seller': self.seller_id.name if 'seller_id' in self._fields and self.seller_id else False,
            'notes': self._l10n_pe_receipt_notes(),
            'qr': self._order_receipt_generate_qr_code(move.l10n_pe_pos_qr_str) if move.l10n_pe_pos_qr_str else False,
            'footer': self.config_id.receipt_footer or False,
        }
        return data
