# -*- coding: utf-8 -*-
"""Revisión previa de las facturas antes de cederlas: lista todas las que no se
pueden ceder con todos sus motivos, en vez de detenerse en el primer error."""
from odoo import api, fields, models
from odoo.exceptions import UserError

from ..models.factoring import ACTIVE_LINE_STATES


class L10nPeFactoringEligibility(models.TransientModel):
    _name = 'l10n_pe.factoring.eligibility'
    _description = 'Revisión de facturas para factoring'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    contract_id = fields.Many2one(
        'l10n_pe.factoring.contract', string='Contrato', check_company=True,
        help='Opcional: la operación toma el factor y las condiciones del contrato.')
    line_ids = fields.One2many('l10n_pe.factoring.eligibility.line', 'wizard_id', string='Facturas')
    eligible_count = fields.Integer(string='Se pueden ceder', compute='_compute_counts')
    excluded_count = fields.Integer(string='Excluidas', compute='_compute_counts')

    @api.depends('line_ids.eligible')
    def _compute_counts(self):
        for wizard in self:
            wizard.eligible_count = len(wizard.line_ids.filtered('eligible'))
            wizard.excluded_count = len(wizard.line_ids) - wizard.eligible_count

    @api.model
    def _invoice_errors(self, invoice, currency, exclude_line=None):
        """Motivos que impiden ceder ``invoice`` en una operación en ``currency``."""
        errors = []
        name = invoice.name or invoice.display_name
        if invoice.move_type != 'out_invoice' or invoice.state != 'posted':
            return [self.env._('%s no es una factura de cliente publicada.', name)]
        if currency and invoice.currency_id != currency:
            errors.append(self.env._('%(invoice)s está en %(currency)s y la operación en %(operation)s.',
                                     invoice=name, currency=invoice.currency_id.name,
                                     operation=currency.name))
        if invoice.currency_id.is_zero(invoice.amount_residual):
            errors.append(self.env._('%s ya está pagada.', name))
        if invoice.l10n_pe_conformity_state == 'rejected':
            errors.append(self.env._(
                'El cliente dio su disconformidad con %s: no se puede ceder hasta que se subsane '
                '(nota de crédito o débito o nuevo comprobante).', name))
        today = fields.Date.context_today(self)
        if invoice.invoice_date_due and invoice.invoice_date_due < today \
                and not invoice.currency_id.is_zero(invoice.amount_residual):
            errors.append(self.env._('%(invoice)s venció el %(date)s.', invoice=name,
                                     date=invoice.invoice_date_due))
        if invoice.l10n_pe_negotiable_state in ('transferred', 'protested', 'paid'):
            errors.append(self.env._('La factura negociable %s ya está transferida, pagada o protestada.',
                                     name))
        domain = [('move_id', '=', invoice.id), ('state', 'in', ACTIVE_LINE_STATES)]
        if exclude_line and exclude_line.id:
            domain.append(('id', '!=', exclude_line.id))
        other = self.env['l10n_pe.factoring.line'].search(domain, limit=1)
        if other:
            errors.append(self.env._('%(invoice)s ya está en la operación %(operation)s.', invoice=name,
                                     operation=other.factoring_id.name))
        return errors

    @api.model
    def _invoice_warnings(self, invoice):
        warnings = []
        if not invoice.l10n_pe_is_credit:
            warnings.append(self.env._('Al contado: la factura negociable nace de una venta al crédito.'))
        if invoice.l10n_pe_conformity_state == 'pending':
            warnings.append(self.env._('Conformidad pendiente (presunta desde el %s).',
                                       invoice.l10n_pe_presumed_conformity_date or '—'))
        if invoice.l10n_pe_negotiable_state in ('none', 'cancelled', False):
            warnings.append(self.env._('Sin anotación en CAVALI.'))
        return warnings

    @api.model
    def _prepare(self, invoices):
        currency = invoices[:1].currency_id
        return self.create({
            'company_id': invoices[:1].company_id.id,
            'line_ids': [(0, 0, {
                'move_id': invoice.id,
                'errors': '\n'.join(self._invoice_errors(invoice, currency)
                                    + ([self.env._('Es de otra compañía.')]
                                       if invoice.company_id != invoices[:1].company_id else [])),
                'warnings': '\n'.join(self._invoice_warnings(invoice)),
            }) for invoice in invoices],
        })

    def action_create_operation(self):
        """Crea la operación en borrador con las facturas que se pueden ceder."""
        self.ensure_one()
        eligible = self.line_ids.filtered('eligible').move_id
        if not eligible:
            raise UserError(self.env._('Ninguna de las facturas elegidas se puede ceder.'))
        return eligible._l10n_pe_factoring_create_operation(self.contract_id)


class L10nPeFactoringEligibilityLine(models.TransientModel):
    _name = 'l10n_pe.factoring.eligibility.line'
    _description = 'Factura revisada para factoring'

    wizard_id = fields.Many2one('l10n_pe.factoring.eligibility', required=True, ondelete='cascade')
    move_id = fields.Many2one('account.move', string='Factura', required=True)
    partner_id = fields.Many2one(related='move_id.commercial_partner_id', string='Cliente')
    invoice_date_due = fields.Date(related='move_id.invoice_date_due', string='Vencimiento')
    currency_id = fields.Many2one(related='move_id.currency_id')
    amount_residual = fields.Monetary(related='move_id.amount_residual', string='Saldo')
    errors = fields.Text(string='No se puede ceder porque')
    warnings = fields.Text(string='Avisos')
    eligible = fields.Boolean(string='Se puede ceder', compute='_compute_eligible')

    @api.depends('errors')
    def _compute_eligible(self):
        for line in self:
            line.eligible = not line.errors
