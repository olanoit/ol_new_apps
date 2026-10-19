# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.fields import Command

from .product_product import PAYMENT_PROGRAM_TYPES


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_pos_voucher_account_id = fields.Many2one(
        'account.account', string='Cuenta de tarjetas de regalo y monedero',
        check_company=True, domain="[('account_type', 'in', ('liability_current', 'liability_payable'))]",
        help='Pasivo con el cliente por las tarjetas de regalo y recargas del monedero vendidas '
             'y aún no canjeadas. La venta lo aumenta y el canje lo disminuye; nunca es ingreso '
             'ni lleva IGV (Informe SUNAT 097-2010).')

    @api.model
    def _l10n_pe_pos_setup_vouchers(self):
        """Al instalar o actualizar: cuenta de pasivo por defecto (496 Ingresos
        diferidos del PCGE) y sin impuesto en los productos de tarjetas y
        recargas, que ya no entran en el comprobante. Quita solo el impuesto
        inafecto (9998) que les ponía antes al_l10n_pe_edi_pos: con él, la
        venta aparecía como operación inafecta en el registro de ventas."""
        # sudo: tarea de configuración (instalación o actualización del módulo)
        # que recorre compañías, cuentas y productos compartidos.
        companies_sudo = self.sudo().search([('account_fiscal_country_id.code', '=', 'PE')])
        products_sudo = self.env['product.product'].sudo()._l10n_pe_pos_voucher_products()
        discount_products_sudo = self.env['loyalty.program'].sudo().with_context(active_test=False).search(
            [('program_type', 'in', PAYMENT_PROGRAM_TYPES)]).reward_ids.discount_line_product_id
        for company_sudo in companies_sudo:
            if not company_sudo.l10n_pe_pos_voucher_account_id:
                Account = self.env['account.account'].sudo().with_company(company_sudo)
                company_sudo.l10n_pe_pos_voucher_account_id = Account.search([
                    *Account._check_company_domain(company_sudo),
                    ('code', '=like', '496%'), ('account_type', '=', 'liability_current'),
                ], order='code', limit=1)
            for product_sudo in products_sudo.product_tmpl_id:
                taxes = product_sudo.taxes_id.filtered(
                    lambda t: t.company_id == company_sudo and t.l10n_pe_edi_tax_code == '9998')
                if taxes:
                    product_sudo.taxes_id = [Command.unlink(tax.id) for tax in taxes]
            # El canje es una forma de pago: su producto de descuento no lleva
            # el impuesto de venta que Odoo le pone al crearlo.
            for product_sudo in discount_products_sudo.product_tmpl_id:
                taxes = product_sudo.taxes_id.filtered(lambda t: t.company_id == company_sudo)
                if taxes:
                    product_sudo.taxes_id = [Command.unlink(tax.id) for tax in taxes]
