# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

from .factoring import LINE_STATES

#: Retención del IGV que aplica un cliente agente de retención (R.S. 037-2002/SUNAT)
#: sobre comprobantes de más de S/ 700.
RETENTION_RATE = 0.03
RETENTION_MIN_AMOUNT = 700.0


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

    def _l10n_pe_factoring_net_pending(self):
        """Monto neto pendiente de pago (DU 013-2020, art. 6; R.S. 193-2020/SUNAT):
        el saldo de la factura sin la detracción, que el cliente deposita en el
        Banco de la Nación, ni la retención del IGV si el cliente es agente de
        retención. Usa los datos de los módulos de detracciones y de consulta
        RUC de la suite cuando están instalados; es una propuesta editable."""
        self.ensure_one()
        company = self.company_id
        to_invoice = lambda amount: company.currency_id._convert(
            amount, self.currency_id, company, self.invoice_date or self.date or fields.Date.context_today(self))
        deduction = 0.0
        if 'l10n_pe_detraction_applies' in self._fields and self.l10n_pe_detraction_applies:
            deduction += to_invoice(self.l10n_pe_detraction_amount)
        elif (getattr(self.commercial_partner_id, 'is_retention_agent', False)
              and not self.currency_id.is_zero(self.amount_tax)
              and company.currency_id.compare_amounts(abs(self.amount_total_signed), RETENTION_MIN_AMOUNT) > 0):
            deduction += self.currency_id.round(self.amount_total * RETENTION_RATE)
        net = self.amount_total - deduction
        return max(0.0, min(self.amount_residual, self.currency_id.round(net)))

    def action_register_payment(self):
        # Con recurso la factura cedida sigue pendiente, pero la cobra el
        # factor: su cobro se registra desde la operación («Cobro del factor»),
        # que cancela a la vez la obligación con el factor.
        assigned = self.filtered(lambda m: m.l10n_pe_factoring_state == 'assigned')
        if assigned:
            raise UserError(self.env._(
                'Estas facturas están cedidas a factoring y las cobra el factor: %(invoices)s. '
                'Registre el cobro desde la operación (Cobro del factor) o, si el cliente no '
                'pagó, la recompra.', invoices=', '.join(
                    '%s (%s)' % (m.name, m.l10n_pe_factoring_id.name) for m in assigned)))
        return super().action_register_payment()

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
            'line_ids': [(0, 0, {'move_id': invoice.id, 'nominal_amount': invoice._l10n_pe_factoring_net_pending(),
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
