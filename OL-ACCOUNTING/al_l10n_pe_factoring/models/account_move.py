# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

from .factoring import LINE_STATES


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_factoring_line_ids = fields.One2many(
        'l10n_pe.factoring.line', 'move_id', string='Cesiones a factoring', readonly=True)
    l10n_pe_factoring_id = fields.Many2one(
        'l10n_pe.factoring', string='Operación de factoring', compute='_compute_l10n_pe_factoring',
        store=True, index='btree_not_null')
    l10n_pe_factoring_state = fields.Selection(
        [state for state in LINE_STATES if state[0] != 'cancelled'], string='Factoring',
        compute='_compute_l10n_pe_factoring', store=True,
        help='Estado de la factura en su última operación de factoring.')
    l10n_pe_factor_id = fields.Many2one(
        related='l10n_pe_factoring_id.factor_id', string='Factor')
    l10n_pe_factoring_modality = fields.Selection(
        related='l10n_pe_factoring_id.modality', string='Modalidad')

    @api.depends('l10n_pe_factoring_line_ids.state')
    def _compute_l10n_pe_factoring(self):
        for move in self:
            line = move.l10n_pe_factoring_line_ids.filtered(
                lambda l: l.state != 'cancelled').sorted('id')[-1:]
            move.l10n_pe_factoring_id = line.factoring_id
            move.l10n_pe_factoring_state = line.state or False

    def action_l10n_pe_factoring_create(self):
        """«Ceder a factoring» desde la lista de facturas: operación en borrador
        con las facturas elegidas, para completar el factor y la modalidad."""
        invoices = self.filtered(lambda m: m.move_type == 'out_invoice')
        if not invoices:
            raise UserError(self.env._('Seleccione facturas de cliente.'))
        invalid = invoices.filtered(lambda m: m.state != 'posted' or m.currency_id.is_zero(m.amount_residual))
        if invalid:
            raise UserError(self.env._('Estas facturas no están publicadas o ya están pagadas: %s',
                                       ', '.join(invalid.mapped('name'))))
        if len(invoices.company_id) > 1 or len(invoices.currency_id) > 1:
            raise UserError(self.env._('Las facturas de una operación deben ser de la misma compañía y moneda.'))
        operation = self.env['l10n_pe.factoring'].with_company(invoices.company_id).create({
            'company_id': invoices.company_id.id,
            'currency_id': invoices.currency_id.id,
            'line_ids': [(0, 0, {'move_id': invoice.id, 'nominal_amount': invoice.amount_residual,
                                 'due_date': invoice.invoice_date_due}) for invoice in invoices],
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'l10n_pe.factoring',
            'res_id': operation.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_l10n_pe_open_factoring(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'l10n_pe.factoring',
            'res_id': self.l10n_pe_factoring_id.id,
            'view_mode': 'form',
        }


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    l10n_pe_factoring_line_id = fields.Many2one(
        'l10n_pe.factoring.line', string='Factura cedida', index='btree_not_null', copy=False,
        check_company=True)
