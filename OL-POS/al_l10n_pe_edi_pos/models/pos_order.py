# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # Elegidos en caja con los selectores de la pantalla de pago; pos.order
    # carga todos sus campos al frontend, así que sincronizan solos.
    l10n_pe_doc_type = fields.Selection(
        selection=[('recibo', 'Recibo'), ('boleta', 'Boleta'),
                   ('factura', 'Factura')],
        string='Tipo de comprobante (PE)', default='boleta', copy=False)
    edi_series_id = fields.Many2one(
        'edi.invoice.series', string='Serie CPE', copy=False,
        help='Serie elegida en caja; la factura generada se numera con '
             'esta serie.')
    l10n_pe_edi_send = fields.Boolean(
        string='Emitir a SUNAT', default=True,
        help='Con «No», el comprobante se genera pero queda retenido: no '
             'se envía a SUNAT desde el TPV; otro usuario libera el envío '
             'desde el backend.')

    def _prepare_invoice_vals(self):
        vals = super()._prepare_invoice_vals()
        # La facturación agrupada al cierre de sesión (len > 1) mezcla
        # órdenes de ambos tipos: se deja el diario estándar del TPV.
        if len(self) != 1 or self.company_id.country_code != 'PE':
            return vals
        config = self.config_id
        if not config.l10n_pe_cpe_enabled:
            # Mismo criterio que el frontend: el flujo CPE exige ambos diarios.
            return vals
        if self.refunded_order_id:
            return self._l10n_pe_prepare_refund_invoice_vals(vals)
        doc_type = self.l10n_pe_doc_type or 'boleta'
        if doc_type == 'recibo':
            # Ticket simple: si aun así se factura, flujo estándar del TPV.
            return vals
        journal = (config.l10n_pe_factura_journal_id if doc_type == 'factura'
                   else config.l10n_pe_boleta_journal_id)
        if doc_type == 'factura':
            vat = (self.partner_id.vat or '').strip()
            is_ruc = self.partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code == '6'
            if not self.partner_id or not is_ruc or len(vat) != 11 or not vat.isdigit():
                raise UserError(_(
                    'La factura electrónica requiere un cliente con RUC (tipo de '
                    'documento RUC y 11 dígitos). Seleccione el cliente o emita una boleta.'))
        vals['journal_id'] = journal.id
        doc_code = '01' if doc_type == 'factura' else '03'
        # El tipo lo decide la caja. Sin esto, l10n_pe toma el primero que
        # admite el cliente: con RUC, la factura (01) aunque se eligiera boleta,
        # y el comprobante salía como «factura» numerada en la serie de boletas.
        vals['l10n_latam_document_type_id'] = self.env.ref(
            'l10n_pe.document_type01' if doc_type == 'factura' else 'l10n_pe.document_type02').id
        serie = self.edi_series_id
        if (serie and serie in journal.edi_series_ids
                and serie.state == 'publish' and serie.edi_type_code == doc_code):
            vals['edi_series_id'] = serie.id
        if not self.l10n_pe_edi_send:
            vals['l10n_pe_edi_hold'] = True
        return vals

    def _l10n_pe_prepare_refund_invoice_vals(self, vals):
        """Devolución: la nota de crédito va al diario del comprobante que
        rectifica (una NC de factura nunca al diario de boletas, sea cual
        sea el tipo marcado en la orden de devolución). La serie la resuelve
        al_account_move_name_sequence desde el comprobante de origen, así
        que no se fuerza la de caja. Sin comprobante de origen (se devolvió
        un «Recibo»), flujo estándar."""
        refunded_move = self.refunded_order_id.account_move
        if len(refunded_move) != 1:
            return vals
        vals['journal_id'] = refunded_move.journal_id.id
        if not self.l10n_pe_edi_send:
            vals['l10n_pe_edi_hold'] = True
        return vals

    def _create_invoice(self, move_vals):
        """El compute de la serie en account.move se dispara al calcularse
        el tipo de documento latam y puede pisar la serie elegida en caja:
        se reafirma tras crear la factura."""
        invoice = super()._create_invoice(move_vals)
        if (len(self) == 1 and self.edi_series_id
                and move_vals.get('edi_series_id')
                and invoice.state == 'draft'):
            invoice.edi_series_id = self.edi_series_id
        return invoice
