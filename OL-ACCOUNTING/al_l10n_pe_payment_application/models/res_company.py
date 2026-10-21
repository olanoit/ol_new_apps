from odoo import fields, models

ADVANCE_ACCOUNT_DOMAIN = "[('account_type', '=', '%s'), ('reconcile', '=', True)]"


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_application_journal_id = fields.Many2one(
        'account.journal', string='Diario de aplicaciones', check_company=True,
        domain="[('type', '=', 'general')]",
        help='Diario de los asientos que aplican anticipos y compensan documentos.')
    l10n_pe_advance_customer_account_id = fields.Many2one(
        'account.account', string='Anticipos de clientes', check_company=True,
        domain=ADVANCE_ACCOUNT_DOMAIN % 'asset_receivable',
        help='Cuenta de los anticipos recibidos de clientes (PCGE 122).')
    l10n_pe_advance_customer_fc_account_id = fields.Many2one(
        'account.account', string='Anticipos de clientes (M.E.)', check_company=True,
        domain=ADVANCE_ACCOUNT_DOMAIN % 'asset_receivable',
        help='Opcional: anticipos en moneda extranjera. Vacía, se usa la anterior.')
    l10n_pe_advance_supplier_account_id = fields.Many2one(
        'account.account', string='Anticipos a proveedores', check_company=True,
        domain=ADVANCE_ACCOUNT_DOMAIN % 'liability_payable',
        help='Cuenta de los anticipos entregados a proveedores (PCGE 422).')
    l10n_pe_advance_supplier_fc_account_id = fields.Many2one(
        'account.account', string='Anticipos a proveedores (M.E.)', check_company=True,
        domain=ADVANCE_ACCOUNT_DOMAIN % 'liability_payable',
        help='Opcional: anticipos en moneda extranjera. Vacía, se usa la anterior.')

    def _l10n_pe_advance_account(self, partner_type, currency):
        """Cuenta de anticipos según el tipo de socio y la moneda."""
        self.ensure_one()
        company = self.root_id
        foreign = currency and currency != company.currency_id
        if partner_type == 'customer':
            return (foreign and company.l10n_pe_advance_customer_fc_account_id) \
                or company.l10n_pe_advance_customer_account_id
        return (foreign and company.l10n_pe_advance_supplier_fc_account_id) \
            or company.l10n_pe_advance_supplier_account_id

    def _l10n_pe_advance_accounts(self):
        self.ensure_one()
        company = self.root_id
        return (company.l10n_pe_advance_customer_account_id
                | company.l10n_pe_advance_customer_fc_account_id
                | company.l10n_pe_advance_supplier_account_id
                | company.l10n_pe_advance_supplier_fc_account_id)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_application_journal_id = fields.Many2one(
        related='company_id.l10n_pe_application_journal_id', readonly=False)
    l10n_pe_advance_customer_account_id = fields.Many2one(
        related='company_id.l10n_pe_advance_customer_account_id', readonly=False)
    l10n_pe_advance_customer_fc_account_id = fields.Many2one(
        related='company_id.l10n_pe_advance_customer_fc_account_id', readonly=False)
    l10n_pe_advance_supplier_account_id = fields.Many2one(
        related='company_id.l10n_pe_advance_supplier_account_id', readonly=False)
    l10n_pe_advance_supplier_fc_account_id = fields.Many2one(
        related='company_id.l10n_pe_advance_supplier_fc_account_id', readonly=False)
