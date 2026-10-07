# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_edi_hold = fields.Boolean(
        string='Emisión SUNAT retenida', copy=False,
        help='Marcado desde el TPV («Emitir a SUNAT: No»): el cron de EDI '
             'no envía este comprobante. Desmarque la casilla para liberar '
             'el envío (lo procesa el siguiente cron o el botón Procesar '
             'ahora).')

    # Campos que el recibo del TPV lee tras la sincronización de la orden
    # (read_pos_data devuelve el account.move de la orden facturada).
    l10n_pe_pos_doc_code = fields.Char(
        related='l10n_latam_document_type_id.code',
        string='Código de documento (PE)')
    l10n_pe_pos_amount_text = fields.Char(
        string='Importe en letras (PE)',
        compute='_compute_l10n_pe_pos_amount_text')
    l10n_pe_pos_qr_str = fields.Char(
        string='QR de representación impresa (PE)',
        compute='_compute_l10n_pe_pos_qr_str')
    l10n_pe_pos_igv_label = fields.Char(
        string='Etiqueta del IGV (PE)', compute='_compute_l10n_pe_pos_igv_label',
        help='«IGV (18%)» o «IGV (10.5%)» según la tasa aplicada (MYPE de restaurantes).')

    @api.depends('invoice_line_ids.tax_ids')
    def _compute_l10n_pe_pos_igv_label(self):
        for move in self:
            move.l10n_pe_pos_igv_label = (
                move._l10n_pe_report_igv_label() if move.is_invoice() else 'IGV')

    @api.depends('amount_total', 'currency_id', 'state')
    def _compute_l10n_pe_pos_amount_text(self):
        for move in self:
            if (move.country_code == 'PE' and move.is_invoice()
                    and move.state == 'posted'):
                move.l10n_pe_pos_amount_text = move._l10n_pe_edi_amount_to_text()
            else:
                move.l10n_pe_pos_amount_text = False

    @api.depends('state', 'name', 'amount_total', 'invoice_date',
                 'l10n_pe_edi_amount_igv', 'commercial_partner_id.vat',
                 'commercial_partner_id.l10n_latam_identification_type_id',
                 'l10n_latam_document_number', 'l10n_latam_document_type_id',
                 'company_id.vat')
    def _compute_l10n_pe_pos_qr_str(self):
        """QR de la representación impresa (R.S. 018-2005/SUNAT):
        RUC|tipo|serie|folio|igv|total|fecha|tipoDocCliente|nroDocCliente.
        Disponible desde el asiento publicado, sin esperar el envío del
        XML a SUNAT (el QR oficial con hash llega con el CDR)."""
        for move in self:
            if (move.country_code != 'PE' or not move.is_invoice()
                    or move.state != 'posted'
                    or not move.l10n_latam_document_type_id):
                move.l10n_pe_pos_qr_str = False
                continue
            # Serie/folio desde l10n_latam_document_number ("B001-00000001"):
            # el helper _l10n_pe_edi_get_serie_folio parte del name y
            # arrastra la letra del tipo de documento ("BB001").
            serie, _sep, folio = (move.l10n_latam_document_number or '').partition('-')
            move.l10n_pe_pos_qr_str = '|'.join([
                move.company_id.vat or '',
                move.l10n_latam_document_type_id.code or '',
                serie,
                folio,
                f'{move.l10n_pe_edi_amount_igv:.2f}',
                f'{move.amount_total:.2f}',
                move.invoice_date.strftime('%Y-%m-%d') if move.invoice_date else '',
                # el adquirente es la entidad comercial, como en el XML
                move.commercial_partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code or '',
                move.commercial_partner_id.vat or '',
            ])

    @api.model
    def _load_pos_data_fields(self, config):
        result = super()._load_pos_data_fields(config)
        if self.env.company.country_id.code == 'PE':
            result += [
                'state', 'amount_untaxed', 'amount_tax', 'amount_total',
                'l10n_latam_document_number', 'l10n_pe_pos_doc_code',
                'l10n_pe_pos_amount_text', 'l10n_pe_pos_qr_str',
                'l10n_pe_edi_amount_base', 'l10n_pe_edi_amount_igv',
                'l10n_pe_edi_amount_exonerated',
                'l10n_pe_edi_amount_unaffected',
                'l10n_pe_edi_amount_icbper',
                # el ticket debe cuadrar con el TaxTotal del XML
                'l10n_pe_edi_amount_isc', 'l10n_pe_edi_amount_ivap',
                'l10n_pe_edi_amount_free', 'l10n_pe_edi_amount_export',
                'l10n_pe_edi_amount_others', 'l10n_pe_pos_igv_label',
            ]
        return result
