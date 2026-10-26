# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Cuentas de orden (PCGE, elemento 0): la carta fianza no es deuda mientras
    # no se ejecute, pero conviene tenerla a la vista en el balance de comprobación.
    l10n_pe_guarantee_memo = fields.Boolean(
        string='Cartas fianza en cuentas de orden',
        help='Registra cada carta fianza vigente en cuentas de orden y la extorna al liberarla o ejecutarla.')
    l10n_pe_guarantee_memo_journal_id = fields.Many2one(
        'account.journal', string='Diario de cuentas de orden', check_company=True,
        domain="[('type', '=', 'general')]")
    l10n_pe_guarantee_issued_debit_id = fields.Many2one(
        'account.account', string='Emitidas: cuenta deudora', check_company=True,
        help='Vacía: 0113 otras cuentas de orden deudoras.')
    l10n_pe_guarantee_issued_credit_id = fields.Many2one(
        'account.account', string='Emitidas: contrapartida', check_company=True,
        help='Vacía: 0114 deudoras por contra.')
    l10n_pe_guarantee_received_debit_id = fields.Many2one(
        'account.account', string='Recibidas: contrapartida', check_company=True,
        help='Vacía: 0129 acreedoras por contra.')
    l10n_pe_guarantee_received_credit_id = fields.Many2one(
        'account.account', string='Recibidas: cuenta acreedora', check_company=True,
        help='Vacía: 0126 bienes y valores recibidos.')

    def _get_company_root_delegated_field_names(self):
        return super()._get_company_root_delegated_field_names() + [
            'l10n_pe_guarantee_memo', 'l10n_pe_guarantee_memo_journal_id',
            'l10n_pe_guarantee_issued_debit_id', 'l10n_pe_guarantee_issued_credit_id',
            'l10n_pe_guarantee_received_debit_id', 'l10n_pe_guarantee_received_credit_id']

    def _l10n_pe_guarantee_memo_accounts(self, direction):
        """(cuenta del debe, cuenta del haber) de las cuentas de orden al emitir."""
        self.ensure_one()
        company = self.root_id

        def ref(xmlid):
            return self.env.ref('account.%s_%s' % (company.id, xmlid), raise_if_not_found=False) \
                or self.env['account.account']
        if direction == 'issued':
            return (company.l10n_pe_guarantee_issued_debit_id or ref('chart0113'),
                    company.l10n_pe_guarantee_issued_credit_id or ref('chart0114'))
        return (company.l10n_pe_guarantee_received_debit_id or ref('chart0129'),
                company.l10n_pe_guarantee_received_credit_id or ref('chart0126'))


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_guarantee_memo = fields.Boolean(related='company_id.l10n_pe_guarantee_memo', readonly=False)
    l10n_pe_guarantee_memo_journal_id = fields.Many2one(
        related='company_id.l10n_pe_guarantee_memo_journal_id', readonly=False)
    l10n_pe_guarantee_issued_debit_id = fields.Many2one(
        related='company_id.l10n_pe_guarantee_issued_debit_id', readonly=False)
    l10n_pe_guarantee_issued_credit_id = fields.Many2one(
        related='company_id.l10n_pe_guarantee_issued_credit_id', readonly=False)
    l10n_pe_guarantee_received_debit_id = fields.Many2one(
        related='company_id.l10n_pe_guarantee_received_debit_id', readonly=False)
    l10n_pe_guarantee_received_credit_id = fields.Many2one(
        related='company_id.l10n_pe_guarantee_received_credit_id', readonly=False)
