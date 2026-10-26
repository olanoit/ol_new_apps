# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain

from ..models.treasury_payment_plan import OPEN_STATES


class L10nPeTreasuryPaymentPlanPropose(models.TransientModel):
    _name = 'l10n_pe.treasury.payment.plan.propose'
    _description = 'Proponer documentos a pagar'
    _check_company_auto = True

    plan_id = fields.Many2one('l10n_pe.treasury.payment.plan', string='Programación', required=True,
                              check_company=True)
    company_id = fields.Many2one(related='plan_id.company_id')
    date_due = fields.Date(string='Vencidos hasta', required=True, default=fields.Date.context_today,
                           help='Incluye los documentos que vencen hasta esta fecha (también los ya vencidos).')
    date_from = fields.Date(string='Vencidos desde', help='Vacío: también los vencidos hace mucho.')
    partner_ids = fields.Many2many('res.partner', string='Proveedores', help='Vacío: todos.')
    exclude_partner_ids = fields.Many2many('res.partner', 'l10n_pe_treasury_propose_exclude_rel',
                                           string='Excepto', help='Proveedores que no se proponen.')
    min_amount = fields.Float(string='Saldo desde', help='No propone documentos con un saldo menor.')
    include_no_maturity = fields.Boolean(string='Incluir sin vencimiento')

    def _l10n_pe_domain(self):
        self.ensure_one()
        plan = self.plan_id
        company = plan.company_id
        planned = self.env['l10n_pe.treasury.payment.plan.line'].search([
            ('plan_id.state', 'in', OPEN_STATES), ('payment_id', '=', False)]).move_line_id
        currencies = plan.currency_id | company.currency_id
        domain = [
            *self.env['account.move.line']._check_company_domain(company),
            ('account_id.account_type', '=', 'liability_payable'),
            ('parent_state', '=', 'posted'),
            ('reconciled', '=', False),
            ('amount_residual', '<', 0),
            ('id', 'not in', planned.ids + plan.line_ids.move_line_id.ids),
            ('currency_id', 'in', currencies.ids),
        ]
        if plan.currency_id != company.currency_id:
            # Desde un banco en dólares se pagan los documentos en dólares.
            domain.append(('currency_id', '=', plan.currency_id.id))
        maturity = Domain('date_maturity', '<=', self.date_due)
        if self.date_from:
            maturity &= Domain('date_maturity', '>=', self.date_from)
        if self.include_no_maturity:
            maturity |= Domain('date_maturity', '=', False)
        domain = Domain.AND([domain, maturity])
        if self.partner_ids:
            domain &= Domain('partner_id', 'in', self.partner_ids.ids)
        if self.exclude_partner_ids:
            domain &= Domain('partner_id', 'not in', self.exclude_partner_ids.ids)
        return domain

    def action_propose(self):
        self.ensure_one()
        lines = self.env['account.move.line'].search(self._l10n_pe_domain(), order='partner_id, date_maturity, id')
        PlanLine = self.env['l10n_pe.treasury.payment.plan.line']
        vals_list = []
        for aml in lines:
            residual = PlanLine.new({'plan_id': self.plan_id.id})._l10n_pe_residual(aml)
            if self.min_amount and residual < self.min_amount:
                continue
            vals_list.append({'plan_id': self.plan_id.id, 'move_line_id': aml.id, 'amount': residual})
        if not vals_list:
            raise UserError(self.env._('No hay documentos por pagar con esos criterios.'))
        PlanLine.create(vals_list)
        return {'type': 'ir.actions.act_window_close'}
