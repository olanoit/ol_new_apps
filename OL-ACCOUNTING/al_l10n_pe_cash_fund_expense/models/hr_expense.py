# -*- coding: utf-8 -*-
"""Gasto pagado con un fondo (requerimiento CREVAL v1.0, CR-14): Odoo lo
registraba como un recibo a nombre del empleado, en el diario de compras y con
la numeración de otro proveedor. Aquí cada gasto es la factura de su
proveedor, con su tipo y número de comprobante, y la rendición del fondo la
paga."""
from collections import defaultdict

from odoo import Command, api, fields, models
from odoo.exceptions import UserError


class HrExpense(models.Model):
    _inherit = 'hr.expense'

    l10n_pe_cash_fund_id = fields.Many2one(
        'l10n_pe.cash.fund', string='Pagado con el fondo', check_company=True,
        domain="[('state', '=', 'open'), ('company_id', '=', company_id)]",
        help='Caja chica o entrega a rendir con la que se pagó. El gasto se registra como la '
             'factura del proveedor y la rendición del fondo la paga.')
    l10n_latam_document_type_id = fields.Many2one(
        'l10n_latam.document.type', string='Tipo de comprobante')
    l10n_pe_document_number = fields.Char(
        string='Número de comprobante', help='Serie y número, por ejemplo F001-00001234.')

    @api.onchange('l10n_pe_cash_fund_id')
    def _onchange_l10n_pe_cash_fund_id(self):
        if self.l10n_pe_cash_fund_id:
            self.payment_mode = 'own_account'

    def action_post(self):
        fund_expenses = self.filtered(
            lambda e: e.l10n_pe_cash_fund_id and e.payment_mode == 'own_account')
        if fund_expenses:
            fund_expenses._check_can_create_move()
            fund_expenses._l10n_pe_post_with_fund()
        others = self - fund_expenses
        if others:
            return super(HrExpense, others).action_post()
        return True

    def _l10n_pe_check_fund_expenses(self):
        for expense in self:
            missing = [label for label, value in (
                (self.env._('proveedor'), expense.vendor_id),
                (self.env._('tipo de comprobante'), expense.l10n_latam_document_type_id),
                (self.env._('número de comprobante'), expense.l10n_pe_document_number))
                if not value]
            if missing:
                raise UserError(self.env._(
                    'El gasto «%(expense)s» se paga con el fondo %(fund)s: le falta %(missing)s.',
                    expense=expense.name, fund=expense.l10n_pe_cash_fund_id.display_name,
                    missing=', '.join(missing)))
            if expense.l10n_pe_cash_fund_id.state != 'open':
                raise UserError(self.env._('El fondo %s no está entregado.',
                                           expense.l10n_pe_cash_fund_id.display_name))
            if expense.currency_id != expense.l10n_pe_cash_fund_id.currency_id:
                raise UserError(self.env._(
                    'El gasto «%s» está en otra moneda que el fondo.', expense.name))

    def _l10n_pe_prepare_bill_vals(self, journal):
        """Factura del proveedor del gasto: su comprobante y la línea del
        gasto con su cuenta, impuestos y analítica."""
        self.ensure_one()
        line = self._prepare_move_lines_vals()
        line['partner_id'] = self.vendor_id.id
        return {
            'name': '/',
            'move_type': 'in_invoice',
            'journal_id': journal.id,
            'partner_id': self.vendor_id.id,
            'invoice_date': self.date,
            'date': self.date,
            'ref': self.name,
            'currency_id': self.currency_id.id,
            'company_id': self.company_id.id,
            'invoice_payment_term_id': False,
            'invoice_date_due': self.date,
            'l10n_latam_document_type_id': self.l10n_latam_document_type_id.id,
            'l10n_latam_document_number': self.l10n_pe_document_number,
            'expense_ids': [Command.set(self.ids)],
            'invoice_line_ids': [Command.create(line)],
            'attachment_ids': [
                Command.create(attachment.copy_data(
                    {'res_model': 'account.move', 'res_id': False, 'raw': attachment.raw})[0])
                for attachment in self.attachment_ids],
        }

    def _l10n_pe_post_with_fund(self):
        self._l10n_pe_check_fund_expenses()
        by_fund = defaultdict(lambda: self.browse())
        for expense in self:
            by_fund[expense.l10n_pe_cash_fund_id] |= expense
        for fund, expenses in by_fund.items():
            company = fund.company_id
            journal = company._l10n_pe_expense_journal()
            if not journal:
                raise UserError(self.env._(
                    'Configure el diario de comprobantes de gastos (un diario de compras con '
                    'documentos) en Ajustes ▸ Perú ▸ Entregas a rendir y caja chica.'))
            # sudo: como en Odoo, quien contabiliza el gasto no siempre
            # registra facturas de proveedor ni rendiciones; solo se crean las
            # de estos gastos.
            bills_sudo = self.env['account.move'].sudo().with_company(company).create([
                expense._l10n_pe_prepare_bill_vals(journal) for expense in expenses])
            bills_sudo.action_post()
            settlement_sudo = self.env['l10n_pe.cash.settlement'].sudo().create({
                'fund_id': fund.id,
                'date': max(expenses.mapped('date')),
                'document_line_ids': [Command.create({'move_id': bill.id})
                                      for bill in bills_sudo],
            })
            settlement_sudo.action_post()
            for expense, bill in zip(expenses, bills_sudo):
                expense.message_post(body=self.env._(
                    'Registrado como %(bill)s del proveedor y pagado con %(fund)s en la '
                    'rendición %(settlement)s.', bill=bill.display_name,
                    fund=fund.display_name, settlement=settlement_sudo.display_name))
