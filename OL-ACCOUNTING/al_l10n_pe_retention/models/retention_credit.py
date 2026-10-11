# -*- coding: utf-8 -*-
"""Notas de crédito de proveedor descontadas en el siguiente CRE.

Art. 2 de la R.S. 037-2002/SUNAT (texto según la R.S. 050-2002/SUNAT): las
notas de crédito no modifican los importes ya retenidos ni dan lugar a su
devolución por el agente; la retención que les corresponde «podrá deducirse
de la retención que corresponda a operaciones con el mismo proveedor respecto
de las cuales aún no ha operado ésta». Con la opción de la compañía activa,
el siguiente CRE al proveedor (desde un pago o sin pago) retiene menos y cita
la nota de crédito; cada descuento queda registrado con su CRE.
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class L10nPeRetentionCreditDeduction(models.Model):
    _name = 'l10n_pe.retention.credit.deduction'
    _description = 'Nota de crédito descontada en un CRE'
    _order = 'id'
    _check_company_auto = True

    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, readonly=True, index=True,
        default=lambda self: self.env.company)
    credit_note_id = fields.Many2one(
        'account.move', string='Nota de crédito', required=True, readonly=True, index=True,
        ondelete='cascade', check_company=True)
    partner_id = fields.Many2one(
        related='credit_note_id.commercial_partner_id', string='Proveedor', store=True)
    amount = fields.Monetary(
        string='Retención descontada', currency_field='currency_id', readonly=True,
        help='En soles.')
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    payment_id = fields.Many2one(
        'account.payment', string='Pago', readonly=True, index=True, ondelete='cascade',
        check_company=True)
    document_id = fields.Many2one(
        'l10n_pe.retention.document', string='CRE sin pago', readonly=True, index=True,
        ondelete='cascade', check_company=True)
    retention_number = fields.Char(
        string='Comprobante de retención', compute='_compute_retention_number')
    active_deduction = fields.Boolean(
        string='Vigente', compute='_compute_active_deduction',
        help='El CRE que la descontó sigue vigente (no anulado ni revertido).')

    @api.constrains('payment_id', 'document_id')
    def _check_origin(self):
        for deduction in self:
            if bool(deduction.payment_id) == bool(deduction.document_id):
                raise ValidationError(self.env._(
                    'Cada descuento de una nota de crédito pertenece a un solo comprobante de '
                    'retención.'))

    @api.depends('payment_id.l10n_pe_edi_retention_number',
                 'document_id.l10n_pe_edi_retention_number')
    def _compute_retention_number(self):
        for deduction in self:
            cre = deduction.payment_id or deduction.document_id
            deduction.retention_number = cre.l10n_pe_edi_retention_number

    @api.depends('payment_id.state', 'payment_id.l10n_pe_edi_status',
                 'document_id.state', 'document_id.l10n_pe_edi_status')
    def _compute_active_deduction(self):
        for deduction in self:
            cre = deduction.payment_id or deduction.document_id
            alive = (cre.state in ('in_process', 'paid') if deduction.payment_id
                     else cre.state == 'posted')
            deduction.active_deduction = bool(alive and cre.l10n_pe_edi_status != 'cancelled')


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_retention_credit_deduction_ids = fields.One2many(
        'l10n_pe.retention.credit.deduction', 'credit_note_id',
        string='Descuentos en CRE', readonly=True)
    l10n_pe_retention_credit_amount = fields.Monetary(
        string='Retención de la nota de crédito', currency_field='company_currency_id',
        compute='_compute_l10n_pe_retention_credit',
        help='3 % de la nota de crédito, en soles, cuando la factura de origen ya tuvo '
             'comprobante de retención: se puede descontar del siguiente CRE al proveedor '
             '(art. 2 de la R.S. 037-2002/SUNAT).')
    l10n_pe_retention_credit_pending = fields.Monetary(
        string='Retención por descontar', currency_field='company_currency_id',
        compute='_compute_l10n_pe_retention_credit')

    @api.depends('move_type', 'state', 'reversed_entry_id', 'amount_total', 'currency_id',
                 'l10n_pe_retention_credit_deduction_ids.amount',
                 'l10n_pe_retention_credit_deduction_ids.active_deduction',
                 'company_id.l10n_pe_retention_deduct_credit_notes',
                 'company_id.l10n_pe_retention_rate')
    def _compute_l10n_pe_retention_credit(self):
        for move in self:
            amount = 0.0
            origin = move.reversed_entry_id
            company = move.company_id
            if (move.move_type == 'in_refund' and move.state == 'posted' and origin
                    and company.l10n_pe_retention_deduct_credit_notes
                    and origin._l10n_pe_retention_cre_history()):
                amount = company.currency_id.round(
                    move._l10n_pe_retention_base() * company.l10n_pe_retention_rate / 100.0)
            used = sum(move.l10n_pe_retention_credit_deduction_ids.filtered(
                'active_deduction').mapped('amount'))
            move.l10n_pe_retention_credit_amount = amount
            move.l10n_pe_retention_credit_pending = max(
                0.0, company.currency_id.round(amount - used))

    @api.model
    def _l10n_pe_retention_pending_credit_notes(self, company, partner):
        """Notas de crédito del proveedor con retención por descontar, de la
        más antigua a la más reciente."""
        if not company.l10n_pe_retention_deduct_credit_notes:
            return self.browse()
        notes = self.search([
            ('company_id', '=', company.id),
            ('move_type', '=', 'in_refund'),
            ('state', '=', 'posted'),
            ('commercial_partner_id', '=', partner.commercial_partner_id.id),
            ('reversed_entry_id', '!=', False),
        ], order='invoice_date, id')
        return notes.filtered(lambda n: not company.currency_id.is_zero(
            n.l10n_pe_retention_credit_pending))

    @api.model
    def _l10n_pe_retention_plan_deductions(self, company, partner, available):
        """``[(nota, importe)]`` que caben en ``available`` (soles), en orden."""
        plan = []
        currency = company.currency_id
        for note in self._l10n_pe_retention_pending_credit_notes(company, partner):
            if currency.compare_amounts(available, 0.0) <= 0:
                break
            amount = currency.round(min(note.l10n_pe_retention_credit_pending, available))
            plan.append((note, amount))
            available = currency.round(available - amount)
        return plan
