# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

# Comprobantes que el CRE admite como documento relacionado (01 factura,
# 08 nota de débito, 12 ticket con crédito fiscal; la 07 rebaja y la 20 es
# el propio CRE). Quedan fuera boletas (03), honorarios (02), liquidaciones
# de compra (04), recibos de servicios públicos (14), etc.
ALLOWED_DOCUMENT_CODES = ('01', '08', '12')
# Código SUNAT del IGV en los impuestos de l10n_pe
IGV_TAX_CODE = '1000'


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_retention_eligible = fields.Boolean(
        string='Comprendida en el régimen de retención',
        compute='_compute_l10n_pe_retention', store=True,
        help='La compañía es agente de retención y la operación no está '
             'exceptuada (agente de retención o de percepción, buen '
             'contribuyente, comprobante sin crédito fiscal, detracción, '
             'sin IGV). El monto mínimo se decide al pagar: se retiene si '
             'los comprobantes pagados juntos suman más de S/ 700.')
    l10n_pe_retention_applies = fields.Boolean(
        string='Sujeta a retención de IGV',
        compute='_compute_l10n_pe_retention_applies', store=True,
        help='Comprendida en el régimen y por encima del monto mínimo por sí '
             'sola. Una factura menor también se retiene si se paga junto con '
             'otras y entre todas superan el mínimo.')
    l10n_pe_retention_amount = fields.Monetary(
        string='Retención estimada',
        currency_field='company_currency_id',
        compute='_compute_l10n_pe_retention_amount',
        help='Estimación informativa (tasa sobre el total): la retención '
             'efectiva se calcula en cada pago.')

    def _l10n_pe_retention_has_igv(self):
        """La retención solo alcanza operaciones gravadas con IGV.

        Se reconoce el IGV por su código SUNAT; un impuesto positivo sin
        código (creado a mano) se toma como IGV para no dejar fuera
        configuraciones antiguas.
        """
        self.ensure_one()
        taxes = self.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product'
        ).tax_ids.filtered(lambda t: not t.is_withholding_tax_on_payment)
        return any(
            tax.l10n_pe_edi_tax_code == IGV_TAX_CODE
            or (not tax.l10n_pe_edi_tax_code and tax.amount > 0)
            for tax in taxes)

    @api.depends('move_type', 'partner_id', 'company_id', 'country_code', 'state',
                 'company_id.l10n_pe_retention_agent',
                 'company_id.l10n_pe_retention_tax_id',
                 'l10n_latam_document_type_id',
                 'invoice_line_ids.product_id',
                 'invoice_line_ids.tax_ids',
                 'commercial_partner_id.is_retention_agent',
                 'commercial_partner_id.is_good_taxpayer',
                 'commercial_partner_id.l10n_pe_is_perception_agent')
    def _compute_l10n_pe_retention(self):
        for move in self:
            company = move.company_id
            if move.state == 'posted':
                # Publicada, la decisión ya quedó en sus líneas: el impuesto
                # de retención se inyectó solo si correspondía. Así una
                # actualización del padrón no reescribe facturas antiguas.
                tax = company.l10n_pe_retention_tax_id
                move.l10n_pe_retention_eligible = bool(
                    tax and move.move_type == 'in_invoice'
                    and tax in move.invoice_line_ids.tax_ids)
                continue
            partner = move.commercial_partner_id
            eligible = (
                company.l10n_pe_retention_agent
                and move.country_code == 'PE'
                and move.move_type == 'in_invoice'
                and not partner.is_retention_agent
                and not partner.is_good_taxpayer
                # art. 5 h) R.S. 037-2002/SUNAT
                and not partner.l10n_pe_is_perception_agent
                and (move.l10n_latam_document_type_id.code or '01') in ALLOWED_DOCUMENT_CODES
                and move._l10n_pe_retention_has_igv()
                # exceptuada si la operación está sujeta a SPOT
                # (campo presente solo con al_l10n_pe_detraction instalado)
                and not getattr(move, 'l10n_pe_detraction_applies', False)
            )
            move.l10n_pe_retention_eligible = bool(eligible)

    def _l10n_pe_retention_base(self, date=None):
        """Importe total en soles: en moneda extranjera, al T.C. venta oficial
        (tasa nativa) de ``date`` o de la emisión, no al T.C. de la factura."""
        self.ensure_one()
        company_currency = self.company_id.currency_id
        if not self.currency_id or self.currency_id == company_currency:
            return abs(self.amount_total)
        currency = self.currency_id.with_context(l10n_pe_exchange_rate_type=False)
        return abs(currency._convert(
            self.amount_total, company_currency, self.company_id,
            date or self.invoice_date or self.date or fields.Date.context_today(self)))

    @api.depends('l10n_pe_retention_eligible', 'amount_total', 'currency_id',
                 'invoice_date', 'company_id.l10n_pe_retention_min_amount')
    def _compute_l10n_pe_retention_applies(self):
        for move in self:
            move.l10n_pe_retention_applies = bool(
                move.l10n_pe_retention_eligible
                and move._l10n_pe_retention_base() > move.company_id.l10n_pe_retention_min_amount)

    @api.depends('l10n_pe_retention_applies', 'amount_total', 'currency_id', 'invoice_date',
                 'company_id.l10n_pe_retention_rate')
    def _compute_l10n_pe_retention_amount(self):
        """La estimación va en su propio cómputo.

        Comparte origen con la aplicabilidad pero no su almacenamiento:
        con un único método, leer el importe —que no se almacena—
        arrastraba un recálculo que **escribía** el booleano almacenado.
        Odoo 19 lo avisa, y en tests el aviso es un error.
        """
        for move in self:
            company = move.company_id
            move.l10n_pe_retention_amount = (
                company.currency_id.round(
                    move._l10n_pe_retention_base()
                    * company.l10n_pe_retention_rate / 100.0)
                if move.l10n_pe_retention_applies else 0.0)

    def _post(self, soft=True):
        """Inyecta el impuesto de retención nativo en las líneas de toda
        factura comprendida en el régimen: no altera el total (los impuestos
        ``is_withholding_tax_on_payment`` se excluyen del cálculo) y hace que
        el asistente de pago proponga el 3 % de cada pago. El mínimo de
        S/ 700 lo aplica el asistente sobre los comprobantes pagados juntos."""
        for move in self:
            company = move.company_id
            if (move.country_code != 'PE'
                    or move.move_type != 'in_invoice'
                    or not company.l10n_pe_retention_agent):
                continue
            tax = company.l10n_pe_retention_tax_id
            product_lines = move.invoice_line_ids.filtered(
                lambda l: l.display_type == 'product')
            if move.l10n_pe_retention_eligible:
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
