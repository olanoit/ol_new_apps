# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_expense_journal_id = fields.Many2one(
        'account.journal', string='Diario de comprobantes de gastos', check_company=True,
        domain="[('type', '=', 'purchase'), ('l10n_latam_use_documents', '=', True)]",
        help='Diario de compras con documentos donde se registran las facturas de los gastos '
             'pagados con un fondo. Vacío: el primer diario de compras con documentos.')

    def _l10n_pe_expense_journal(self):
        self.ensure_one()
        return self.l10n_pe_expense_journal_id or self.env['account.journal'].search([
            *self.env['account.journal']._check_company_domain(self),
            ('type', '=', 'purchase'), ('l10n_latam_use_documents', '=', True)], limit=1)
