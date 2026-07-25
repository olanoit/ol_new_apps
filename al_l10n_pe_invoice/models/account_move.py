# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    sale_id = fields.Many2one('sale.order', string='Orden de venta')
    is_credit = fields.Boolean(
        string='Es Crédito', compute='_compute_is_credit', store=True)

    @api.depends('invoice_payment_term_id')
    def _compute_is_credit(self):
        for move in self:
            move.is_credit = bool(
                move.invoice_payment_term_id
                and move.invoice_payment_term_id.line_ids)

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref(
            'al_l10n_pe_invoice.report_cpe_invoice_a4'
        ).report_action(self.id)

    # ------------------------------------------------------------------
    # Datos auxiliares para las plantillas
    # El QR y el monto en letras NO se recalculan aquí: los provee el core
    # (l10n_pe_edi) vía _l10n_pe_edi_get_extra_report_values(), que extrae
    # el QR oficial (con hash de la firma) del XML firmado, y
    # _l10n_pe_edi_amount_to_text().
    # ------------------------------------------------------------------
    def _get_report_base_filename_custom(self):
        name_custom = self._get_move_display_name()
        name_client = self.partner_id.parent_id.name or self.partner_id.name
        return f'{name_custom} {name_client}'

    def get_amount_discount(self):
        self.ensure_one()
        amount = sum(self.invoice_line_ids.filtered(
            lambda x: not x.display_type and x.price_total < 0
        ).mapped('price_total'))
        return abs(amount)

    def get_data_dues(self):
        """Cuotas de crédito a mostrar en el reporte: usa el detalle nativo
        de Odoo cuando hay más de una cuota; si solo hay una, muestra el
        saldo pendiente con su fecha de vencimiento."""
        self.ensure_one()
        if self.payment_term_details:
            return [{
                'nro': idx + 1,
                'amount': due.get('amount'),
                'date': due.get('date'),
            } for idx, due in enumerate(self.payment_term_details)]
        return [{
            'nro': 1,
            'amount': self.amount_residual,
            'date': self.invoice_date_due.strftime('%d/%m/%Y') if self.invoice_date_due else '',
        }]

    def _l10n_pe_get_national_bank_account_number(self):
        """Cuenta del Banco de la Nación de la compañía, para el bloque de
        detracción del reporte (mismo criterio que usa el core en
        ``_l10n_pe_edi_get_spot``)."""
        self.ensure_one()
        national_bank = self.env.ref(
            'l10n_pe.peruvian_national_bank', raise_if_not_found=False)
        if not national_bank:
            return ''
        account = self.company_id.bank_ids.filtered(
            lambda b: b.bank_id == national_bank)
        return account[0].acc_number if account else ''

    # ------------------------------------------------------------------
    # Detalle tributario SUNAT — campos STORED (split obligatorio Odoo 18+:
    # un método compute no puede mezclar store=True con store=False)
    # ------------------------------------------------------------------
    l10n_pe_edi_amount_exonerated = fields.Monetary(
        string='Monto Exonerado', compute='_compute_tax_amounts_stored', store=True, compute_sudo=False)
    l10n_pe_edi_amount_igv = fields.Monetary(
        string='IGV', compute='_compute_tax_amounts_stored', store=True, compute_sudo=False)
    l10n_pe_edi_amount_base = fields.Monetary(
        string='Base Imponible', compute='_compute_tax_amounts_stored', store=True, compute_sudo=False)
    l10n_pe_edi_amount_ivap = fields.Monetary(
        string='IVAP', compute='_compute_tax_amounts_stored', store=True, compute_sudo=False)
    l10n_pe_edi_amount_isc = fields.Monetary(
        string='ISC', compute='_compute_tax_amounts_stored', store=True, compute_sudo=False)
    l10n_pe_edi_amount_unaffected = fields.Monetary(
        string='Operaciones Inafectas', compute='_compute_tax_amounts_stored', store=True, compute_sudo=False)
    l10n_pe_edi_amount_others = fields.Monetary(
        string='Otros Tributos', compute='_compute_tax_amounts_stored', store=True, compute_sudo=False)
    l10n_pe_edi_amount_icbper = fields.Monetary(
        string='ICBPER', compute='_compute_tax_amounts_stored', store=True, compute_sudo=False)

    # Campo NO stored — retención, con su propio método compute
    l10n_pe_edi_amount_retention = fields.Monetary(
        string='Retención', compute='_compute_tax_amounts_non_stored', store=False, compute_sudo=False)

    _TAX_MOVE_TYPES = ('out_invoice', 'in_invoice', 'out_refund', 'in_refund')

    @api.depends('line_ids.tax_ids', 'line_ids.price_subtotal', 'amount_total', 'currency_id')
    def _compute_tax_amounts_stored(self):
        for move in self:
            if move.move_type not in move._TAX_MOVE_TYPES:
                move._reset_tax_amounts_stored()
                continue
            try:
                tax_amounts = move._compute_tax_breakdown(move._prepare_edi_tax_details())
                move._update_stored_tax_amounts(tax_amounts)
            except Exception as e:
                move._handle_tax_computation_error(e, stored_only=True)

    @api.depends('line_ids.tax_ids', 'line_ids.price_subtotal', 'amount_total', 'currency_id')
    def _compute_tax_amounts_non_stored(self):
        for move in self:
            if move.move_type not in move._TAX_MOVE_TYPES:
                move.l10n_pe_edi_amount_retention = 0.0
                continue
            try:
                tax_amounts = move._compute_tax_breakdown(move._prepare_edi_tax_details())
                move.l10n_pe_edi_amount_retention = round(tax_amounts['retention'], 2)
            except Exception as e:
                _logger.error('Error calculando retenciones para %s: %s', move.name, e)
                move.l10n_pe_edi_amount_retention = 0.0

    def _update_stored_tax_amounts(self, tax_amounts):
        self.update({
            'l10n_pe_edi_amount_base': round(tax_amounts['base'], 2),
            'l10n_pe_edi_amount_igv': round(tax_amounts['igv'], 2),
            'l10n_pe_edi_amount_ivap': round(tax_amounts['ivap'], 2),
            'l10n_pe_edi_amount_isc': round(tax_amounts['isc'], 2),
            'l10n_pe_edi_amount_icbper': round(tax_amounts['icbper'], 2),
            'l10n_pe_edi_amount_unaffected': round(tax_amounts['unaffected'], 2),
            'l10n_pe_edi_amount_exonerated': round(tax_amounts['exonerated'], 2),
            'l10n_pe_edi_amount_others': round(tax_amounts['others'], 2),
        })

    def _reset_tax_amounts_stored(self):
        self.update({
            'l10n_pe_edi_amount_base': 0.0,
            'l10n_pe_edi_amount_igv': 0.0,
            'l10n_pe_edi_amount_ivap': 0.0,
            'l10n_pe_edi_amount_isc': 0.0,
            'l10n_pe_edi_amount_icbper': 0.0,
            'l10n_pe_edi_amount_unaffected': 0.0,
            'l10n_pe_edi_amount_exonerated': 0.0,
            'l10n_pe_edi_amount_others': 0.0,
        })

    def _compute_tax_breakdown(self, tax_details):
        """Clasifica los impuestos del detalle EDI nativo según los
        códigos tributarios SUNAT (catálogo 05/07/08/09/etc.)."""
        tax_amounts = {
            'base': 0.0, 'igv': 0.0, 'ivap': 0.0, 'isc': 0.0, 'icbper': 0.0,
            'unaffected': 0.0, 'exonerated': 0.0, 'others': 0.0, 'retention': 0.0,
        }
        for tax_detail in tax_details.get('tax_details', {}).values():
            tax = tax_detail.get('grouping_key', self.env['account.tax'])
            tax_code = tax.l10n_pe_edi_tax_code if tax else ''
            # Claves *_currency: moneda del documento (igual a la de compañía
            # en facturas PEN). Con 'tax_amount'/'base_amount' (moneda de
            # compañía) una factura USD mostraba el desglose en soles junto a
            # un importe total en dólares.
            amount = tax_detail.get('tax_amount_currency', 0.0)
            base = tax_detail.get('base_amount_currency', 0.0)

            if tax_code == '1000':  # IGV (18%)
                tax_amounts['igv'] += amount
                tax_amounts['base'] += base
            elif tax_code == '1016':  # IVAP
                tax_amounts['ivap'] += amount
            elif tax_code == '2000':  # ISC
                tax_amounts['isc'] += amount
            elif tax_code == '7152':  # ICBPER
                tax_amounts['icbper'] += amount
            elif tax_code == '9996':  # Otros tributos
                tax_amounts['others'] += base
            elif tax_code == '9997':  # Exonerado
                tax_amounts['exonerated'] += base
            elif tax_code == '9998':  # Inafecto
                tax_amounts['unaffected'] += base
            elif tax_code == 'RET':  # Retenciones
                tax_amounts['retention'] += abs(amount)

        # Líneas sin impuesto se consideran exoneradas según SUNAT
        tax_amounts['exonerated'] += sum(self.invoice_line_ids.filtered(
            lambda l: not l.tax_ids).mapped('price_subtotal'))
        return tax_amounts

    def _handle_tax_computation_error(self, error, stored_only=False):
        _logger.error('Error calculando impuestos para %s: %s', self.name, error)
        self._reset_tax_amounts_stored()
        if not stored_only:
            self.l10n_pe_edi_amount_retention = 0.0
        if not self.env.context.get('suppress_tax_warnings'):
            raise UserError(self.env._(
                'Error calculando impuestos para el documento %(name)s:\n%(error)s',
                name=self.name, error=str(error)))
