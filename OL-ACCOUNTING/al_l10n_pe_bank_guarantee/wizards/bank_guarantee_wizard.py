# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError


class L10nPeBankGuaranteeWizard(models.TransientModel):
    _name = 'l10n_pe.bank.guarantee.wizard'
    _description = 'Renovar o ejecutar una carta fianza'
    _check_company_auto = True

    guarantee_id = fields.Many2one('l10n_pe.bank.guarantee', string='Carta fianza', required=True,
                                   check_company=True)
    company_id = fields.Many2one(related='guarantee_id.company_id')
    currency_id = fields.Many2one(related='guarantee_id.currency_id')
    direction = fields.Selection(related='guarantee_id.direction')
    operation = fields.Selection([('renew', 'Renovar'), ('execute', 'Ejecutar')], required=True, default='renew')
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    date_end = fields.Date(string='Nuevo vencimiento', compute='_compute_defaults', store=True, readonly=False)
    amount = fields.Monetary(string='Importe', compute='_compute_defaults', store=True, readonly=False)
    commission = fields.Monetary(string='Comisión', help='Vacía: se calcula con la tasa de la carta fianza.')
    journal_id = fields.Many2one('account.journal', string='Banco', check_company=True,
                                 domain="[('type', '=', 'bank')]", compute='_compute_defaults', store=True,
                                 readonly=False)
    account_id = fields.Many2one(
        'account.account', string='Contrapartida', check_company=True,
        help='Emitida: gasto o cuenta por cobrar con la que se reconoce lo pagado por el banco. '
             'Recibida: la deuda del afianzado (p. ej. el anticipo no devuelto) o un ingreso.')

    @api.depends('guarantee_id', 'operation')
    def _compute_defaults(self):
        for wizard in self:
            guarantee = wizard.guarantee_id
            wizard.amount = guarantee.amount
            wizard.journal_id = guarantee.journal_id
            if guarantee.date_end:
                wizard.date_end = guarantee.date_end + relativedelta(
                    days=(guarantee.date_end - guarantee.date_issue).days)

    def action_confirm(self):
        self.ensure_one()
        guarantee = self.guarantee_id
        if self.operation == 'renew':
            new = guarantee._l10n_pe_renew(self.date_end, amount=self.amount,
                                           commission=self.commission or None, date=min(self.date, guarantee.date_end))
            return {'type': 'ir.actions.act_window', 'res_model': new._name, 'res_id': new.id, 'view_mode': 'form'}
        if not (self.journal_id and self.account_id):
            raise UserError(self.env._('Indique el banco y la contrapartida.'))
        guarantee._l10n_pe_execute(self.date, self.amount, self.journal_id, self.account_id)
        return {'type': 'ir.actions.act_window_close'}
