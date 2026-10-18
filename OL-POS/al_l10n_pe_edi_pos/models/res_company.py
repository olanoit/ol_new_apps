# -*- coding: utf-8 -*-
from odoo import api, models
from odoo.fields import Command


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model
    def _l10n_pe_edi_pos_set_loyalty_taxes(self):
        """Las tarjetas de regalo y las recargas del monedero de pos_loyalty no
        traen impuestos, y el comprobante electrónico exige uno en cada línea:
        sin él, la boleta no se emite y una venta cobrada en línea (Niubiz,
        Culqi…) queda pagada pero sin cerrar en la caja. Venderlas no es una
        venta de bienes gravada: el IGV se paga al canjearlas, así que llevan el
        impuesto inafecto (0 % Ina, código 9998) de cada compañía peruana. Solo
        completa productos sin impuesto de venta en esa compañía."""
        if 'loyalty.program' not in self.env:
            return
        # sudo: tarea de configuración (instalación o actualización del módulo)
        # que recorre programas y productos de todas las compañías.
        programs_sudo = self.env['loyalty.program'].sudo().with_context(active_test=False).search(
            [('program_type', 'in', ('gift_card', 'ewallet'))])
        products = programs_sudo.trigger_product_ids.product_tmpl_id
        # Los productos de Odoo para tarjetas de regalo y recargas del monedero
        # se venden en el TPV aunque no haya un programa que los use.
        for xmlid in ('loyalty.gift_card_product_50', 'loyalty.ewallet_product_50'):
            products |= self.env.ref(xmlid, raise_if_not_found=False).sudo().product_tmpl_id
        companies = self.sudo().search([('account_fiscal_country_id.code', '=', 'PE')])
        for company in companies:
            tax = self.env['account.tax'].sudo().search([
                ('company_id', '=', company.id), ('type_tax_use', '=', 'sale'),
                ('l10n_pe_edi_tax_code', '=', '9998'), ('amount', '=', 0)], limit=1)
            if not tax:
                continue
            for product in products.with_company(company):
                if not product.taxes_id.filtered(lambda t: t.company_id == company):
                    product.taxes_id = [Command.link(tax.id)]
