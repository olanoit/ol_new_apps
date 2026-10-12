# -*- coding: utf-8 -*-
"""Retención de renta de 4.ª categoría en los recibos por honorarios.

El agente de retención retiene el 8 % del importe total del recibo por
honorarios (documento 02) cuando paga o acredita la renta, salvo que el
recibo no supere el tope (S/ 1 500) o que el prestador le haya entregado la
constancia de suspensión del Formulario Virtual 1609. La retención se
registra en el propio recibo con el impuesto de 4.ª de la compañía: la cuenta
por pagar queda por el neto y la retención en la 40172; la PLAME la declara
en el periodo del pago (ver el reporte mensual).
"""
from odoo import api, fields, models

RECEIPT_CODE = '02'
SYNC_TRIGGERS = {'partner_id', 'invoice_date', 'date', 'l10n_latam_document_type_id',
                 'invoice_line_ids', 'line_ids', 'currency_id', 'company_id'}
STATUSES = [
    ('withheld', 'Retenido'),
    ('suspended', 'Suspendido (constancia 1609)'),
    ('under_threshold', 'No supera el tope'),
    ('not_agent', 'La compañía no es agente de retención'),
]


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_fourth_category_receipt = fields.Boolean(
        string='Recibo por honorarios', compute='_compute_fourth_category_receipt', store=True)
    l10n_pe_fourth_category_status = fields.Selection(
        STATUSES, string='Estado de la retención de 4.ª', compute='_compute_fourth_category',
        store=True,
        help='Por qué se retiene o no el impuesto a la renta de 4.ª categoría en este recibo.')
    l10n_pe_fourth_category_suspension_id = fields.Many2one(
        'l10n_pe.fourth.category.suspension', string='Constancia de suspensión',
        compute='_compute_fourth_category', store=True, check_company=True)
    l10n_pe_fourth_category_amount = fields.Monetary(
        string='Importe retenido de 4.ª', compute='_compute_fourth_category_amount', store=True,
        currency_field='company_currency_id',
        help='Impuesto a la renta de 4.ª categoría retenido, en la moneda de la compañía.')

    @api.depends('move_type', 'l10n_latam_document_type_id.code', 'country_code')
    def _compute_fourth_category_receipt(self):
        for move in self:
            move.l10n_pe_fourth_category_receipt = (
                move.move_type == 'in_invoice' and move.country_code == 'PE'
                and move.l10n_latam_document_type_id.code == RECEIPT_CODE)

    # Solo los datos del propio recibo: una constancia registrada o un tope
    # cambiado después no deben reescribir el estado de un recibo publicado
    # (su asiento ya tiene o no la retención). En borrador, la sincronización
    # lo recalcula expresamente.
    @api.depends('l10n_pe_fourth_category_receipt', 'partner_id', 'invoice_date', 'date',
                 'currency_id', 'invoice_line_ids.price_subtotal')
    def _compute_fourth_category(self):
        for move in self:
            status, suspension = move._l10n_pe_fourth_category_evaluate()
            move.l10n_pe_fourth_category_status = status
            move.l10n_pe_fourth_category_suspension_id = suspension

    @api.depends('line_ids.balance', 'line_ids.tax_line_id.l10n_pe_fourth_category')
    def _compute_fourth_category_amount(self):
        for move in self:
            lines = move.line_ids.filtered(lambda l: l.tax_line_id.l10n_pe_fourth_category)
            move.l10n_pe_fourth_category_amount = -sum(lines.mapped('balance'))

    def _l10n_pe_fourth_category_gross(self):
        """Importe total del recibo (honorarios, sin la retención) en la
        moneda de la compañía a la fecha del recibo."""
        self.ensure_one()
        lines = self.invoice_line_ids.filtered(lambda l: l.display_type == 'product')
        total = sum(lines.mapped('price_subtotal'))
        day = self.invoice_date or self.date or fields.Date.context_today(self)
        return self.currency_id._convert(total, self.company_id.currency_id, self.company_id, day)

    def _l10n_pe_fourth_category_evaluate(self):
        """``(estado, constancia)`` de la retención de 4.ª del recibo."""
        self.ensure_one()
        Suspension = self.env['l10n_pe.fourth.category.suspension']
        if not self.l10n_pe_fourth_category_receipt:
            return False, Suspension
        company = self.company_id
        if not company.l10n_pe_fourth_category_agent:
            return 'not_agent', Suspension
        day = self.invoice_date or self.date or fields.Date.context_today(self)
        # sudo: la constancia la consulta quien registra el recibo aunque no
        # administre las suspensiones (solo se lee si hay una vigente).
        suspension = Suspension.sudo()._l10n_pe_find(self.partner_id, day, company)
        if suspension:
            return 'suspended', suspension.sudo(False)
        threshold = company.l10n_pe_fourth_category_threshold
        if company.currency_id.compare_amounts(self._l10n_pe_fourth_category_gross(),
                                               threshold) <= 0:
            return 'under_threshold', Suspension
        return 'withheld', Suspension

    def _l10n_pe_fourth_category_sync(self):
        """Pone o quita el impuesto de retención de 4.ª en las líneas del
        recibo en borrador según la evaluación."""
        for move in self.filtered(lambda m: m.state == 'draft'):
            lines = move.invoice_line_ids.filtered(lambda l: l.display_type == 'product')
            status = move._l10n_pe_fourth_category_evaluate()[0]
            taxes = lines.tax_ids.filtered('l10n_pe_fourth_category')
            if status == 'withheld' and lines:
                tax = move.company_id._l10n_pe_fourth_category_tax()
                for line in lines.filtered(lambda l: tax not in l.tax_ids):
                    line.tax_ids = line.tax_ids - taxes | tax
            elif taxes:
                for line in lines.filtered(lambda l: l.tax_ids & taxes):
                    line.tax_ids = line.tax_ids - taxes
            move._compute_fourth_category()

    @api.onchange('partner_id', 'invoice_date', 'l10n_latam_document_type_id',
                  'invoice_line_ids', 'currency_id')
    def _onchange_fourth_category(self):
        self._l10n_pe_fourth_category_sync()

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        moves.filtered('l10n_pe_fourth_category_receipt')._l10n_pe_fourth_category_sync()
        return moves

    def write(self, vals):
        res = super().write(vals)
        if SYNC_TRIGGERS & set(vals) and not self.env.context.get('l10n_pe_fourth_category_sync'):
            self.filtered('l10n_pe_fourth_category_receipt').with_context(
                l10n_pe_fourth_category_sync=True)._l10n_pe_fourth_category_sync()
        return res

    def _post(self, soft=True):
        self.filtered('l10n_pe_fourth_category_receipt').with_context(
            l10n_pe_fourth_category_sync=True)._l10n_pe_fourth_category_sync()
        return super()._post(soft=soft)

    # ------------------------------------------------------------------
    # Pago (PLAME: la retención se declara en el periodo del pago)
    # ------------------------------------------------------------------
    def _l10n_pe_fourth_category_payment_date(self):
        """Fecha en que el recibo quedó pagado (la última conciliación de su
        cuenta por pagar), o False si aún tiene saldo."""
        self.ensure_one()
        if self.payment_state not in ('paid', 'in_payment'):
            return False
        payable = self.line_ids.filtered(
            lambda l: l.account_id.account_type == 'liability_payable')
        partials = payable.matched_debit_ids | payable.matched_credit_ids
        return max(partials.mapped('max_date')) if partials else False
