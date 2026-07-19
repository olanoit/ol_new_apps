# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

# Boletas de venta (código 03): sin derecho a crédito fiscal → exceptuadas
EXCLUDED_DOCUMENT_CODES = ('03',)


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_retention_applies = fields.Boolean(
        string='Sujeta a retención de IGV',
        compute='_compute_l10n_pe_retention', store=True,
        help='La compañía es agente de retención y la operación no está '
             'exceptuada (mínimo S/ 700, agente-agente, buen '
             'contribuyente, boleta, detracción).')
    l10n_pe_retention_amount = fields.Monetary(
        string='Retención estimada',
        currency_field='company_currency_id',
        compute='_compute_l10n_pe_retention',
        help='Estimación informativa (tasa sobre el total): la retención '
             'efectiva se calcula en cada pago.')

    @api.depends('move_type', 'partner_id', 'amount_total_signed',
                 'company_id', 'l10n_latam_document_type_id',
                 'invoice_line_ids.product_id',
                 'commercial_partner_id.l10n_pe_retention_agent',
                 'commercial_partner_id.l10n_pe_good_contributor')
    def _compute_l10n_pe_retention(self):
        for move in self:
            company = move.company_id
            applies = (
                company.l10n_pe_retention_agent
                and move.country_code == 'PE'
                and move.move_type == 'in_invoice'
                and abs(move.amount_total_signed)
                > company.l10n_pe_retention_min_amount
                and not move.commercial_partner_id.l10n_pe_retention_agent
                and not move.commercial_partner_id.l10n_pe_good_contributor
                and (move.l10n_latam_document_type_id.code or '01')
                not in EXCLUDED_DOCUMENT_CODES
                # exceptuada si la operación está sujeta a SPOT
                # (campo presente solo con al_l10n_pe_detraction instalado)
                and not getattr(move, 'l10n_pe_detraction_applies', False)
            )
            move.l10n_pe_retention_applies = applies
            move.l10n_pe_retention_amount = (
                company.currency_id.round(
                    abs(move.amount_total_signed)
                    * company.l10n_pe_retention_rate / 100.0)
                if applies else 0.0)

    def _post(self, soft=True):
        """Inyecta el impuesto de retención nativo en las líneas de la
        factura que aplica: no altera el total (los impuestos
        ``is_withholding_tax_on_payment`` se excluyen del cálculo) y hace
        que el wizard de pago proponga la retención del 3% de cada pago."""
        for move in self:
            company = move.company_id
            if (move.country_code != 'PE'
                    or move.move_type != 'in_invoice'
                    or not company.l10n_pe_retention_agent):
                continue
            tax = company.l10n_pe_retention_tax_id
            product_lines = move.invoice_line_ids.filtered(
                lambda l: l.display_type == 'product')
            if move.l10n_pe_retention_applies:
                if not tax:
                    raise UserError(self.env._(
                        'La compañía es agente de retención y la factura '
                        '%(move)s está sujeta a retención, pero falta '
                        'configurar el «Impuesto de retención IGV» en '
                        'Ajustes ▸ Perú.', move=move.display_name))
                missing = product_lines.filtered(
                    lambda l: tax not in l.tax_ids)
                if missing:
                    missing.write({'tax_ids': [(4, tax.id)]})
            elif tax:
                extra = product_lines.filtered(lambda l: tax in l.tax_ids)
                if extra:
                    extra.write({'tax_ids': [(3, tax.id)]})
        return super()._post(soft=soft)
